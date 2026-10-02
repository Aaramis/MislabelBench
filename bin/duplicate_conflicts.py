#!/usr/bin/env python3
"""Identical sequences under conflicting labels, in the reference itself.

Daniel's eighth comment asks about mislabels that are also duplicates. The injected version of that
question needs a construction; this one does not. Two sequences that are byte-identical cannot both be
right if their labels disagree, and finding them costs one pass and no phylogenetics.

Three things are reported, because each answers a different objection:

  how many groups of identical sequences carry conflicting labels, and at which rank they first differ
  whether they are identical before the alignment too, since --matchonly discards insertions and could
      make two different sequences look the same
  whether the tool flags them, which bounds what any method on this marker can do: if an identical
      sequence carries two labels then the marker cannot separate them and no placement can either

Identity rather than a similarity threshold, because a threshold needs an argument about where to put
it and identity does not.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def read_fasta(path):
    out, name, chunks = {}, None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith(">"):
            if name:
                out[name] = "".join(chunks)
            name, chunks = line[1:].split()[0], []
        else:
            chunks.append(line.strip())
    if name:
        out[name] = "".join(chunks)
    return out


def read_tax(path):
    return {l.partition("\t")[0]: l.partition("\t")[2]
            for l in Path(path).read_text().splitlines() if l.strip()}


def flagged_names(mis):
    return {l.split("\t")[0] for l in Path(mis).read_text().splitlines()
            if l.strip() and not l.startswith(";")}


def first_disagreement(labels):
    """Shallowest rank index at which any two of the labels differ."""
    return min(next((i for i, (x, y) in enumerate(zip(a.split(";"), b.split(";"))) if x != y), 7)
               for a in labels for b in labels if a != b)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--alignment", required=True)
    p.add_argument("--taxonomy", required=True)
    p.add_argument("--unaligned", help="the pre-alignment fasta, to tell a real duplicate from one the "
                                       "alignment created by discarding insertions")
    p.add_argument("--baseline-mis", help="a run on this un-injected set, to see what is flagged")
    p.add_argument("--out")
    args = p.parse_args()

    aln, tax = read_fasta(args.alignment), read_tax(args.taxonomy)
    raw = read_fasta(args.unaligned) if args.unaligned else {}
    flagged = flagged_names(args.baseline_mis) if args.baseline_mis else set()

    by_row = defaultdict(list)
    for name, seq in aln.items():
        if name in tax:
            by_row[seq].append(name)

    identical = [g for g in by_row.values() if len(g) > 1]
    conflicting = [g for g in identical if len({tax[n] for n in g}) > 1]
    agreeing = [g for g in identical if len({tax[n] for n in g}) == 1]

    by_rank, raw_identical, shallow = defaultdict(int), 0, []
    for g in conflicting:
        labels = {tax[n] for n in g}
        depth = first_disagreement(labels)
        by_rank[RANKS[depth] if depth < len(RANKS) else "deeper"] += 1
        if raw:
            same = len({raw.get(n) for n in g}) == 1 and all(n in raw for n in g)
            raw_identical += same
            if depth <= 2:
                shallow.append({"rank": RANKS[depth], "rows": len(g), "identical_unaligned": same,
                                "labels": sorted({l.split(";")[depth] for l in labels})})

    n = len(aln)
    print(f"{n} sequences, {len(by_row)} distinct alignment rows")
    print(f"{len(identical)} groups of identical rows covering "
          f"{sum(len(g) for g in identical)} sequences "
          f"({100 * sum(len(g) for g in identical) / n:.0f}%)")
    print(f"{len(conflicting)} of those groups carry conflicting labels")
    for r in RANKS + ["deeper"]:
        if by_rank.get(r):
            print(f"    first disagreeing at {r}: {by_rank[r]}")
    if raw:
        print(f"  identical before the alignment too: {raw_identical} of {len(conflicting)}")
        for s in sorted(shallow, key=lambda d: (RANKS.index(d["rank"]), -d["rows"])):
            print(f"    {s['rank']}: {s['rows']} rows, unaligned identical="
                  f"{s['identical_unaligned']}, {' vs '.join(s['labels'][:2])}")
    if flagged:
        members = [x for g in conflicting for x in g]
        same = [x for g in agreeing for x in g]
        print(f"  flagged by the tool: {sum(1 for x in members if x in flagged)} of {len(members)} "
              f"sequences in conflicting groups, "
              f"{sum(1 for g in conflicting if any(x in flagged for x in g))} of "
              f"{len(conflicting)} groups")
        print(f"  for contrast, identical rows that agree on their label: "
              f"{sum(1 for x in same if x in flagged)} of {len(same)} flagged")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "sequences": n, "distinct_rows": len(by_row),
            "identical_groups": len(identical), "conflicting_groups": len(conflicting),
            "conflict_first_rank": dict(by_rank),
            "conflicting_identical_unaligned": raw_identical if raw else None,
            "shallow_conflicts": shallow,
        }, indent=2))


if __name__ == "__main__":
    main()
