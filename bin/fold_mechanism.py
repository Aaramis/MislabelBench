#!/usr/bin/env python3
"""Is the fork different from upstream on the k axis, and does fold co-removal explain it?

Three questions, in the order they have to be asked.

1. Is there a difference at all? The means suggest the fork gains 6 to 8 points at k=2 to 5, but
   with three seeds per cell a gap has to be read next to the spread, so both are printed.

2. If there is, is it the placement engine? At k=1 there is no shared label to anchor anything, so
   any engine difference shows there. If k=1 is equal, the engine is not the explanation.

3. Could it be fold co-removal? When a fold is removed, a co-carrier sometimes leaves with the
   target, and that case should behave like k=1. With K folds that happens with probability
   1 - (1 - 1/K)^(k-1), which predicts a gain of P x (recall at k=1 - recall at k). The prediction
   is testable twice over: against the observed gap, and against K=5 versus K=25 on the same
   cells, where P changes from 0.31 to 0.87 at k=10 and recall should move a lot if this is it.
"""

import argparse
import json
import sys
from pathlib import Path


def by_k(path):
    d = json.loads(Path(path).read_text())
    by_k.cells[path] = d.get("n_cells")
    return {r["k"]: r for r in d["rows"]
            if r["metric"] == "by_confidence" and r["threshold"] == 0.0
            and r["recall_mean"] is not None}


by_k.cells = {}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--upstream", required=True, help="grid summary json for the comparator")
    p.add_argument("--fork", required=True, help="grid summary json for the fork at K=25")
    p.add_argument("--fork-k5", help="grid summary json for the fork at K=5, same cells")
    p.add_argument("--folds", type=int, default=25)
    args = p.parse_args()

    up, fk = by_k(args.upstream), by_k(args.fork)
    shared = sorted(set(up) & set(fk))
    if not shared:
        raise SystemExit("the two summaries share no k value")

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
                  f"{1 - 0.8 ** (k - 1):14.3f}{1 - (1 - 1 / 25) ** (k - 1):15.3f}")


if __name__ == "__main__":
    main()
