#!/usr/bin/env python3
"""Side by side: where each engine put the sequences the two tools disagree on.

The co-author's suggestion on the engine disagreement was to "compare the placements for those
cases where results deviate". bin/analysis/placement_locality.py reads one tool's placements for one cell;
this joins two of its records -- upstream's and the fork's, same cell -- on the sequence, restricted
to the sequences flagged by exactly one of them, and writes one row per sequence with both edges,
both weights, both clade readings and whether each landed among the k-1 co-carriers.

What the table can show that the flag sets cannot: whether the two engines placed a deviating
sequence in different clades at all, or in the same clade with different weight, or in the same
clade with the same weight and the scoring code read it differently -- which is the three-way
distinction the minimal cases could not make from .mis files.

Clades, not edge numbers. Upstream numbers edges on its full reference tree and the fork on the
tree of the fold that held the sequence out, so the same number names unrelated branches and an
equal number is a coincidence: on the first real cell one deviating sequence of 31 had equal numbers
and that said nothing. The edge numbers stay in the table as the way back to the jplace; what is
compared is the clade reading -- the rank to which the leaves below the edge agree with the wrong
label and with the true one, and whether the edge sits among the co-carriers.
"""

import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--upstream", required=True, help="placement_locality.py record, upstream")
    p.add_argument("--fork", required=True, help="placement_locality.py record, the fork")
    p.add_argument("--out")
    args = p.parse_args()

    up = {r["sequence"]: r for r in json.loads(Path(args.upstream).read_text())["rows"]}
    fk = {r["sequence"]: r for r in json.loads(Path(args.fork).read_text())["rows"]}
    shared = sorted(set(up) & set(fk))
    if not shared:
        raise SystemExit("the two records place no sequence in common")

    cols = ["sequence", "flagged_upstream", "flagged_fork", "edge_upstream", "edge_fork", "same_clade",
            "lwr_upstream", "lwr_fork", "below_wrong_upstream", "below_wrong_fork",
            "below_true_upstream", "below_true_fork", "among_upstream", "among_fork"]
    rows = []
    for s in shared:
        a, b = up[s], fk[s]
        reading = lambda r: (r["below_agree_with_wrong_to_rank"], r["below_agree_with_true_to_rank"],
                             r["among_co_carriers"])
        rows.append([s, a["flagged"], b["flagged"], a["edge"], b["edge"], reading(a) == reading(b),
                     a["lwr"], b["lwr"], a["below_agree_with_wrong_to_rank"],
                     b["below_agree_with_wrong_to_rank"], a["below_agree_with_true_to_rank"],
                     b["below_agree_with_true_to_rank"], a["among_co_carriers"], b["among_co_carriers"]])
    deviating = [r for r in rows if r[1] != r[2]]
    same = sum(1 for r in deviating if r[5])
    print(f"{len(shared)} injected sequences placed by both engines, {len(deviating)} flagged by one "
          f"only; of those, {same} read the same clade in both and "
          f"{len(deviating) - same} a different one")
    for side, idx in (("upstream", 1), ("fork", 2)):
        only = [r for r in deviating if r[idx]]
        if only:
            lwr = sorted((r[6], r[7]) for r in only)
            print(f"  flagged by {side} only: {len(only)}, median weight on the best edge "
                  f"upstream {sorted(x[0] for x in lwr)[len(lwr) // 2]:.3f}, "
                  f"fork {sorted(x[1] for x in lwr)[len(lwr) // 2]:.3f}")
    for r in deviating[:12]:
        print(f"  {r[0]:42} up {'F' if r[1] else '-'} edge {r[3]:>5} lwr {r[6]:.3f} | "
              f"fork {'F' if r[2] else '-'} edge {r[4]:>5} lwr {r[7]:.3f}")
    if args.out:
        Path(args.out).write_text("\t".join(cols) + "\n"
                                  + "\n".join("\t".join(str(x) for x in r) for r in rows) + "\n")


if __name__ == "__main__":
    main()
