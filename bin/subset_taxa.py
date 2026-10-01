#!/usr/bin/env python3
"""Cut a dataset down by taking whole taxa, never part of one.

The injection grid cannot run on the full set: upstream SATIVA takes about 50 minutes on
7051 sequences, and the grid is hundreds of cells. It runs on a subset instead, and the
headline numbers stay on the full set.

Sampling sequences at random would break the thing the benchmark depends on. Leave-one-out
needs a sequence to have at least one sibling in its taxon, so removing half the members of a
species turns judgeable sequences into unjudgeable ones and the subset stops resembling the
set it came from. So this draws whole species groups until it reaches the target, and reports
the judgeability of both so the subset can be checked against the set it came from.
"""

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def read_tax(path):
    tax = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            tax[name] = lineage
    return tax


def read_fasta(path):
    seqs, name, chunks = {}, None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith(">"):
            if name:
                seqs[name] = "".join(chunks)
            name, chunks = line[1:].strip(), []
        else:
            chunks.append(line.strip())
    if name:
        seqs[name] = "".join(chunks)
    return seqs


def judgeable(lineages):
    out = {}
    for lvl, rank in enumerate(RANKS):
        c = Counter(";".join(l.split(";")[:lvl + 1]) for l in lineages)
        out[rank] = round(100 * sum(v for v in c.values() if v >= 2) / len(lineages), 1)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fasta")
    p.add_argument("taxonomy")
    p.add_argument("--target", type=int, required=True, help="approximate number of sequences")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--prefix", required=True)
    p.add_argument("--min-group", type=int, default=1,
                   help="only draw taxa with at least this many members. The default of 1 "
                        "keeps the subset representative; raising it builds a deliberately "
                        "easier set where every sequence has a sibling")
    args = p.parse_args()

    tax = read_tax(args.taxonomy)
    seqs = read_fasta(args.fasta)
    missing = set(tax) - set(seqs)
    if missing:
        sys.exit(f"{len(missing)} names in the taxonomy are absent from the alignment")

    groups = defaultdict(list)
    for name, lineage in tax.items():
        groups[lineage].append(name)

    # Draw taxa without preferring the ones that have siblings. Preferring them was the first
    # attempt and it produced a subset judgeable at 100 % against a source at 72.7 %, which
    # measures an easier problem than the real database poses. Taking groups as they come
    # reproduces the source profile to within a few points.
    eligible = sorted(g for g, m in groups.items() if len(m) >= args.min_group)
    singletons = sorted(g for g, m in groups.items() if len(m) < args.min_group)

    rng = random.Random(args.seed)
    rng.shuffle(eligible)
    rng.shuffle(singletons)

    chosen, taken = [], 0
    for g in eligible + singletons:
        if taken >= args.target:
            break
        chosen.append(g)
        taken += len(groups[g])

    names = sorted(n for g in chosen for n in groups[g])
    lineages = [tax[n] for n in names]

    with open(f"{args.prefix}.fasta", "w") as fh:
        for n in names:
            fh.write(f">{n}\n{seqs[n]}\n")
    with open(f"{args.prefix}.tax", "w") as fh:
        for n in names:
            fh.write(f"{n}\t{tax[n]}\n")

    report = {
        "source_fasta": args.fasta,
        "source_taxonomy": args.taxonomy,
        "seed": args.seed,
        "target": args.target,
        "n_source": len(tax),
        "n_subset": len(names),
        "n_taxa_source": len(groups),
        "n_taxa_subset": len(chosen),
        "judgeable_source": judgeable(list(tax.values())),
        "judgeable_subset": judgeable(lineages),
    }
    Path(f"{args.prefix}.subset.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
