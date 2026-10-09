#!/usr/bin/env python3
"""Side by side: where each engine put the sequences the two tools disagree on.

The co-author's suggestion on the engine disagreement was to "compare the placements for those
cases where results deviate". bin/placement_locality.py reads one tool's placements for one cell;
this joins two of its records -- upstream's and the fork's, same cell -- on the sequence, restricted
to the sequences flagged by exactly one of them, and writes one row per sequence with both edges,
both weights, both clade readings and whether each landed among the k-1 co-carriers.

What the table can show that the flag sets cannot: whether the two engines placed a deviating
sequence on different edges at all, or on the same edge with different weight, or on the same edge
with the same weight and the scoring code read it differently -- which is the three-way distinction
the minimal cases could not make from .mis files.
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

    cols = ["sequence", "flagged_upstream", "flagged_fork", "edge_upstream", "edge_fork", "same_edge",
            "lwr_upstream", "lwr_fork", "below_wrong_upstream", "below_wrong_fork",
            "below_true_upstream", "below_true_fork", "among_upstream", "among_fork"]
    rows = []
    for s in shared:
        a, b = up[s], fk[s]
        rows.append([s, a["flagged"], b["flagged"], a["edge"], b["edge"], a["edge"] == b["edge"],
                     a["lwr"], b["lwr"], a["below_agree_with_wrong_to_rank"],
                     b["below_agree_with_wrong_to_rank"], a["below_agree_with_true_to_rank"],
                     b["below_agree_with_true_to_rank"], a["among_co_carriers"], b["among_co_carriers"]])
    deviating = [r for r in rows if r[1] != r[2]]
    same_edge = sum(1 for r in deviating if r[5])
    print(f"{len(shared)} injected sequences placed by both engines, {len(deviating)} flagged by one "
          f"only; of those, {same_edge} sit on the same edge in both and "
          f"{len(deviating) - same_edge} on different edges")
    for r in deviating[:12]:
        print(f"  {r[0]:42} up {'F' if r[1] else '-'} edge {r[3]:>5} lwr {r[6]:.3f} | "
              f"fork {'F' if r[2] else '-'} edge {r[4]:>5} lwr {r[7]:.3f}")
    if args.out:
        Path(args.out).write_text("\t".join(cols) + "\n"
                                  + "\n".join("\t".join(str(x) for x in r) for r in rows) + "\n")


if __name__ == "__main__":
    main()
