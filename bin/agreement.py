#!/usr/bin/env python3
"""Do the two tools flag the same sequences, and propose the same labels?

The fork claims upstream's decision rule, unchanged: EPA-ng replaces RAxML for the placement and nothing
else moves. So agreement on un-injected data is the non-regression control, and it is the only reason
this benchmark keeps an agreement measure at all.

Two questions, and the second is the stricter one. Agreeing on *which* sequences are mislabelled is
weaker than agreeing on *what* they should be: a placement engine could pick the same suspects for
different reasons. Where both tools flag a sequence, this also compares the rank at which they say the
label goes wrong and the lineage they propose instead.
"""

import argparse
import json
from pathlib import Path


def read_mis(path):
    """SeqID -> (mislabelled level, proposed label, proposed path, confidence).

    A row this cannot parse, and a sequence named twice, are errors rather than omissions. The Jaccard
    below is a published number and both faults would lower it silently: `if len(f) >= 7` used to drop
    a short row without a word, and a dict keyed by SeqID keeps the last of a repeated one. Swept over
    the whole corpus before this was tightened -- 1 482 `.mis` files, 175 499 data rows, **0 short rows
    and 0 repeated ids** -- so refusing is free today and is the only version that stays true if the
    tool's output ever changes shape.
    """
    out = {}
    for n, line in enumerate(Path(path).read_text(errors="replace").splitlines(), 1):
        if not line.strip() or line.startswith(";"):
            continue
        f = line.split("\t")
        if len(f) < 7:
            raise SystemExit(f"{path}:{n}: {len(f)} columns, need at least 7")
        if f[0] in out:
            raise SystemExit(f"{path}:{n}: {f[0]} appears twice")
        out[f[0]] = (f[1], f[3], f[6], float(f[4]))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True, help=".mis from the comparator")
    p.add_argument("--b", required=True, help=".mis from the fork")
    p.add_argument("--label-a", default="upstream")
    p.add_argument("--label-b", default="fork")
    p.add_argument("--out")
    args = p.parse_args()

    A, B = read_mis(args.a), read_mis(args.b)
    both = set(A) & set(B)
    only_a, only_b = set(A) - set(B), set(B) - set(A)
    union = set(A) | set(B)

    same_rank = sum(1 for s in both if A[s][0] == B[s][0])
    same_label = sum(1 for s in both if A[s][1] == B[s][1])
    same_path = sum(1 for s in both if A[s][2] == B[s][2])

    print(f"{args.label_a}: {len(A)} flags, {args.label_b}: {len(B)} flags")
    print(f"  both           {len(both)}")
    print(f"  {args.label_a} only{'':5}{len(only_a)}")
    print(f"  {args.label_b} only{'':9}{len(only_b)}")
    print(f"  Jaccard        {len(both) / len(union):.3f}" if union else "  no flags")
    if both:
        print(f"  of the {len(both)} shared, they agree on")
        print(f"    the rank that is wrong    {same_rank}/{len(both)} ({100*same_rank/len(both):.1f}%)")
        print(f"    the proposed taxon name   {same_label}/{len(both)} "
              f"({100*same_label/len(both):.1f}%)")
        print(f"    the whole proposed path   {same_path}/{len(both)} "
              f"({100*same_path/len(both):.1f}%)")

    # The one-sided flags as rows, not as two counts. The counts were all that was written, so the
    # 51 and 119 of the 7 051-sequence baseline had no per-sequence record anywhere, and the question
    # "which sequences, at what confidence" -- the one the co-author asked -- had to be answered by
    # rereading two .mis files by hand. Everything below was already in memory.
    if args.out:
        rows = [f"side\tsequence\tlevel\tproposed\tpath\tconfidence"]
        for side, names, src in ((f"{args.label_a}_only", only_a, A), (f"{args.label_b}_only", only_b, B)):
            rows += [f"{side}\t{n}\t{src[n][0]}\t{src[n][1]}\t{src[n][2]}\t{src[n][3]}"
                     for n in sorted(names)]
        Path(args.out).with_name(Path(args.out).stem + "_disagreements.tsv").write_text(
            "\n".join(rows) + "\n")
        Path(args.out).write_text(json.dumps({
            "a": args.a, "b": args.b,
            "n_a": len(A), "n_b": len(B), "both": len(both),
            "only_a": len(only_a), "only_b": len(only_b),
            "jaccard": round(len(both) / len(union), 4) if union else None,
            "agree_rank": same_rank, "agree_label": same_label, "agree_path": same_path,
        }, indent=2))


if __name__ == "__main__":
    main()
