#!/usr/bin/env python3
"""Is the fork different from upstream on the k axis, and does fold co-removal explain it?

Three questions, in the order they have to be asked.

1. Is there a difference at all? On the completed 180-cell grid the fork gains 24, 15 and 10 points
   at k=2, 3 and 5, and nothing at k=1 and k=10. The figures in this paragraph read "6 to 8 points"
   while the grid was partial, which is what writing a measurement into a comment costs when the
   measurement is still arriving; they are rebuilt into results/fold_mechanism.json now, so a stale
   number shows up as a diff. A gap is still printed beside the spread, because three seeds per cell
   is not many: the ratio is 2.6 at k=2 and 0.06 at k=1.

2. If there is, is it the placement engine? At k=1 there is no shared label to anchor anything, so
   any engine difference shows there. If k=1 is equal, the engine is not the explanation.

3. Could it be fold co-removal? When a fold is removed, a co-carrier sometimes leaves with the
   target, and that case should behave like k=1. With K folds that happens with probability
   1 - (1 - 1/K)^(k-1), which predicts a gain of P x (recall at k=1 - recall at k). The prediction
   is testable twice over: against the observed gap, and against K=5 versus K=25 on the same
   cells, where P changes from 0.31 to 0.87 at k=10 and recall should move a lot if this is it.

The answer, now that the grid is complete, is that co-removal is not the explanation. It predicts
+0.022 at k=2 where the observed gap is +0.240 -- eleven times larger -- and +0.257 at k=10 where the
observed gap is +0.005. The second test agrees: raising P from 0.04 to 0.20 at k=2 by running K=5
instead of K=25 moves recall by -0.011, the wrong way. The engine is what differs, which
kexact_decomposition.py shows directly by removing the folds and leaving the engine in place.
"""

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path


def by_k(path):
    """Recall at threshold zero, averaged over every (distance, rate) cell, per k.

    A summary holds one row per (distance, rate, k), so {r["k"]: r for r in rows} keeps whichever
    row sorts last and silently reports a single slice. That was harmless on the 15-cell sweeps this
    was written for, where one distance and one rate meant one row per k, and wrong the moment it
    was pointed at the 180-cell grid: it reported the species/5% slice as if it were the whole grid.
    """
    d = json.loads(Path(path).read_text())
    by_k.cells[path] = d.get("n_cells")
    groups = defaultdict(list)
    for r in d["rows"]:
        if r["metric"] == "by_confidence" and r["threshold"] == 0.0 \
                and r["recall_mean"] is not None:
            groups[r["k"]].append(r)
    out = {}
    for k, rows in groups.items():
        out[k] = {"k": k, "n_rows": len(rows),
                  "recall_mean": st.mean(r["recall_mean"] for r in rows),
                  # Spread across cells, which is what a difference between conditions has to beat.
                  "recall_sd": st.stdev([r["recall_mean"] for r in rows]) if len(rows) > 1
                               else rows[0]["recall_sd"]}
    return out


by_k.cells = {}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--upstream", required=True, help="grid summary json for the comparator")
    p.add_argument("--fork", required=True, help="grid summary json for the fork at K=25")
    p.add_argument("--fork-k5", help="grid summary json for the fork at K=5, same cells")
    p.add_argument("--folds", type=int, default=25, help="fold count of --fork")
    # --folds governed the first table and the second hard-coded 5 and 25, so passing --folds 5 would
    # have relabelled one table and not the other. Both read their fold count from a flag now.
    p.add_argument("--folds-k5", type=int, default=5, help="fold count of --fork-k5")
    p.add_argument("--out", help="write the two tables as a record")
    args = p.parse_args()

    up, fk = by_k(args.upstream), by_k(args.fork)
    shared = sorted(set(up) & set(fk))
    if not shared:
        raise SystemExit("the two summaries share no k value")

    record = {"folds": args.folds, "folds_k5": args.folds_k5, "by_k": [], "fold_count": []}
    print(f"{'k':>3}{'upstream':>18}{'fork':>18}{'gap':>9}{'sd':>8}{'gap/sd':>8}"
          f"{'co-removal':>12}{'predicted':>11}")
    for k in shared:
        u, f = up[k], fk[k]
        sd = ((u["recall_sd"] ** 2 + f["recall_sd"] ** 2) / 2) ** 0.5
        gap = f["recall_mean"] - u["recall_mean"]
        pco = 1 - (1 - 1 / args.folds) ** (k - 1)
        pred = pco * (up[shared[0]]["recall_mean"] - u["recall_mean"])
        print(f"{k:>3}{u['recall_mean']:11.3f} ±{u['recall_sd']:5.3f}"
              f"{f['recall_mean']:11.3f} ±{f['recall_sd']:5.3f}{gap:+9.3f}{sd:8.3f}"
              f"{(gap / sd if sd else float('inf')):8.2f}{pco:12.3f}{pred:+11.3f}")
        record["by_k"].append({"k": k, "upstream": round(u["recall_mean"], 4),
                               "fork": round(f["recall_mean"], 4), "gap": round(gap, 4),
                               "sd": round(sd, 4), "p_co_removal": round(pco, 4),
                               "predicted_gap": round(pred, 4)})

    if args.fork_k5:
        k5 = by_k(args.fork_k5)
        # The fold-count comparison is only meaningful on one cell set. Comparing a K=5 sweep
        # against a K=25 run over different cells would mix the fold effect with the cells.
        a, b = by_k.cells.get(args.fork_k5), by_k.cells.get(args.fork)
        if a != b:
            print(f"\nwarning: {args.fork_k5} covers {a} cells and {args.fork} covers {b}; "
                  "pass the K=25 summary computed on the same cells for this comparison",
                  file=sys.stderr)
        print(f"\nsame cells, K=5 against K=25. Co-removal predicts a large gain here and nothing"
              f" else does.")
        print(f"{'k':>3}{'K=5':>9}{'K=25':>9}{'diff':>9}{'P(co-rm) K=5':>14}{'P(co-rm) K=25':>15}")
        for k in sorted(set(k5) & set(fk)):
            print(f"{k:>3}{k5[k]['recall_mean']:9.3f}{fk[k]['recall_mean']:9.3f}"
                  f"{k5[k]['recall_mean'] - fk[k]['recall_mean']:+9.3f}"
                  f"{1 - (1 - 1 / args.folds_k5) ** (k - 1):14.3f}"
                  f"{1 - (1 - 1 / args.folds) ** (k - 1):15.3f}")
            record["fold_count"].append(
                {"k": k, "k5": round(k5[k]["recall_mean"], 4),
                 "k25": round(fk[k]["recall_mean"], 4),
                 "diff": round(k5[k]["recall_mean"] - fk[k]["recall_mean"], 4),
                 "p_co_removal_k5": round(1 - (1 - 1 / args.folds_k5) ** (k - 1), 4),
                 "p_co_removal_k25": round(1 - (1 - 1 / args.folds) ** (k - 1), 4)})

    if args.out:
        Path(args.out).write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
