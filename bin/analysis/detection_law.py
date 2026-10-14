#!/usr/bin/env python3
"""What governs detection of a shared mislabel: the fold scheme, or the surviving labels?

The grid shows recall falling steeply with k at every taxonomic distance, in the K=25 condition
that was supposed to handle exactly this case. Fold co-location does not explain it: folds are a
stride over sorted leaf names (epang_l1o.py, `ordered[i::K]`), so with K=25 two members of a
group share a fold about 4 % of the time, while recall at k=2 is 0.60.

The construction says what does. The k injected sequences are drawn from one donor group, so
they are relatives, and the group keeps at least one correctly labelled member. When one is
removed, what it is placed against is its own relatives: k-1 now carry the wrong label and the
rest carry the right one. This script tests whether that ratio predicts detection.

If it does, the limit is a property of leave-one-out itself and not of this implementation, and
it explains why K=5 and K=25 find the same sequences.
"""

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path


def flagged(path):
    return {l.split("\t")[0] for l in Path(path).read_text().splitlines()
            if l.strip() and not l.startswith(";")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-tax", required=True)
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--condition", required=True)
    p.add_argument("--also-present", metavar="CONDITION",
                   help="restrict to cells that also have this condition. Needed whenever one arm of "
                        "the grid lags: comparing a curve over 180 cells against one over 99 compares "
                        "the cell sets as much as the tools.")
    p.add_argument("--bins", type=int, default=5)
    p.add_argument("--out")
    args = p.parse_args()

    group_size = defaultdict(int)
    for line in Path(args.base_tax).read_text().splitlines():
        if line.strip():
            group_size[line.partition("\t")[2]] += 1

    buckets = defaultdict(lambda: [0, 0])
    by_k = defaultdict(lambda: [0, 0])
    # The donor groups each k actually drew from. README explains that k is not an independent
    # variable -- raising it shrinks the eligible pool and shifts it towards large taxa -- with a
    # table of group counts, median sizes and shares relabelled that no record produced.
    #
    # Weighted by injected sequence and not by taxon, which is the choice that matters: the question
    # is what a typical injected sequence sees, not what a typical taxon looks like. The two differ --
    # at k=5 the median size is 9 per sequence and 10 per taxon -- and computing it per taxon here
    # first made README's table look wrong when it was this statistic that was.
    sizes_by_k = defaultdict(list)
    groups_by_k = defaultdict(set)
    for truth_p in sorted(Path(args.injected_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        mis = Path(args.runs_dir) / f"{cell}__{args.condition}" / f"{cell}__{args.condition}.mis"
        if not mis.exists():
            continue
        if args.also_present:
            other = (Path(args.runs_dir) / f"{cell}__{args.also_present}"
                     / f"{cell}__{args.also_present}.mis")
            if not other.exists():
                continue
        hits = flagged(mis)
        t = json.loads(truth_p.read_text())
        k = t["k"]
        for name, rec in t["injected"].items():
            # Relatives that survive the removal of this one sequence, by which label they carry.
            wrong, right = k - 1, group_size[rec["true"]] - k
            if wrong + right == 0:
                continue
            groups_by_k[k].add(rec["true"])
            sizes_by_k[k].append(group_size[rec["true"]])
            b = min(int(wrong / (wrong + right) * args.bins), args.bins - 1)
            for d in (buckets[b], by_k[k]):
                d[0] += name in hits
                d[1] += 1

    width = 1 / args.bins
    print(f"condition {args.condition}"
          + (f", restricted to cells that also have {args.also_present}" if args.also_present else ""))
    print("recall by the fraction of surviving relatives that carry the wrong label")
    out = {"by_ratio": [], "by_k": []}
    for b in range(args.bins):
        hit, tot = buckets[b]
        if not tot:
            continue
        print(f"  {b * width:.1f}-{(b + 1) * width:.1f}  {hit:5}/{tot:<6} {hit / tot:.3f}")
        out["by_ratio"].append({"low": round(b * width, 3), "high": round((b + 1) * width, 3),
                                "detected": hit, "injected": tot, "recall": round(hit / tot, 4)})
    print("\nrecall by k, for comparison")
    for k in sorted(by_k):
        hit, tot = by_k[k]
        print(f"  k={k:<3} {hit:5}/{tot:<6} {hit / tot:.3f}")
        sizes = sizes_by_k[k]
        out["by_k"].append({"k": k, "detected": hit, "injected": tot,
                            "recall": round(hit / tot, 4),
                            "donor_groups": tot // k,
                            "distinct_donor_taxa": len(groups_by_k[k]),
                            "median_group_size": st.median(sizes) if sizes else None,
                            "mean_share_relabelled": round(st.mean(k / n for n in sizes), 2) if sizes else None,
                            # A taxon can host k injections only with k+1 members, which is what
                            # shrinks the pool: the count is of the whole base, not of what was drawn.
                            "eligible_taxa": sum(1 for n in group_size.values() if n >= k + 1)})
    # The two tables count the same injected sequences, so their totals must agree. They would not
    # if a sequence landed outside the printed bins: group_size is a defaultdict, so a true lineage
    # absent from the base taxonomy gives right = -k, a negative ratio, a negative bucket index, and
    # a row that is tallied and then never printed, while by_k keeps it. Unreachable in the data --
    # 0 of 11 178 injected sequences has a missing lineage or a donor group without a survivor --
    # and silent if it ever became reachable, which is the reason to compare rather than to guard.
    ratio_total = sum(r["injected"] for r in out["by_ratio"])
    k_total = sum(r["injected"] for r in out["by_k"])
    if ratio_total != k_total:
        raise SystemExit(f"the ratio table covers {ratio_total} injected sequences and the k table "
                         f"{k_total}: {k_total - ratio_total} fell outside the printed bins")

    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
