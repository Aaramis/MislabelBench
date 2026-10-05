#!/usr/bin/env python3
"""Cut a small self-contained case out of a reference: one sequence, one wrong label.

The grid finds sequences the fork flags and upstream misses, but each lives in a 2023-sequence
alignment with 102 other injected labels, which is not something anyone can read or send on. This
builds the same situation at a size a person can inspect: one clade kept around the sequence, one
label changed, every all-gap column dropped.

Nothing random. Within a family the target comes first, then its own genus, then the rest by name,
so --per-family is a knob that shrinks the case without changing which sequences a smaller case
keeps. That matters because the case is found by shrinking until the divergence stops reproducing,
and a seeded sample would make each step a different experiment.
"""

import argparse
import hashlib
import json
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            out[name] = lineage
    return out


def prefix(lineage, rank):
    return ";".join(lineage.split(";")[: RANKS.index(rank) + 1])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--alignment", required=True, help="the un-injected alignment")
    p.add_argument("--taxonomy", required=True, help="the un-injected taxonomy")
    p.add_argument("--sequence", required=True, help="the one sequence to mislabel")
    p.add_argument("--wrong-label", required=True, help="the lineage to give it")
    p.add_argument("--keep-rank", default="order", choices=RANKS,
                   help="the clade around the sequence that is kept whole")
    p.add_argument("--per-family", type=int, default=0, help="cap each family; 0 means no cap")
    p.add_argument("--outgroup", type=int, default=10,
                   help="sequences from outside the kept clade, spread over other clades at the "
                        "same rank, so the clade under test is not the whole tree")
    # The cell this sequence came from, so the case carries the same company the sequence had.
    # Without it a case has one wrong label, and the grid's cells have k of them sharing it: at k=2
    # the other carrier stays in the reference while the target is left out, labelled with the wrong
    # family and belonging to the right one, which is evidence *for* the wrong label. A case with
    # one wrong label is therefore an easier problem than the run it is meant to reproduce.
    p.add_argument("--truth", help="the cell's truth.json; every injected sequence sharing the "
                                   "target's true group and wrong label is relabelled too")
    # How many of the cell's wrong labels the case carries. The default is the target's own group,
    # which is the smallest case that reproduces anything. Raising it is the measurement the
    # mechanism asks for: one wrong label is found by both tools and the whole cell's 102 are found
    # by one of them, so the interesting quantity is where in between the two part company. A count
    # at or above the cell's size reproduces the cell exactly, which is the control that says this
    # script agrees with the run it is modelling.
    p.add_argument("--injected-count", type=int, default=0,
                   help="with --truth: apply this many of the cell's wrong labels, the target's "
                        "group first; 0 means the group alone")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    aln, tax = read_fasta(args.alignment), read_tax(args.taxonomy)
    target = args.sequence
    if target not in tax:
        raise SystemExit(f"{target} is not in {args.taxonomy}")
    if target not in aln:
        raise SystemExit(f"{target} is not in {args.alignment}")

    true_lineage = tax[target]
    # The wrong label must be a real lineage in the reference, as the grid's injection guarantees:
    # a label no other sequence carries would make the case about an empty taxon instead of about
    # the engines.
    if args.wrong_label not in set(tax.values()):
        raise SystemExit("the wrong label is not a lineage any sequence in the reference carries")

    # The target's companions, if a cell was given. Matched on the pair and not on the wrong label
    # alone: two groups can be relabelled into the same donor taxon, and only the ones that left the
    # target's own group are the company it had.
    relabel = {target: args.wrong_label}
    if args.truth:
        if not Path(args.truth).is_file():
            raise SystemExit(f"--truth names no readable file: {args.truth}")
        injected = json.loads(Path(args.truth).read_text())["injected"]
        if target not in injected:
            raise SystemExit(f"{target} is not injected in {args.truth}")
        rec = injected[target]
        companions = {n for n, r in injected.items()
                      if r["true"] == rec["true"] and r["wrong"] == rec["wrong"]}
        if args.wrong_label != rec["wrong"]:
            raise SystemExit(f"--wrong-label disagrees with {args.truth}: the cell says {rec['wrong']}")
        # The group first and the rest by name, so a count of n and a count of n+1 differ by one
        # sequence rather than by a different draw. No seed, for the reason --per-family has none.
        order = sorted(companions) + sorted(set(injected) - companions)
        if args.injected_count and args.injected_count < len(companions):
            raise SystemExit(f"--injected-count {args.injected_count} is below the target's own "
                             f"group of {len(companions)}, which the case cannot drop")
        for n in (order[:args.injected_count] if args.injected_count else sorted(companions)):
            relabel[n] = injected[n]["wrong"]

    kept_clade = prefix(true_lineage, args.keep_rank)
    wrong_clade = prefix(args.wrong_label, args.keep_rank)
    if wrong_clade != kept_clade:
        raise SystemExit(f"the wrong label sits outside the kept clade ({wrong_clade}); widen "
                         f"--keep-rank (class, phylum) until both are inside it")

    inside = sorted(n for n in tax if prefix(tax[n], args.keep_rank) == kept_clade)

    # Family by family, so --per-family means the same thing in every family.
    by_family, chosen = {}, []
    for n in inside:
        by_family.setdefault(prefix(tax[n], "family"), []).append(n)
    target_genus = prefix(true_lineage, "genus")
    for fam, members in sorted(by_family.items()):
        members.sort(key=lambda n: (n != target, n not in relabel,
                                    prefix(tax[n], "genus") != target_genus, n))
        chosen += members[: args.per_family] if args.per_family else members

    # The outgroup is taken one per clade in turn rather than all from the nearest, so a cap of 10
    # does not quietly become ten members of one family.
    outside = {}
    for n in sorted(set(tax) - set(inside)):
        outside.setdefault(prefix(tax[n], args.keep_rank), []).append(n)
    picked, i = [], 0
    while len(picked) < args.outgroup and any(v[i:] for v in outside.values()):
        for clade in sorted(outside):
            if len(picked) == args.outgroup:
                break
            if len(outside[clade]) > i:
                picked.append(outside[clade][i])
        i += 1
    chosen += picked

    if target not in chosen:
        raise SystemExit("the target did not survive the selection, which is a bug")

    # All-gap columns are dropped. A 1478-column alignment of 40 sequences is mostly gaps, and
    # RAxML warns on every such column; the sequences that remain are unchanged otherwise.
    width = len(aln[target])
    rows = [aln[n] for n in chosen]
    if any(len(r) != width for r in rows):
        raise SystemExit("the input is not an alignment: the sequences differ in length")
    informative = [j for j in range(width) if any(r[j] not in "-." for r in rows)]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "case.fasta").open("w") as fa, (out / "case.tax").open("w") as tx:
        for n in chosen:
            fa.write(f">{n}\n{''.join(aln[n][j] for j in informative)}\n")
            tx.write(f"{n}\t{relabel.get(n, tax[n])}\n")

    rank = next((r for r in RANKS
                 if prefix(true_lineage, r) != prefix(args.wrong_label, r)), None)
    (out / "case.json").write_text(json.dumps({
        "sequence": target,
        "true": true_lineage,
        "wrong": args.wrong_label,
        "distance": rank,
        "kept_clade": kept_clade,
        "n_seqs": len(chosen),
        # The case's own k, which can be below the cell's: a companion dropped by --per-family is a
        # case with fewer carriers than the run it reproduces, and the number has to say so.
        "n_wrong_labels": len(set(relabel) & set(chosen)),
        "wrong_labels": sorted(set(relabel) & set(chosen)),
        "n_outgroup": len(picked),
        "alignment_width": len(informative),
        # The digests and not just the paths. The case is meant to be sent to someone who does not
        # have this repository, and "cut out of gtdb_arc2k" names a file they cannot check; the
        # sha256 is what lets them verify they started from the same bytes we did.
        "source_alignment": args.alignment,
        "source_alignment_sha256": sha256(args.alignment),
        "source_taxonomy": args.taxonomy,
        "source_taxonomy_sha256": sha256(args.taxonomy),
        "per_family": args.per_family,
    }, indent=2) + "\n")
    print(f"{len(chosen)} sequences, {len(informative)} columns, one label changed at {rank}")


if __name__ == "__main__":
    main()
