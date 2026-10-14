#!/usr/bin/env python3
"""Error kind 7: a chimera of two real sequences, carrying the label of one of them.

A. Stamatakis's answer to "is there another type of error we have missed": chimeric sequences. A
chimera's position in the tree is split between two lineages, so its label is only half correct,
and what a leave-one-out placement makes of it depends on where the breakpoint falls and how far
apart the two parents are. Those are the two axes here.

Construction. Parent A is drawn from the base; parent B is a sequence whose lineage agrees with A's
above the chosen rank and differs at it, the same relation inject_mislabels.py uses for a wrong
label. The chimera is A's aligned columns up to the breakpoint and B's after it, so it has the
alignment's width and needs no realignment; the breakpoint is a fraction of A's ungapped length,
because a fraction of the gapped width would fall at different points of the molecule for sequences
with different gap patterns. It is added under A's lineage and a new id; both parents stay in the
reference, so the base is untouched and the baseline flag set stays comparable, as with kind 6.

Truth records both parents, their lineages, the rank they differ at and the breakpoint column. The
label the chimera carries is A's, so "wrong" is A's lineage and "true" is A's lineage too: the error
here is not that the label names the wrong taxon but that half the molecule is from another one.
bin/analysis/score_injection.py reports detection for this kind, as for kind 6, plus whether the proposed
lineage sides with the unlabelled parent.
"""

import argparse
import json
import random
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def read_fasta(path):
    seqs, name = {}, None
    for line in Path(path).read_text().splitlines():
        if line.startswith(">"):
            name = line[1:].split()[0]
            seqs[name] = []
        elif name:
            seqs[name].append(line.strip())
    return {k: "".join(v) for k, v in seqs.items()}


def read_tax(path):
    return dict(line.split("\t", 1) for line in Path(path).read_text().splitlines() if line.strip())


def breakpoint_column(seq, fraction):
    """The aligned column at which `fraction` of the ungapped residues have been seen."""
    residues = sum(1 for c in seq if c != "-")
    target = max(1, round(fraction * residues))
    seen = 0
    for i, c in enumerate(seq):
        if c != "-":
            seen += 1
            if seen == target:
                return i + 1
    return len(seq)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-fasta", required=True)
    p.add_argument("--base-tax", required=True)
    p.add_argument("--distance", required=True, choices=RANKS[1:],
                   help="rank at which the two parents' lineages differ")
    p.add_argument("--breakpoint", type=float, required=True,
                   help="fraction of parent A's ungapped length taken from A")
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--prefix", required=True)
    args = p.parse_args()
    if not 0 < args.breakpoint < 1:
        raise SystemExit("--breakpoint must be strictly between 0 and 1")

    seqs, tax = read_fasta(args.base_fasta), read_tax(args.base_tax)
    widths = {len(s) for s in seqs.values()}
    if len(widths) != 1:
        raise SystemExit(f"ragged alignment: widths {sorted(widths)[:5]}")
    r = RANKS.index(args.distance)

    # Candidates for B, grouped by what they share with A above the rank.
    by_prefix = {}
    for name, lineage in tax.items():
        if name in seqs:
            by_prefix.setdefault(";".join(lineage.split(";")[:r]), []).append(name)

    rng = random.Random(args.seed)
    names = sorted(set(seqs) & set(tax))
    rng.shuffle(names)
    injected, out_fa, out_tx = {}, [], []
    for a in names:
        if len(injected) >= args.n:
            break
        parts = tax[a].split(";")
        others = [b for b in by_prefix.get(";".join(parts[:r]), [])
                  if tax[b].split(";")[r] != parts[r]]
        if not others:
            continue
        b = others[rng.randrange(len(others))]
        col = breakpoint_column(seqs[a], args.breakpoint)
        cid = f"chimera_{len(injected) + 1:03d}"
        out_fa.append(f">{cid}\n{seqs[a][:col] + seqs[b][col:]}\n")
        out_tx.append(f"{cid}\t{tax[a]}\n")
        injected[cid] = {"true": tax[a], "wrong": tax[a], "parent_a": a, "parent_b": b,
                         "lineage_a": tax[a], "lineage_b": tax[b], "breakpoint_column": col}
    if len(injected) < args.n:
        raise SystemExit(f"only {len(injected)} of {args.n} chimeras have a parent at "
                         f"{args.distance} distance")

    Path(f"{args.prefix}.fasta").write_text(
        "".join(f">{n}\n{seqs[n]}\n" for n in sorted(seqs)) + "".join(out_fa))
    Path(f"{args.prefix}.tax").write_text(
        "".join(f"{n}\t{tax[n]}\n" for n in sorted(tax)) + "".join(out_tx))
    Path(f"{args.prefix}.truth.json").write_text(json.dumps({
        "kind": "chimera",
        "distance": args.distance,
        "breakpoint": args.breakpoint,
        "seed": args.seed,
        "rate": round(args.n / len(tax), 6),
        "base_sequences": len(tax),
        "n_total": len(tax),
        "n_injected": len(injected),
        "injected": injected,
    }, indent=2))
    print(f"{len(injected)} chimeras at {args.distance} distance, breakpoint {args.breakpoint} "
          f"of the ungapped length, added to {len(tax)} sequences of width {widths.pop()}")


if __name__ == "__main__":
    main()
