#!/usr/bin/env python3
"""What a dataset looks like before anything is aligned, and whether leave-one-out can judge it.

One tool for every dataset here, so that the judgeability table in the protocol is computed one way
rather than per dataset. What differs between references is only how they write an unresolved rank,
which --convention selects. Two things decide whether the dataset is usable at all, and neither needs an aligner:

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
import re
import statistics as st
from collections import Counter
from pathlib import Path

RANKS_UNITE = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
RANKS_GTDB = ["domain", "phylum", "class", "order", "family", "genus", "species"]

# What counts as a label one cannot have a sibling in, taken from the full inventory of label forms
# in UNITE v10.0 RepS. One family of forms per rank, and it took three passes to get right, so the
# counts are written down here as the thing any change has to still reproduce:
#
#   phylum   1846   Ascomycota_phy_Incertae_sedis
#   class    7737   ..._cls_Incertae_sedis            + 91 bare GS codes
#   order   10469   ..._ord_Incertae_sedis            + 863 bare GS codes
#   family  23016   ..._fam_Incertae_sedis
#   genus   31482   Ascomycota_gen_Incertae_sedis
#   species 62129   Cortinarius_sp, and Fungi_sp, which is a kingdom standing in for a species
#
# "_spathulata" and "_sporotrichioides" are real species, so the species test is the whole final
# token and not a substring. The first pass tested `len(label) <= 3 or endswith __unidentified`,
# found nothing at any rank, and that is how a judgeability of 85.7 % at species came to be
# published for a dataset where three sequences in four have no species name. The second pass
# caught the bare forms and missed Ascomycota_gen_Incertae_sedis, which is the common one.
UNRESOLVED_UNITE = re.compile(
    r"^(?:Incertae_sedis|GS\d+|unidentified|unclassified)$"
    r"|_(?:phy|cls|ord|fam|gen|sp)_Incertae_sedis$",
    re.I,
)

# GTDB has nothing of the kind, which was checked rather than assumed: in gtdb_arc2k and
# gtdb_arc1200 every lineage is seven ranks deep, no rank is empty, and no label is a catch-all.
# Its unnamed species are written per cluster -- s__JAJYEA01 sp021809545, 595 such labels over 1235
# sequences at 2023, the largest holding 32 -- so two sequences sharing one are conspecific by
# GTDB's own definition and the sibling relation is real. That is the opposite of UNITE's
# Cortinarius_sp, which 62129 sequences share and which asserts nothing.
UNRESOLVED_GTDB = re.compile(r"^(?:sp|unidentified|unclassified|Incertae_sedis)$", re.I)

CONVENTIONS = {
    "unite": (RANKS_UNITE, UNRESOLVED_UNITE, True),
    "gtdb": (RANKS_GTDB, UNRESOLVED_GTDB, False),
}


def make_is_unresolved(pattern, tail_test):
    def is_unresolved(label):
        """label is the part after the x__ prefix."""
        if not label:
            return True
        if pattern.search(label):
            return True
        # UNITE writes Cortinarius_sp and Fungi_sp, so the final token alone, which leaves
        # _spathulata and _sporotrichioides standing. GTDB needs no such test.
        if tail_test:
            return label.rsplit("_", 1)[-1].lower() in ("sp", "unidentified", "unclassified")
        return False
    return is_unresolved


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
    p.add_argument("--convention", default="unite", choices=sorted(CONVENTIONS),
                   help="how this reference writes an unresolved rank")
    p.add_argument("--out", help="write the record here; without it the table above is the output")
    args = p.parse_args()

    RANKS, pattern, tail_test = CONVENTIONS[args.convention]
    is_unresolved = make_is_unresolved(pattern, tail_test)

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
