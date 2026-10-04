#!/usr/bin/env python3
"""Error kind 6: a sequence whose true position is far outside its declared clade.

A. Stamatakis's construction. Take sequences from a bacterial phylum, add them to the archaeal
database, and give each one the lineage of a real archaeal species. The declared label is
plausible, the sequence is not, and placement should put it on a long branch far from where its
label says it belongs. Unlike a relabelling, the truth here is not a judgement about the base:
a bacterium under an archaeal label is wrong by construction.

The donors are *added*, not substituted, so the base database is untouched and the baseline flag
set stays comparable.

The target species is drawn per donor, and by default with replacement, which does NOT make this the
isolated case -- the claim this docstring used to make. 7051 sequences carry 3067 distinct species
lineages, so drawing target *sequences* independently collides on the *label* far more often than a
birthday estimate over sequences suggests: across the nine committed cells 94 of 393 donors share
their archaeal label with another donor, 19 of 101 in the densest. Those donors are kind 2 crossed
with this one, by accident, and that is where the whole of kind 6's miss rate lives -- 299 of 299
isolated donors are detected by both tools and every one of the fork's 20 misses is a donor whose
label is shared. --distinct-labels draws distinct lineages and gives the construction described here;
the default is left as it was so the committed cells reproduce from this file. Either way the
sharing is counted into truth.json, so a recall figure can no longer be read without it.

Both alignments must come from the same covariance model with --matchonly, which emits exactly
the model's match columns, so the two files have the same width and concatenate directly. That
is asserted rather than assumed.
"""

import argparse
import json
import random
from collections import Counter
from pathlib import Path


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
    return dict(l.split("\t", 1) for l in Path(path).read_text().splitlines() if l.strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-fasta", required=True)
    p.add_argument("--base-tax", required=True)
    p.add_argument("--donor-fasta", required=True)
    p.add_argument("--donor-tax", required=True)
    p.add_argument("--n", type=int, required=True, help="number of foreign sequences to add")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--prefix", required=True)
    p.add_argument("--distinct-labels", action="store_true",
                   help="one archaeal label per donor, the genuinely isolated case")
    args = p.parse_args()

    base_seq, base_tax = read_fasta(args.base_fasta), read_tax(args.base_tax)
    donor_seq, donor_tax = read_fasta(args.donor_fasta), read_tax(args.donor_tax)

    widths = {len(s) for s in base_seq.values()} | {len(s) for s in donor_seq.values()}
    if len(widths) != 1:
        raise SystemExit(f"alignment widths differ: {sorted(widths)}; "
                         "both files must come from the same model with --matchonly")

    rng = random.Random(args.seed)
    donors = rng.sample(sorted(set(donor_seq) & set(donor_tax)), args.n)
    if args.distinct_labels:
        first = {}
        for n, lineage in sorted(base_tax.items()):
            first.setdefault(lineage, n)
        targets = [first[l] for l in rng.sample(sorted(first), args.n)]
    else:
        targets = rng.choices(sorted(base_tax), k=args.n)

    injected = {}
    out_fa = [f">{n}\n{base_seq[n]}\n" for n in sorted(base_seq)]
    out_tx = [f"{n}\t{base_tax[n]}\n" for n in sorted(base_tax)]
    for donor, target in zip(donors, targets):
        label = base_tax[target]
        out_fa.append(f">{donor}\n{donor_seq[donor]}\n")
        out_tx.append(f"{donor}\t{label}\n")
        injected[donor] = {"true": donor_tax[donor], "wrong": label, "target_sequence": target}

    groups = Counter(r["wrong"] for r in injected.values())
    n_shared = sum(v for v in groups.values() if v > 1)
    sizes = Counter(groups.values())

    Path(f"{args.prefix}.fasta").write_text("".join(out_fa))
    Path(f"{args.prefix}.tax").write_text("".join(out_tx))
    Path(f"{args.prefix}.truth.json").write_text(json.dumps({
        "kind": "foreign",
        "distance": "domain",
        "seed": args.seed,
        "rate": round(args.n / len(base_tax), 6),
        "base_sequences": len(base_tax),
        "n_injected": args.n,
        "distinct_labels": args.distinct_labels,
        # Donors sharing an archaeal label with another donor, and the group sizes. Without this a
        # recall figure for this cell reads as a figure about foreign sequences when part of it is
        # about shared mislabels.
        "n_shared_label_donors": n_shared,
        "label_group_sizes": {str(k): v for k, v in sorted(sizes.items())},
        "injected": injected,
    }, indent=2))
    print(f"{args.n} foreign sequences added to {len(base_tax)}, "
          f"alignment width {widths.pop()}, {n_shared} sharing a label")


if __name__ == "__main__":
    main()
