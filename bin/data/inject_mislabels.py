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
import hashlib
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

    # No bookkeeping of which sequences are already taken, because there is nothing to keep: a
    # sequence belongs to exactly one lineage and each lineage appears once in `donors`, so two
    # groups can never compete for the same member. This loop used to subtract a `used` set and
    # re-test `floor` afterwards, which read as protection against an overlap that cannot occur.
    # Checked over 60 combinations of k, rate and seed on the 2 023-sequence set: neither the
    # subtraction nor the re-test ever changed anything.
    injected = {}
    for donor in donors:
        if len(injected) >= need:
            break
        prefix = ";".join(donor.split(";")[:r])
        options = sorted(x for x in by_prefix[prefix]
                         if x.split(";")[r] != donor.split(";")[r])
        if not options:
            continue
        wrong = options[rng.randrange(len(options))]
        members = sorted(by_lineage[donor])
        rng.shuffle(members)
        for name in members[:args.k]:
            injected[name] = {"true": donor, "wrong": wrong, "donor_group": donor}

    if len(injected) < need:
        print(f"warning: asked for {need}, injected {len(injected)}; "
              f"not enough taxa with >= {floor} members at distance {args.distance}",
              file=sys.stderr)
    elif len(injected) > need:
        # The loop breaks after a group has pushed the count to or past `need`, so the last group
        # always completes and the overshoot is up to k-1 sequences. That is the right semantics --
        # k sequences sharing one wrong label is what k means, and a partial group would be a
        # different experiment -- but it was silent, and the protocol says cells are "dropped rather
        # than silently rounded". At k=10 and rate 0.05 on 2023 sequences it means 110 injections
        # where 101 were asked, an effective rate of 5.44% against 5.00%. Averaged over the grid the
        # effective rate rises with k: 2.99% at k=1 to 3.21% at k=10, which is a covariate on the
        # axis the main result is measured along, small and in the direction that makes high k
        # harder rather than easier.
        print(f"note: asked for {need}, injected {len(injected)} -- whole groups of k={args.k}, "
              f"so the effective rate is {100 * len(injected) / len(tax):.2f}% "
              f"against {100 * args.rate:.2f}% requested", file=sys.stderr)

    out_tax = Path(f"{args.prefix}.tax")
    with out_tax.open("w") as fh:
        for name, ranks in tax.items():
            lineage = injected[name]["wrong"] if name in injected else ";".join(ranks)
            fh.write(f"{name}\t{lineage}\n")

    truth = {
        # The input's name and digest rather than the path it was read from. An absolute path makes
        # the record differ between two machines that produced the same cell, and names a file
        # without identifying it. Everything else here is already machine-independent: the 180
        # cells regenerate byte for byte from their seed, checked on macOS against Linux.
        "source": Path(args.taxonomy).name,
        "source_sha256": hashlib.sha256(Path(args.taxonomy).read_bytes()).hexdigest(),
        "distance": args.distance,
        "rate": args.rate,
        # What was asked and what whole groups of k could deliver. The second is the one a recall
        # figure is a fraction of, and it is not the first.
        "n_requested": need,
        "rate_effective": round(len(injected) / len(tax), 6),
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
