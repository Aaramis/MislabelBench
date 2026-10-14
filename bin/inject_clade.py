#!/usr/bin/env python3
"""Error kind 3: relabel a whole taxon, so nothing correctly labelled remains to confirm it.

The protocol keeps kind 3 as a case to characterise rather than to score like kinds 1 and 2,
and says why: with every member of a taxon relabelled, leave-one-out has nothing to place the
removed sequence against, so the taxon cannot be confirmed. The clade is still placed, though, and
if its own signal points elsewhere then every member lands away from where its new label says it
belongs. So detection does not disappear -- it moves from "is this label contradicted by its
relatives" to "is this clade distinguishable from the taxon it has been assigned to".

**That is what is varied here.** The protocol says the
cells have to vary compactness and not just distance. Compactness is measured against the recipient
rather than against the whole database, because that is the comparison the question is about:

    within      mean pairwise identity among the clade's members
    recipient   mean identity from those members to the members of the taxon whose label they get
    separation  within - recipient, so a high value is a clade that can anchor itself

Measured on the alignment, over columns where both sequences have a base, which is the same rule
bin/cluster_conflict.py uses. All-against-all would be 3 billion character comparisons in pure
python; against the recipient alone it is a few hundred pairs and is the quantity in the hypothesis.

The hard case the protocol names -- "a wrong label inside the correct genus" -- is `--distance
species`, where the clade keeps its genus and is given a sibling species. The easy end is
`--distance phylum`.

The donor-survivor rule that bin/inject_mislabels.py enforces is lifted here by construction. That
is the point of the kind and not an oversight, which is why this is a separate script: the rule is
not negotiable there and must not be made so.
"""

import argparse
import hashlib
import json
import random
import statistics as st
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]
BASES = set("ACGTacgt")


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


def identity(a, b):
    same = tot = 0
    for x, y in zip(a, b):
        if x in BASES and y in BASES:
            tot += 1
            same += x.upper() == y.upper()
    return same / tot if tot else 0.0


def mean_identity(aln, xs, ys=None):
    """Within a set if ys is None, else between the two sets."""
    pairs = combinations(xs, 2) if ys is None else ((x, y) for x in xs for y in ys)
    vals = [identity(aln[x], aln[y]) for x, y in pairs]
    return st.mean(vals) if vals else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("taxonomy")
    p.add_argument("--alignment", required=True, help="fixed-width, for the compactness measure")
    p.add_argument("--distance", required=True, choices=RANKS[1:])
    p.add_argument("--n-clades", type=int, default=6)
    p.add_argument("--min-size", type=int, default=3)
    p.add_argument("--max-size", type=int, default=8)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--prefix", required=True)
    args = p.parse_args()

    tax = {}
    for line in Path(args.taxonomy).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            tax[name] = lineage.split(";")
    if not tax:
        sys.exit(f"no entries in {args.taxonomy}")
    depth = len(next(iter(tax.values())))
    if any(len(v) != depth for v in tax.values()):
        sys.exit("ragged lineages: every entry must have the same number of ranks")

    r = RANKS.index(args.distance)
    if r >= depth:
        sys.exit(f"--distance {args.distance} needs at least {r + 1} ranks, found {depth}")

    aln = read_fasta(args.alignment)
    widths = {len(v) for v in aln.values()}
    if len(widths) != 1:
        sys.exit(f"{args.alignment} is not an alignment: widths {min(widths)} to {max(widths)}")
    missing = set(tax) - set(aln)
    if missing:
        sys.exit(f"{len(missing)} taxonomy entries have no sequence, e.g. {sorted(missing)[0]}")

    by_lineage = defaultdict(list)
    for name, ranks in tax.items():
        by_lineage[";".join(ranks)].append(name)
    by_prefix = defaultdict(set)
    for lineage in by_lineage:
        by_prefix[";".join(lineage.split(";")[:r])].add(lineage)

    rng = random.Random(args.seed)

    # Every taxon that could be relabelled whole, with its separation from the recipient it would
    # be given. The recipient is drawn here rather than later because separation depends on it.
    candidates = []
    for donor in sorted(l for l, m in by_lineage.items()
                        if args.min_size <= len(m) <= args.max_size):
        prefix = ";".join(donor.split(";")[:r])
        options = sorted(x for x in by_prefix[prefix]
                         if x.split(";")[r] != donor.split(";")[r])
        if not options:
            continue
        wrong = options[rng.randrange(len(options))]
        members, recipients = sorted(by_lineage[donor]), sorted(by_lineage[wrong])
        within = mean_identity(aln, members)
        to_recipient = mean_identity(aln, members, recipients)
        if within is None or to_recipient is None:
            continue
        candidates.append({"clade": donor, "wrong": wrong, "members": members,
                           "size": len(members), "recipient_size": len(recipients),
                           "within": round(within, 4), "to_recipient": round(to_recipient, 4),
                           "separation": round(within - to_recipient, 4)})

    if len(candidates) < args.n_clades:
        sys.exit(f"only {len(candidates)} taxa of {args.min_size}-{args.max_size} members have a "
                 f"recipient at {args.distance}; asked for {args.n_clades}")

    # Spread over the separation range rather than drawn at random, because the range is the
    # variable: a sample of six from 145 candidates would cluster wherever the mass is.
    candidates.sort(key=lambda c: c["separation"])
    step = (len(candidates) - 1) / (args.n_clades - 1) if args.n_clades > 1 else 0
    picked = [candidates[round(i * step)] for i in range(args.n_clades)]

    injected = {}
    for c in picked:
        for name in c["members"]:
            injected[name] = {"true": c["clade"], "wrong": c["wrong"], "donor_group": c["clade"]}

    out_tax = Path(f"{args.prefix}.tax")
    with out_tax.open("w") as fh:
        for name in sorted(tax):
            lineage = injected[name]["wrong"] if name in injected else ";".join(tax[name])
            fh.write(f"{name}\t{lineage}\n")

    Path(f"{args.prefix}.truth.json").write_text(json.dumps({
        "kind": "whole_clade",
        "source": Path(args.taxonomy).name,
        "source_sha256": hashlib.sha256(Path(args.taxonomy).read_bytes()).hexdigest(),
        "alignment": Path(args.alignment).name,
        "distance": args.distance,
        "seed": args.seed,
        # No k: a clade is relabelled whole, so the count is its size and it varies between clades.
        "k": None,
        "n_clades": len(picked),
        "n_candidates": len(candidates),
        "n_total": len(tax),
        "n_injected": len(injected),
        "clades": [{k: v for k, v in c.items() if k != "members"} for c in picked],
        "injected": injected,
    }, indent=2))

    print(f"{len(picked)} whole clades relabelled at {args.distance}, {len(injected)} sequences, "
          f"separation {picked[0]['separation']:+.4f} to {picked[-1]['separation']:+.4f}")
    for c in picked:
        print(f"  {c['size']:2} seqs  within {c['within']:.4f}  recipient {c['to_recipient']:.4f}  "
              f"separation {c['separation']:+.4f}  {c['clade'].split(';')[-1][:44]}")


if __name__ == "__main__":
    main()
