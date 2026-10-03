#!/usr/bin/env python3
"""What a dataset looks like before anything is aligned, and whether leave-one-out can judge it.

Written for UNITE RepS, where the open question is the alignment, and useful for any unaligned
reference. Two things decide whether the dataset is usable at all, and neither needs an aligner:

Length spread. ITS is not 16S: it has no conserved secondary structure to align against, and the
argument about which aligner to trust is really an argument about how much of the result is gap.
The ratio of the 95th to the 5th percentile length says how bad that is in one number.

Judgeability. Leave-one-out removes a sequence and places it back, so it needs another sequence
carrying the same label. A taxon with one member cannot be judged at that rank at all. The
fraction of sequences whose taxon has at least one other member is therefore a ceiling on recall
that is a property of the database and not of either tool.

Also counted: how many lineages are ragged or carry placeholder ranks, because an all-placeholder
lineage collapses to the empty string and that is a parsing question the pipeline has already met.
"""

import argparse
import json
import statistics as st
from collections import Counter
from pathlib import Path

RANKS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]


def read_fasta_lengths(path):
    lengths, name, n = {}, None, 0
    for line in Path(path).open(errors="replace"):
        if line.startswith(">"):
            name = line[1:].split()[0]
            lengths[name] = 0
            n += 1
        elif name is not None:
            lengths[name] += len(line.strip())
    return lengths


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fasta", required=True)
    p.add_argument("--tax", required=True)
    p.add_argument("--out", default="shape.json")
    args = p.parse_args()

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
            # UNITE marks an unidentified rank as x__ with nothing after it, or as
            # "x__unidentified"; both are a label that cannot be judged against.
            if len(label) <= 3 or label.endswith("__unidentified"):
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
        "judgeable_pct": judgeable,
        "judgeable_denominator": considered,
        "n_taxa": {r: len(members[r]) for r in RANKS},
    }
    Path(args.out).write_text(json.dumps(shape, indent=2))

    L = shape["length"]
    print(f"{shape['n_sequences']} sequences, {shape['n_with_lineage']} with a lineage")
    print(f"length: min {L['min']}, p5 {L['p5']}, median {L['median']}, p95 {L['p95']}, "
          f"max {L['max']}  -> p95/p5 = {L['p95_over_p5']}")
    print(f"lineage depths: {shape['lineage_depths']}, empty: {empty}")
    print(f"{'rank':10}{'taxa':>8}{'labelled':>10}{'judgeable %':>13}{'placeholders':>14}")
    for r in RANKS:
        print(f"{r:10}{len(members[r]):>8}{considered[r]:>10}"
              f"{str(judgeable[r]):>13}{placeholder[r]:>14}")


if __name__ == "__main__":
    main()
