#!/usr/bin/env python3
"""Is a foreign sequence flagged because of where it places, or because it aligns badly?

Error kind 6 adds bacterial sequences to the archaeal set under an archaeal label, and both tools find
almost all of them. The protocol promises the alignment score beside the recall, because the donors
align to the archaeal covariance model at a median 1009 bits against 1509 for the archaea: part of what
makes them conspicuous may be the poor alignment rather than their position in the tree.

That is testable rather than merely sayable. If flagging tracks the bit score, the signal is alignment
quality and a filter on the score would do the same work. If the flagged and unflagged donors have the
same score distribution, the detection is phylogenetic and the caveat was overcautious.
"""

import argparse
import json
import statistics as st
from pathlib import Path


def cmalign_scores(path):
    """Sequence name to bit score, from cmalign's --sfile table."""
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split()
        if len(f) >= 7:
            try:
                out[f[1]] = float(f[6])
            except ValueError:
                pass
    return out


def flagged(mis):
    return {l.split("\t")[0] for l in Path(mis).read_text().splitlines()
            if l.strip() and not l.startswith(";")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--donor-scores", required=True, help="cmalign --sfile for the donor pool")
    p.add_argument("--base-scores", help="cmalign --sfile for the archaeal set, for contrast")
    p.add_argument("--foreign-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--condition", required=True)
    p.add_argument("--out")
    args = p.parse_args()

    scores = cmalign_scores(args.donor_scores)
    hit, miss = [], []
    for truth_p in sorted(Path(args.foreign_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        mis = Path(args.runs_dir) / f"{cell}__{args.condition}" / f"{cell}__{args.condition}.mis"
        if not mis.exists():
            continue
        f = flagged(mis)
        for name in json.loads(truth_p.read_text())["injected"]:
            if name not in scores:
                continue
            (hit if name in f else miss).append(scores[name])

    if not hit and not miss:
        raise SystemExit("no donor matched a run; check --runs-dir and --condition")

    def describe(v):
        if not v:
            return "none"
        return (f"n={len(v)} median={st.median(v):.1f} "
                f"range {min(v):.1f}-{max(v):.1f}")

    print(f"donors flagged     {describe(hit)}")
    print(f"donors not flagged {describe(miss)}")
    if args.base_scores:
        base = list(cmalign_scores(args.base_scores).values())
        print(f"archaeal set       {describe(base)}")
    # The median cannot answer the question it was given. Three quarters of the donors sit between
    # 1001 and 1014 bits, so a median difference of a fraction of a bit says nothing about the left
    # tail, which is the only place an alignment effect could live: a donor that aligns at 461 bits
    # is the one that might be flagged for aligning badly rather than for where it places. So count
    # the tail instead, against what independence predicts.
    tail = {}
    if hit and miss:
        print(f"\nmedian difference between flagged and unflagged donors: "
              f"{st.median(hit) - st.median(miss):+.2f} bits")
        print(f"lowest score  flagged {min(hit):.2f}  unflagged {min(miss):.2f}")
        allv = sorted(hit + miss)
        print(f"\n{'tail':>12}{'cut':>10}{'flagged':>9}{'unflag':>8}{'expected':>10}")
        for q in (0.05, 0.10, 0.25):
            cut = allv[int(len(allv) * q)]
            nh = sum(1 for v in hit if v <= cut)
            nm = sum(1 for v in miss if v <= cut)
            exp = len(hit) * (nh + nm) / len(allv)
            tail[f"below_p{int(q * 100)}"] = {"cut_bits": round(cut, 2), "flagged": nh,
                                             "unflagged": nm, "flagged_expected": round(exp, 1)}
            print(f"{'below p' + str(int(q * 100)):>12}{cut:10.2f}{nh:9}{nm:8}{exp:10.1f}")
        print("\nflagged at or near the expected count in every tail means the detection does not "
              "track alignment quality")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "condition": args.condition,
            "flagged": {"n": len(hit), "median": round(st.median(hit), 2) if hit else None},
            "unflagged": {"n": len(miss), "median": round(st.median(miss), 2) if miss else None},
            "low_score_tail": tail,
        }, indent=2))


if __name__ == "__main__":
    main()
