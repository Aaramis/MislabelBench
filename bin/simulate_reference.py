#!/usr/bin/env python3
"""Sanity check on simulated data: a reference where every label is certain by construction.

Injection is the primary source of truth and leaves one hole in itself, which 2.1 and 2.4 both
name: the sequences we did not touch are only assumed correct, because real references contain
real errors. Simulation closes that hole and opens another. Here the taxonomy is the tree, so a
label cannot be wrong unless we made it wrong, and a flag on an untouched sequence is a false
positive in the strict sense that the injected grid can never offer. The cost is that the data is
as regular as the model that made it, which is why 2.1 calls this a control and not a second set of
results.

**Why this is forty lines of python and not another pinned container.** Every tool in this
benchmark is pinned by container and build string (2.7), and that is right for tools whose
behaviour we are measuring. A simulator is not one of those: what matters is that it is
deterministic, that the model is stated, and that a reader can check it. Jukes-Cantor along a tree
is short enough to read, so it is here rather than behind a version string.

The tree is the taxonomy. Branching at each rank with a branch length per level, longer towards
the root, so species are tight and phyla far apart -- the shape that makes mislabel detection
possible at all. Sites evolve independently under Jukes-Cantor: over a branch of length d, a site
changes with probability 3/4 (1 - exp(-4d/3)) and then picks one of the other three bases.

No gaps are produced. A simulated alignment is aligned by construction, which is the one
simplification worth naming up front: it removes the alignment from the question entirely, and
the caveat on the foreign-sequence error type is precisely about what the alignment carries.
"""

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]
BASES = "ACGT"


def evolve(seq, d, rng):
    """One branch of length d under Jukes-Cantor."""
    p = 0.75 * (1.0 - math.exp(-4.0 * d / 3.0))
    out = list(seq)
    for i, b in enumerate(out):
        if rng.random() < p:
            out[i] = rng.choice([x for x in BASES if x != b])
    return "".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--branching", default="3,2,2,2,2,3",
                   help="splits at phylum,class,order,family,genus,species")
    p.add_argument("--per-species", type=int, default=3)
    p.add_argument("--length", type=int, default=1478, help="sites; the archaeal alignment's width")
    p.add_argument("--rates", default="0.30,0.15,0.08,0.04,0.02,0.010,0.004",
                   help="branch length at each level, root first, then the within-species tip")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--prefix", required=True)
    args = p.parse_args()

    branching = [int(x) for x in args.branching.split(",")]
    rates = [float(x) for x in args.rates.split(",")]
    if len(branching) != 6:
        raise SystemExit("--branching needs six values, phylum through species")
    if len(rates) != 7:
        raise SystemExit("--rates needs seven values, six ranks plus the within-species branch")

    rng = random.Random(args.seed)
    root = "".join(rng.choice(BASES) for _ in range(args.length))

    # Descend the taxonomy, evolving along each edge. The label is built as we go, so it cannot
    # disagree with the topology: there is one path from the root to any sequence.
    seqs, tax, newick_tips = {}, {}, []
    level = [(["d__sim"], root)]
    for depth, splits in enumerate(branching):
        nxt = []
        for labels, seq in level:
            for i in range(splits):
                name = f"{RANKS[depth + 1][0]}__{labels[-1].split('__')[-1]}_{i}" \
                    if depth else f"p__{i}"
                child = evolve(seq, rates[depth], rng)
                nxt.append((labels + [name], child))
        level = nxt
    for labels, seq in level:
        for j in range(args.per_species):
            # The species label already encodes the whole path, so the id needs only it.
            sid = f"sim_{labels[-1].split('__')[-1]}_{j}"
            seqs[sid] = evolve(seq, rates[6], rng)
            tax[sid] = ";".join(labels)
            newick_tips.append(sid)

    Path(f"{args.prefix}.fasta").write_text(
        "".join(f">{n}\n{seqs[n]}\n" for n in sorted(seqs)))
    Path(f"{args.prefix}.tax").write_text(
        "".join(f"{n}\t{tax[n]}\n" for n in sorted(tax)))

    groups = len(level)
    Path(f"{args.prefix}.sim.json").write_text(json.dumps({
        "model": "Jukes-Cantor, sites independent, no indels",
        "branching": branching,
        "rates": rates,
        "per_species": args.per_species,
        "length": args.length,
        "seed": args.seed,
        "n_species": groups,
        "n_sequences": len(seqs),
        # The claim this control exists to support: nothing here is wrong unless injected.
        "labels_certain": True,
        "fasta_sha256": hashlib.sha256(Path(f"{args.prefix}.fasta").read_bytes()).hexdigest(),
        "tax_sha256": hashlib.sha256(Path(f"{args.prefix}.tax").read_bytes()).hexdigest(),
    }, indent=2))

    print(f"{len(seqs)} sequences of {args.length} sites, {groups} species, "
          f"{args.per_species} per species, seed {args.seed}")


if __name__ == "__main__":
    main()
