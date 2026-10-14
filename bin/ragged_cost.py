#!/usr/bin/env python3
"""What does an incomplete lineage cost detection?

A quarter of each cell's untouched lineages is cut to genus and a quarter to family
(slurm/make_ragged.sh), the injected sequences keep their full lineage, and the truth file is the
cell's own. So recall is comparable cell for cell against the full-lineage grid, which is checked
here rather than assumed: the run aborts if any cell's injected set differs from the full cell's.

Both tools, because whether SATIVA accepts ragged
lineages at all was otherwise unmeasured. If the two differ, that difference is the answer.

Two quantities, not one. Recall is the question asked; the count of flags on untouched sequences is
the one that can move for a reason that is not detection, since a sequence whose lineage stops at
genus cannot be flagged below it. Reporting only recall would hide that.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def flagged(path):
    """Sequence ids in a .mis. Header lines start with ';' and the file ends on a blank line."""
    return {l.split("\t")[0] for l in path.read_text(errors="replace").splitlines()
            if l.strip() and not l.startswith(";")}


def recall(runs_dir, cell, condition, injected):
    d = Path(runs_dir) / f"{cell}__{condition}__rep1"
    mis = d / f"{cell}__{condition}__rep1.mis"
    if not mis.exists():
        return None
    hits = flagged(mis)
    return {"detected": len(hits & injected), "injected": len(injected),
            "untouched_flags": len(hits - injected)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ragged-runs", default="results/ragged/runs")
    p.add_argument("--full-runs", default="results/grid_fork/runs")
    p.add_argument("--ragged-dir", default="data/ragged")
    p.add_argument("--full-dir", default="data/injected")
    p.add_argument("--conditions", default="epang_T8_K25,upstream_raxml_T8")
    p.add_argument("--out")
    args = p.parse_args()

    cells = sorted(d.name for d in Path(args.ragged_dir).iterdir() if d.is_dir())
    if not cells:
        raise SystemExit(f"no cells under {args.ragged_dir}")

    rows = []
    for cell in cells:
        full_cell = cell[4:] if cell.startswith("rag_") else cell
        rag_truth = json.loads((Path(args.ragged_dir) / cell / f"{cell}.truth.json").read_text())
        full_path = Path(args.full_dir) / full_cell / f"{full_cell}.truth.json"
        full_truth = json.loads(full_path.read_text())
        # The whole comparison rests on this. A cell whose injected set moved would be answering a
        # different question with the same name.
        if rag_truth["injected"].keys() != full_truth["injected"].keys():
            raise SystemExit(f"{cell}: injected set differs from {full_cell}")
        injected = set(rag_truth["injected"])
        for cond in args.conditions.split(","):
            rag = recall(args.ragged_runs, cell, cond, injected)
            full = recall(args.full_runs, full_cell, cond, injected)
            if rag is None or full is None:
                print(f"{cell} {cond}: missing "
                      + ("ragged" if rag is None else "") + ("full" if full is None else ""))
                continue
            rows.append({"cell": cell, "k": rag_truth["k"], "seed": rag_truth["seed"],
                         "condition": cond, "ragged": rag, "full": full})

    print(f"{'condition':20}{'k':>4}{'cells':>7}{'recall full':>13}{'recall ragged':>15}"
          f"{'delta':>8}{'untouched full':>16}{'untouched ragged':>18}")
    out = []
    for cond in args.conditions.split(","):
        by_k = defaultdict(list)
        for r in rows:
            if r["condition"] == cond:
                by_k[r["k"]].append(r)
        for k in sorted(by_k) + ["all"]:
            group = rows if k == "all" else by_k[k]
            group = [r for r in group if r["condition"] == cond]
            if not group:
                continue
            det = sum(r["ragged"]["detected"] for r in group)
            tot = sum(r["ragged"]["injected"] for r in group)
            fdet = sum(r["full"]["detected"] for r in group)
            ftot = sum(r["full"]["injected"] for r in group)
            ru, fu = (sum(r[s]["untouched_flags"] for r in group) for s in ("ragged", "full"))
            rr, fr = det / tot, fdet / ftot
            print(f"{cond:20}{str(k):>4}{len(group):>7}{fr:>13.3f}{rr:>15.3f}"
                  f"{rr - fr:>+8.3f}{fu:>16}{ru:>18}")
            out.append({"condition": cond, "k": k, "cells": len(group),
                        "recall_full": round(fr, 4), "recall_ragged": round(rr, 4),
                        "delta": round(rr - fr, 4), "untouched_full": fu, "untouched_ragged": ru})

    if args.out:
        Path(args.out).write_text(json.dumps({"cells": len(cells), "by_condition": out}, indent=2))


if __name__ == "__main__":
    main()
