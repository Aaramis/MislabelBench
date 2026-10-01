#!/usr/bin/env python3
"""Relabel known sequences so detection can be scored against truth rather than against
agreement with another tool.

The design follows the protocol: a taxonomic distance, a rate, and k sequences sharing one
wrong label. k is the axis that matters most, because strict leave-one-out removes one
sequence at a time, so the k-1 others keep anchoring the placement onto the wrong label.

One rule is not negotiable and is enforced here: a donor taxon always keeps at least one
correctly labelled member. Without it the taxon disappears from the tree when the injected
sequences are removed, and we would be measuring a structural limit of leave-one-out rather
than the tool. --allow-empty-donor lifts it, for measuring that limit on purpose.
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def read_tax(path):
    tax = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        name, _, lineage = line.partition("\t")
        tax[name] = lineage.split(";")
    return tax


def main():
    p = argparse.ArgumentParser()
    p.add_argument("taxonomy")
    p.add_argument("--distance", required=True, choices=RANKS[1:],
                   help="rank at which the wrong label differs from the true one")
    p.add_argument("--rate", type=float, default=0.01, help="fraction of the database to relabel")
    p.add_argument("--k", type=int, default=1, help="sequences sharing one wrong label")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--prefix", default="injected")
    p.add_argument("--allow-empty-donor", action="store_true",
                   help="let a donor taxon lose every correct member")
    args = p.parse_args()

    tax = read_tax(args.taxonomy)
    if not tax:
        sys.exit(f"no entries in {args.taxonomy}")
    depth = len(next(iter(tax.values())))
    if any(len(v) != depth for v in tax.values()):
        sys.exit("ragged lineages: every entry must have the same number of ranks")

    r = RANKS.index(args.distance)          # recipient shares ranks[:r], differs at ranks[r]
    if r >= depth:
        sys.exit(f"--distance {args.distance} needs at least {r + 1} ranks, found {depth}")

    by_lineage = defaultdict(list)
    for name, ranks in tax.items():
        by_lineage[";".join(ranks)].append(name)

    # Candidate recipients, grouped by the prefix they must share with their donor.
    by_prefix = defaultdict(set)
    for lineage in by_lineage:
        by_prefix[";".join(lineage.split(";")[:r])].add(lineage)

    rng = random.Random(args.seed)
    need = max(1, round(args.rate * len(tax)))
    floor = args.k if args.allow_empty_donor else args.k + 1

    donors = sorted(l for l, m in by_lineage.items() if len(m) >= floor)
    rng.shuffle(donors)

    injected, used = {}, set()
    for donor in donors:
        if len(injected) >= need:
            break
        prefix = ";".join(donor.split(";")[:r])
        options = sorted(x for x in by_prefix[prefix]
                         if x.split(";")[r] != donor.split(";")[r])
        if not options:
            continue
        wrong = options[rng.randrange(len(options))]
        members = sorted(set(by_lineage[donor]) - used)
        if len(members) < floor:
            continue
        rng.shuffle(members)
        for name in members[:args.k]:
            injected[name] = {"true": donor, "wrong": wrong, "donor_group": donor}
            used.add(name)

    if len(injected) < need:
        print(f"warning: asked for {need}, injected {len(injected)}; "
              f"not enough taxa with >= {floor} members at distance {args.distance}",
              file=sys.stderr)

    out_tax = Path(f"{args.prefix}.tax")
    with out_tax.open("w") as fh:
        for name, ranks in tax.items():
            lineage = injected[name]["wrong"] if name in injected else ";".join(ranks)
            fh.write(f"{name}\t{lineage}\n")

    truth = {
        "source": str(args.taxonomy),
        "distance": args.distance,
        "rate": args.rate,
        "k": args.k,
        "seed": args.seed,
        "allow_empty_donor": args.allow_empty_donor,
        "n_total": len(tax),
        "n_injected": len(injected),
        "injected": injected,
    }
    Path(f"{args.prefix}.truth.json").write_text(json.dumps(truth, indent=2))
    print(f"{len(injected)} of {len(tax)} relabelled at {args.distance} distance, k={args.k}")


if __name__ == "__main__":
    main()
