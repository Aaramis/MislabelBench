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
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def check_aligned(seqs, path, allow_ragged):
    """Every consumer of this output assumes a fixed-width alignment.

    The source directory holds both gtdb_arc1200.fasta, which is ragged because it comes straight
    out of the release, and gtdb_arc1200.aligned.fasta. Subsetting the first one produces a file
    that looks right, loads fine, and silently gives SATIVA unaligned sequences. That happened
    once; it is now refused.
    """
    widths = {len(v) for v in seqs.values()}
    if len(widths) == 1:
        return
    lo, hi = min(widths), max(widths)
    message = (f"{path} is not an alignment: lengths run from {lo} to {hi}. "
               "Subsetting it gives unaligned sequences to a tool that expects an alignment. "
               "Pass the aligned file, or --allow-ragged if that is really what you want.")
    if not allow_ragged:
        sys.exit(message)
    print(f"warning: {message}", file=sys.stderr)


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
    p.add_argument("--allow-ragged", action="store_true",
                   help="accept an input whose sequences are not all the same length")
    p.add_argument("--min-group", type=int, default=1,
                   help="only draw taxa with at least this many members. The default of 1 "
                        "keeps the subset representative; raising it builds a deliberately "
                        "easier set where every sequence has a sibling")
    args = p.parse_args()

    tax = read_tax(args.taxonomy)
    seqs = read_fasta(args.fasta)
    check_aligned(seqs, args.fasta, args.allow_ragged)
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
        # Each input's name and digest rather than the path it was read from, which is the same
        # correction inject_mislabels.py carries for truth.json and which was left undone here. The
        # path is whatever the caller typed, so the committed record for gtdb_arc2k reads
        # "gtdb_arc1200.tax" because it was made from inside data/gtdb, and rebuilding it from the
        # repository root produced "data/gtdb/gtdb_arc1200.tax" -- a record that cannot reproduce
        # unless the next person happens to stand in the same directory. The digest also makes the
        # record say which file, not just which name: every injected cell's truth.json already
        # carries the .tax sha256 this one now agrees with.
        "source_fasta": Path(args.fasta).name,
        "source_fasta_sha256": hashlib.sha256(Path(args.fasta).read_bytes()).hexdigest(),
        "source_taxonomy": Path(args.taxonomy).name,
        "source_taxonomy_sha256": hashlib.sha256(Path(args.taxonomy).read_bytes()).hexdigest(),
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
