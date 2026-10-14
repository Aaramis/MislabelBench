#!/usr/bin/env python3
"""What a dataset looks like before anything is aligned, and whether leave-one-out can judge it.

One tool for every dataset here, so that the judgeability table in the protocol is computed one way
rather than per dataset. Two things decide whether the dataset is usable at all, and neither needs an aligner:

Length spread. The ratio of the 95th to the 5th percentile length says how much of an alignment
would be gap, in one number.

Judgeability. Leave-one-out removes a sequence and places it back, so it needs another sequence
carrying the same label. A taxon with one member cannot be judged at that rank at all. The
fraction of sequences whose taxon has at least one other member is therefore a ceiling on recall
that is a property of the database and not of either tool.

Also counted: how many lineages are ragged or carry placeholder ranks, because an all-placeholder
lineage collapses to the empty string and that is a parsing question the pipeline has already met.
"""

import argparse
import json
import re
import statistics as st
from collections import Counter
from pathlib import Path

RANKS_GTDB = ["domain", "phylum", "class", "order", "family", "genus", "species"]

# In gtdb_arc2k and gtdb_arc1200 every lineage is seven ranks deep, no rank is empty, and no label
# is a catch-all. Unnamed species are written per cluster -- s__JAJYEA01 sp021809545, 595 such
# labels over 1235 sequences at 2023, the largest holding 32 -- so two sequences sharing one are
# conspecific by GTDB's own definition and the sibling relation is real.
UNRESOLVED_GTDB = re.compile(r"^(?:sp|unidentified|unclassified|Incertae_sedis)$", re.I)

def is_unresolved(label):
    """label is the part after the x__ prefix."""
    return not label or bool(UNRESOLVED_GTDB.search(label))


def read_fasta_lengths(path):
    # n is compared rather than discarded. Lengths are keyed by accession, so a file with the same
    # accession twice loses the first one and n_sequences comes out short, with every percentile and
    # every judgeability denominator computed over the smaller set. The count was already taken here
    # and thrown away, which is the shape of a check someone meant to write. None of the 18 real
    # FASTA files under data/ has a repeat, so this has never fired and is cheap enough to keep.
    lengths, name, n = {}, None, 0
    for line in Path(path).open(errors="replace"):
        if line.startswith(">"):
            name = line[1:].split()[0]
            lengths[name] = 0
            n += 1
        elif name is not None:
            lengths[name] += len(line.strip())
    if n != len(lengths):
        raise SystemExit(f"{path}: {n} headers but {len(lengths)} distinct accessions")
    return lengths


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fasta", required=True)
    p.add_argument("--tax", required=True)
    p.add_argument("--convention", default="gtdb", choices=["gtdb"], help="how the labels write an unresolved rank")
    p.add_argument("--out", help="write the record here; without it the table above is the output")
    args = p.parse_args()

    RANKS = RANKS_GTDB

    lengths = read_fasta_lengths(args.fasta)
    vals = sorted(lengths.values())
    if not vals:
        raise SystemExit(f"no sequences in {args.fasta}")

    def pct(q):
        return vals[min(len(vals) - 1, int(q * len(vals)))]

    lineages = {}
    for line in Path(args.tax).open(errors="replace"):
        if line.strip():
            name, _, lin = line.partition("\t")
            lineages[name] = lin.strip()

    depths = Counter()
    placeholder = Counter()
    empty = 0
    members = {r: Counter() for r in RANKS}
    for name, lin in lineages.items():
        parts = lin.split(";")
        depths[len(parts)] += 1
        if not lin or set(lin) <= set(";"):
            empty += 1
        for i, part in enumerate(parts[: len(RANKS)]):
            label = part.strip()
            bare = label.split("__", 1)[-1] if "__" in label else label
            if is_unresolved(bare):
                placeholder[RANKS[i]] += 1
            else:
                members[RANKS[i]][";".join(parts[: i + 1])] += 1

    # The denominator is sequences with a real label at that rank, placeholders excluded, because a
    # placeholder is not a taxon one could have a sibling in. Reported alongside the percentage so
    # that it is never compared against a figure computed over a different base.
    judgeable, considered = {}, {}
    for r in RANKS:
        counts = members[r]
        total = sum(counts.values())
        with_sibling = sum(c for c in counts.values() if c >= 2)
        considered[r] = total
        judgeable[r] = round(100 * with_sibling / total, 1) if total else None

    shape = {
        "convention": args.convention,
        "n_sequences": len(lengths),
        "n_with_lineage": len(lineages),
        "length": {
            "min": vals[0], "p5": pct(0.05), "median": int(st.median(vals)),
            "p95": pct(0.95), "max": vals[-1],
            "p95_over_p5": round(pct(0.95) / pct(0.05), 2) if pct(0.05) else None,
        },
        "lineage_depths": dict(sorted(depths.items())),
        "empty_lineages": empty,
        "placeholder_by_rank": {r: placeholder[r] for r in RANKS},
        "judgeable_pct_of_labelled": judgeable,
        "judgeable_pct_of_all": {
            r: (round(100 * sum(c for c in members[r].values() if c >= 2) / len(lineages), 1)
                if lineages else None)
            for r in RANKS
        },
        "judgeable_denominator": considered,
        "n_taxa": {r: len(members[r]) for r in RANKS},
    }
    if args.out:
        Path(args.out).write_text(json.dumps(shape, indent=2))

    L = shape["length"]
    print(f"{shape['n_sequences']} sequences, {shape['n_with_lineage']} with a lineage")
    print(f"length: min {L['min']}, p5 {L['p5']}, median {L['median']}, p95 {L['p95']}, "
          f"max {L['max']}  -> p95/p5 = {L['p95_over_p5']}")
    print(f"lineage depths: {shape['lineage_depths']}, empty: {empty}")
    # Two percentages, because one of them alone is how 85.7 % got published: among sequences that
    # have a resolved label at the rank, and out of the whole dataset. The second is the ceiling a
    # recall figure has to be read against.
    print(f"{'rank':10}{'taxa':>8}{'labelled':>10}{'judg/labelled':>15}"
          f"{'judg/all':>10}{'unresolved':>12}")
    for r in RANKS:
        of_all = shape["judgeable_pct_of_all"][r]
        print(f"{r:10}{len(members[r]):>8}{considered[r]:>10}{str(judgeable[r]):>15}"
              f"{str(of_all):>10}{placeholder[r]:>12}")


if __name__ == "__main__":
    main()
