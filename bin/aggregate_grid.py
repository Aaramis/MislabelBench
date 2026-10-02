#!/usr/bin/env python3
"""Score every cell of the injection grid and summarise it.

Produces one row per (distance, k, rate, threshold, metric) averaged over seeds, which is the
shape the figure needs: recall against a confidence threshold next to recall against an
exclusion threshold, so the two can be read side by side rather than argued about.
"""

import argparse
import json
import statistics as st
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--injected-dir", required=True, help="one directory per cell, with truth.json")
    p.add_argument("--runs-dir", required=True, help="collected runs")
    p.add_argument("--condition", required=True, help="condition suffix of the run directories")
    p.add_argument("--baseline-mis", help=".mis of the same tool on the un-injected subset")
    p.add_argument("--scorer", default="score_injection.py")
    p.add_argument("--out", default="grid_summary.json")
    p.add_argument("--thresholds", default="0.0,0.5,0.7,0.9,0.95,0.99")
    args = p.parse_args()

    cells, missing = [], []
    for truth in sorted(Path(args.injected_dir).glob("*/*.truth.json")):
        name = truth.parent.name
        run = Path(args.runs_dir) / f"{name}__{args.condition}"
        mis = run / f"{name}__{args.condition}.mis"
        if not mis.exists():
            missing.append(name)
            continue
        out = run / "score.json"
        cmd = [args.scorer, "--truth", str(truth), "--mis", str(mis),
               "--out", str(out), "--thresholds", args.thresholds]
        if args.baseline_mis:
            cmd += ["--baseline-mis", args.baseline_mis]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"scoring failed for {name}: {r.stderr.strip()}", file=sys.stderr)
            continue
        cells.append(json.loads(out.read_text()))

    if missing:
        print(f"warning: {len(missing)} cells had no .mis, first few: {missing[:3]}",
              file=sys.stderr)

    # Average over seeds. A cell is identified by everything except its seed.
    grouped = defaultdict(list)
    for c in cells:
        for metric in ("by_confidence", "by_exclusion"):
            for row in (c.get(metric) or []):
                key = (c["distance"], c["k"], c["rate"], metric, row["threshold"])
                grouped[key].append(row)

    summary = []
    for (dist, k, rate, metric, thr), rows in sorted(grouped.items()):
        recalls = [r["recall"] for r in rows if r["recall"] is not None]
        others = [r["flags_on_non_injected"] for r in rows]
        added = [r["added_vs_baseline"] for r in rows if r["added_vs_baseline"] is not None]
        summary.append({
            "distance": dist, "k": k, "rate": rate, "metric": metric, "threshold": thr,
            "seeds": len(rows),
            "recall_mean": round(st.mean(recalls), 4) if recalls else None,
            "recall_sd": round(st.stdev(recalls), 4) if len(recalls) > 1 else 0.0,
            "flags_on_non_injected_mean": round(st.mean(others), 1) if others else None,
            "added_vs_baseline_mean": round(st.mean(added), 1) if added else None,
        })

    Path(args.out).write_text(json.dumps(
        {"n_cells": len(cells), "n_missing": len(missing),
         "baseline_mis": args.baseline_mis, "rows": summary}, indent=2))
    print(f"scored {len(cells)} cells, {len(summary)} summary rows -> {args.out}")


if __name__ == "__main__":
    main()
