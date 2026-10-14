#!/usr/bin/env python3
"""The protocol's dataset table, computed from the release files rather than typed into a YAML comment.

Section 7 of the protocol compares three archaeal sets -- `ssu_reps`, `ssu_all`, and `ssu_all` after
the 1 200 nt filter -- on sequences and on evaluability at genus and species, and the last row adds
the share of species represented by two distinct genomes. Two of those numbers lived nowhere in this
repository except as a comment in assets/datasets.yml, and one, the two-genome share, nowhere at all.
A figure with no producer is a figure that is wrong once and then believed.

Judgeability is bin/dataset_shape.py's rule, imported: among sequences with a real label at a rank,
the share whose label is carried by at least one other sequence. The two-genome column counts a
species as judgeable only when its members come from at least two genomes, the accession before `~`
being the genome; two SSU copies of one genome are siblings for leave-one-out but not evidence that
the species is more than one isolate. Labels follow the GTDB convention (`d__...;s__...` in the
header), with `s__` unresolved forms excluded from the denominator as dataset_shape.py does.

The same table is produced for a bacterial clade by giving --clade its lineage prefix.
"""

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from dataset_shape import RANKS_GTDB, is_unresolved


def rows_of(path, clade):
    """(genome, lineage parts, ssu_len) for every record whose lineage starts with `clade`."""
    for line in gzip.open(path, "rt", errors="replace"):
        if not line.startswith(">"):
            continue
        head = line[1:].rstrip("\n")
        acc, _, rest = head.partition(" ")
        lineage = rest.split(" [")[0].strip()
        if not lineage.startswith(clade):
            continue
        parts = lineage.split(";")
        if len(parts) != len(RANKS_GTDB):
            continue
        m = re.search(r"\[ssu_len=(\d+)\]", rest)
        yield acc.split("~")[0], parts, int(m.group(1)) if m else 0


def shape(records, is_unresolved):
    members = {r: Counter() for r in ("genus", "species")}
    genomes = defaultdict(set)
    n = 0
    for genome, parts, _ in records:
        n += 1
        for rank, i in (("genus", 5), ("species", 6)):
            bare = parts[i].split("__", 1)[-1]
            if not is_unresolved(bare):
                key = ";".join(parts[: i + 1])
                members[rank][key] += 1
                if rank == "species":
                    genomes[key].add(genome)
    out = {"sequences": n}
    for rank in ("genus", "species"):
        total = sum(members[rank].values())
        out[f"evaluable_{rank}_pct"] = (round(100 * sum(c for c in members[rank].values() if c >= 2)
                                              / total, 1) if total else None)
    total = sum(members["species"].values())
    out["evaluable_species_two_genomes_pct"] = (
        round(100 * sum(c for k, c in members["species"].items()
                        if c >= 2 and len(genomes[k]) >= 2) / total, 1) if total else None)
    out["n_species"] = len(members["species"])
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ssu-all", required=True, help="ssu_all_r226.fna.gz")
    p.add_argument("--ssu-reps", help="ar53_ssu_reps_r226.fna.gz, or the bacterial reps file")
    p.add_argument("--clade", default="d__Archaea", help="lineage prefix selecting the records")
    p.add_argument("--min-len", type=int, default=1200)
    p.add_argument("--out")
    args = p.parse_args()

    table = {}
    if args.ssu_reps:
        table["ssu_reps"] = shape(rows_of(args.ssu_reps, args.clade), is_unresolved)
    everything = list(rows_of(args.ssu_all, args.clade))
    table["ssu_all"] = shape(everything, is_unresolved)
    table[f"ssu_all_over_{args.min_len}"] = shape(
        (r for r in everything if r[2] >= args.min_len), is_unresolved)

    print(f"{'set':22}{'sequences':>10}{'genus':>8}{'species':>9}{'2 genomes':>11}{'n species':>11}")
    for name, row in table.items():
        print(f"{name:22}{row['sequences']:>10}{row['evaluable_genus_pct']:>8}"
              f"{row['evaluable_species_pct']:>9}{row['evaluable_species_two_genomes_pct']:>11}"
              f"{row['n_species']:>11}")
    if args.out:
        Path(args.out).write_text(json.dumps({"clade": args.clade, "min_len": args.min_len,
                                              "sources": {"ssu_all": Path(args.ssu_all).name,
                                                          "ssu_reps": (Path(args.ssu_reps).name
                                                                       if args.ssu_reps else None)},
                                              "rows": table}, indent=2) + "\n")


if __name__ == "__main__":
    main()
