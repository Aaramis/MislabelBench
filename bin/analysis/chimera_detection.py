#!/usr/bin/env python3
"""Error kind 7 across its two axes: how far apart the parents are, and where the breakpoint falls.

One row per (distance, breakpoint) per condition, pooled over the three seeds: how many chimeras
were flagged, and among those, how many had a proposed lineage that sided with the unlabelled
parent at the rank where the parents differ. Both numbers come from bin/analysis/score_injection.py's
record for the cell, so the definition is in one place.
"""

import argparse
import json
import subprocess
import tempfile
import sys
from collections import defaultdict
from pathlib import Path

RANKS = ["genus", "family", "order", "phylum"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chimera-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--condition", required=True, help="e.g. epang_T8_K25__rep1")
    p.add_argument("--scorer", default=str(Path(__file__).with_name("score_injection.py")))
    p.add_argument("--out")
    args = p.parse_args()

    cells = defaultdict(lambda: {"cells": 0, "injected": 0, "detected": 0, "sides_b": 0})
    for truth_p in sorted(Path(args.chimera_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        mis = Path(args.runs_dir) / f"{cell}__{args.condition}" / f"{cell}__{args.condition}.mis"
        if not mis.exists():
            continue
        truth = json.loads(truth_p.read_text())
        # Into a file and not /dev/stdout: the scorer prints its own summary there too, and the
        # first run on the 72 cells died on "Extra data" after the JSON.
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            subprocess.run([sys.executable, args.scorer, "--truth", str(truth_p), "--mis", str(mis),
                            "--out", tmp.name], capture_output=True, text=True, check=True)
            score = json.loads(Path(tmp.name).read_text())
        row = next(r for r in score["by_confidence"] if r["threshold"] == 0.0)
        key = (truth["distance"], truth["breakpoint"])
        c = cells[key]
        c["cells"] += 1
        c["injected"] += score["n_injected"]
        hits = round(row["recall"] * score["n_injected"])
        c["detected"] += hits
        c["sides_b"] += round((row["proposed_sides_with_other_parent"] or 0) * hits)

    if not cells:
        sys.exit(f"no chimera cell of {args.condition} under {args.runs_dir}")
    print(f"{args.condition}: chimeras flagged, and of those, proposals siding with the other parent")
    print(f"{'distance':10}{'breakpoint':>11}{'cells':>6}{'chimeras':>9}{'flagged':>8}{'recall':>8}"
          f"{'sides B':>9}{'of flagged':>11}")
    rows = []
    for (dist, bp), c in sorted(cells.items(), key=lambda kv: (RANKS.index(kv[0][0]), kv[0][1])):
        recall = c["detected"] / c["injected"]
        sides = c["sides_b"] / c["detected"] if c["detected"] else None
        print(f"{dist:10}{bp:>11.2f}{c['cells']:>6}{c['injected']:>9}{c['detected']:>8}{recall:>8.3f}"
              f"{c['sides_b']:>9}{(f'{sides:.3f}' if sides is not None else '-'):>11}")
        rows.append({"distance": dist, "breakpoint": bp, **c, "recall": round(recall, 4),
                     "sides_with_other_parent_of_flagged": round(sides, 4) if sides is not None else None})
    if args.out:
        Path(args.out).write_text(json.dumps({"condition": args.condition, "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
