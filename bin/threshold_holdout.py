#!/usr/bin/env python3
"""Choose a threshold on one seed, report it on the others.

A threshold picked on the same data it is reported on flatters itself, and section 2.5 of the
protocol asks for the split. The grid has three seeds per cell, so the selection seed is held out
from the report: a threshold is chosen on seed 1 and the recall it gives is measured on seeds 2
and 3 only.

The criterion has to be stated because there is no such thing as a false positive here. A flag on
a sequence we did not inject may be a real mislabel in the base. So the threshold is the lowest
one whose collateral flags, meaning flags on sequences that are neither injected nor flagged in
the un-injected baseline, stay within a budget expressed as a multiple of the baseline count. The
budget is an argument and the report carries it, rather than a number chosen to look good.

The gap between the selection seed and the held-out seeds is the quantity of interest: a large one
means the threshold was fitted to noise.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

COLUMNS = {"confidence": 4, "exclusion": 8}


def read_mis(path):
    out = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.strip() or line.startswith(";"):
            continue
        f = line.split("\t")
        if len(f) > 8:
            out[f[0]] = {c: float(f[i]) for c, i in COLUMNS.items()}
    return out


def load(injected_dir, runs_dir, condition, baseline_mis):
    """One record per cell: its injected names and the flags with both column values."""
    baseline = set(read_mis(baseline_mis))
    cells = []
    for truth_p in sorted(Path(injected_dir).glob("*/*.truth.json")):
        name = truth_p.parent.name
        mis = Path(runs_dir) / f"{name}__{condition}" / f"{name}__{condition}.mis"
        if not mis.exists():
            continue
        t = json.loads(truth_p.read_text())
        injected = set(t["injected"])
        flags = read_mis(mis)
        cells.append({
            "cell": name, "seed": t["seed"], "k": t.get("k"),
            "distance": t["distance"], "rate": t.get("rate"),
            "n_injected": len(injected),
            "injected_flags": {s: v for s, v in flags.items() if s in injected},
            # Neither injected nor already flagged before any injection.
            "collateral_flags": {s: v for s, v in flags.items()
                                 if s not in injected and s not in baseline},
        })
    return cells, len(baseline)


def totals(cells, column, threshold):
    recall_hits = sum(1 for c in cells for v in c["injected_flags"].values()
                      if v[column] >= threshold)
    injected = sum(c["n_injected"] for c in cells)
    collateral = sum(1 for c in cells for v in c["collateral_flags"].values()
                     if v[column] >= threshold)
    return recall_hits, injected, collateral


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--condition", required=True)
    p.add_argument("--baseline-mis", required=True)
    p.add_argument("--select-seed", type=int, default=1)
    p.add_argument("--budget-multiples", default="1.0,0.5,0.3,0.2,0.1,0.05",
                   help="collateral flags allowed per cell, as multiples of the baseline count. "
                        "A loose budget is satisfied by the lowest threshold in the column and "
                        "filters nothing, so the useful ones are those that bite.")
    p.add_argument("--out")
    args = p.parse_args()

    cells, n_baseline = load(args.injected_dir, args.runs_dir, args.condition, args.baseline_mis)
    if not cells:
        raise SystemExit("no scored cell found; check --runs-dir and --condition")
    fit = [c for c in cells if c["seed"] == args.select_seed]
    held = [c for c in cells if c["seed"] != args.select_seed]
    if not fit or not held:
        raise SystemExit(f"need cells on seed {args.select_seed} and on other seeds; "
                         f"found {len(fit)} and {len(held)}")

    print(f"{len(cells)} cells, {len(fit)} on the selection seed {args.select_seed}, "
          f"{len(held)} held out; baseline {n_baseline} flags")
    collateral_per_cell = sum(len(c["collateral_flags"]) for c in cells) / len(cells)
    print(f"unfiltered collateral flags per cell: {collateral_per_cell:.1f}\n")
    print(f"{'budget/cell':>12}{'column':>12}{'threshold':>11}{'fit recall':>12}"
          f"{'held recall':>13}{'gap':>8}{'held coll.':>12}")

    report = {"condition": args.condition, "select_seed": args.select_seed,
              "baseline_flags": n_baseline, "n_cells_fit": len(fit), "n_cells_held": len(held),
              "collateral_per_cell_unfiltered": round(collateral_per_cell, 2), "budgets": []}

    # Candidate thresholds come from the selection seed only; the held-out cells are never
    # consulted when choosing one.
    candidates = {c: sorted({v[c] for cell in fit
                             for v in list(cell["injected_flags"].values())
                             + list(cell["collateral_flags"].values())})
                  for c in COLUMNS}

    for mult in [float(x) for x in args.budget_multiples.split(",")]:
        per_cell = mult * n_baseline
        entry = {"budget_multiple": mult, "budget_per_cell": round(per_cell, 2), "columns": {}}
        for column in COLUMNS:
            # Lowest threshold meeting the budget: recall only ever falls as the threshold rises.
            chosen = next((t for t in candidates[column]
                           if totals(fit, column, t)[2] <= per_cell * len(fit)), None)
            if chosen is None:
                print(f"{per_cell:12.1f}{column:>12}{'unreachable':>12}"
                      f"{'-':>12}{'-':>13}{'-':>8}{'-':>12}")
                entry["columns"][column] = {"threshold": None, "reason": "budget unreachable"}
                continue
            fh, fi, _ = totals(fit, column, chosen)
            hh, hi, hc = totals(held, column, chosen)
            fr, hr = fh / fi, hh / hi
            print(f"{per_cell:12.1f}{column:>12}{chosen:11.3f}{fr:12.3f}{hr:13.3f}"
                  f"{hr - fr:+8.3f}{hc:12}")
            entry["columns"][column] = {
                "threshold": chosen, "fit_recall": round(fr, 4), "held_recall": round(hr, 4),
                "gap": round(hr - fr, 4), "held_collateral": hc,
                "held_collateral_per_cell": round(hc / len(held), 2)}
        report["budgets"].append(entry)
        print()

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
