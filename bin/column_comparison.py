#!/usr/bin/env python3
"""Confidence against OriginalLabelExclusion, ranked on injected truth.

Section 2.5 of the protocol asked for curves rather than one threshold each. Every flagged
sequence in the grid is known to be injected or not, so both columns can be ranked on the same
set of calls, and the honest question is which one keeps more injected sequences at a matched
number of calls on untouched ones.

The second half looks at where the exclusion column was meant to earn its place. SATIVA credits
a placement sitting on a taxon's stem 0.51 to the parent and 0.49 to the taxon
(`parent_lhw_coeff`), so such a call reports confidence 0.510 whatever the evidence against the
declared label. The exclusion column reports that evidence directly.
"""

import argparse
import json
from pathlib import Path

STEM = 0.510


def collect(injected_dir, runs_dir, condition):
    rows = []
    for truth_p in sorted(Path(injected_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        mis = Path(runs_dir) / f"{cell}__{condition}" / f"{cell}__{condition}.mis"
        if not mis.exists():
            continue
        inj = set(json.loads(truth_p.read_text())["injected"])
        for line in mis.read_text().splitlines():
            if not line.strip() or line.startswith(";"):
                continue
            f = line.split("\t")
            if len(f) < 9:
                continue
            rows.append({"injected": f[0] in inj,
                         "confidence": float(f[4]), "exclusion": float(f[8])})
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--condition", required=True)
    p.add_argument("--out")
    args = p.parse_args()

    rows = collect(args.injected_dir, args.runs_dir, args.condition)
    if not rows:
        raise SystemExit("no flags found; check --runs-dir and --condition")
    n_inj = sum(r["injected"] for r in rows)
    print(f"{len(rows)} flags over the grid, {n_inj} of them on injected sequences\n")

    def curve(col):
        pts = []
        for t in sorted({r[col] for r in rows}):
            pts.append({"threshold": t,
                        "injected_kept": sum(1 for r in rows if r["injected"] and r[col] >= t),
                        "untouched_kept": sum(1 for r in rows
                                              if not r["injected"] and r[col] >= t)})
        return pts

    curves = {c: curve(c) for c in ("confidence", "exclusion")}
    floor = {c: min(p["untouched_kept"] for p in curves[c]) for c in curves}
    print("lowest reachable number of calls on untouched sequences, over the whole column range:")
    for c in curves:
        print(f"  {c:11} {floor[c]}")
    print("\ninjected flags kept at a matched budget of calls on untouched sequences")
    budgets = sorted({max(floor.values()), 12000, 16000, 17000})
    for b in budgets:
        line = f"  budget {b:6}:"
        for c in curves:
            ok = [p for p in curves[c] if p["untouched_kept"] <= b]
            line += (f"   {c} {max(p['injected_kept'] for p in ok):5}"
                     if ok else f"   {c} unreachable")
        print(line)

    stem = [r for r in rows if abs(r["confidence"] - STEM) < 1e-9]
    hi = [r for r in stem if r["exclusion"] >= 0.99]
    print(f"\nflags reported at confidence {STEM}: {len(stem)} "
          f"({100 * len(stem) / len(rows):.1f}% of all flags)")
    if stem:
        print(f"  of those, {len(hi)} ({100 * len(hi) / len(stem):.1f}%) have exclusion >= 0.99, "
              "so the declared label holds essentially none of the placement weight")
        print(f"  {sum(r['injected'] for r in stem)} are injected "
              f"({100 * sum(r['injected'] for r in stem) / len(stem):.1f}%, against "
              f"{100 * n_inj / len(rows):.1f}% over all flags)")
    else:
        # Not an error: on this grid 31.5 % of flags sit at 0.510, but a dataset where none does is
        # a dataset where parent_lhw_coeff never bit, which is worth saying rather than crashing on.
        print("  none, so the stem split never produced a call on this data")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "n_flags": len(rows), "n_injected_flags": n_inj,
            "untouched_floor": floor,
            "stem_flags": len(stem), "stem_exclusion_ge_099": len(hi),
            "stem_injected": sum(r["injected"] for r in stem),
            "curves": curves,
        }, indent=2))


if __name__ == "__main__":
    main()
