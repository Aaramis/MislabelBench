#!/usr/bin/env python3
"""Pick the bacterial clade the archaeal results are replicated on, by the criteria and not by hand.

The protocol is "to check that our conclusions are not specific to archaea, we repeat the
baseline and part of the injection grid on one bacterial clade of comparable size, chosen by the
same evaluability criteria". A whole bacterial phylum is out of the question -- Pseudomonadota alone
has 392 425 sequences over 1 200 nt -- so the candidates are every bacterial class and order in
`ssu_all_r226`, scored on the two numbers the archaeal set is characterised by: 7 051 sequences after
the 1 200 nt filter, and 72.7 % of them judgeable at species (a sibling with the same species label).

Judgeability is computed the way bin/data/dataset_shape.py computes it, by importing its rule rather than
restating it, so the figure here and the figure in results/shape_*.json are one definition. The
score is the sum of the two relative distances, |n - 7051| / 7051 + |judg - 72.7| / 72.7, and the
ten nearest candidates are printed so the choice is visible and a reader can see what the runner-up
would have been.
"""

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from dataset_shape import RANKS_GTDB, is_unresolved

TARGET_N = 7051
TARGET_JUDG = 72.7
MIN_LEN = 1200


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fasta", required=True, help="ssu_all_r226.fna.gz")
    p.add_argument("--ranks", default="class,order")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--out")
    args = p.parse_args()

    rank_idx = [RANKS_GTDB.index(r) for r in args.ranks.split(",")]
    # Per candidate clade: sequence count, count over the length filter, and the species and genus
    # label counts among the long ones, which is what judgeability is computed from.
    n_all = Counter()
    n_long = Counter()
    species = defaultdict(Counter)
    genus = defaultdict(Counter)
    genomes = defaultdict(lambda: defaultdict(set))
    for line in gzip.open(args.fasta, "rt", errors="replace"):
        if not line.startswith(">"):
            continue
        head = line[1:].rstrip("\n")
        acc, _, rest = head.partition(" ")
        lineage = rest.split(" [")[0].strip()
        if not lineage.startswith("d__Bacteria"):
            continue
        parts = lineage.split(";")
        if len(parts) != len(RANKS_GTDB):
            continue
        m = re.search(r"\[ssu_len=(\d+)\]", rest)
        length = int(m.group(1)) if m else 0
        for i in rank_idx:
            clade = ";".join(parts[: i + 1])
            n_all[clade] += 1
            if length < MIN_LEN:
                continue
            n_long[clade] += 1
            sp = parts[6].split("__", 1)[-1]
            if not is_unresolved(sp):
                species[clade][lineage] += 1
                genomes[clade][lineage].add(acc.split("~")[0])
            ge = parts[5].split("__", 1)[-1]
            if not is_unresolved(ge):
                genus[clade][";".join(parts[:6])] += 1

    rows = []
    for clade, n in n_long.items():
        if n < 1000:
            continue
        sp_counts = species[clade]
        total = sum(sp_counts.values())
        judg_sp = 100 * sum(c for c in sp_counts.values() if c >= 2) / total if total else 0.0
        two_genomes = (100 * sum(c for lin, c in sp_counts.items() if len(genomes[clade][lin]) >= 2)
                       / total if total else 0.0)
        ge_counts = genus[clade]
        gt = sum(ge_counts.values())
        judg_ge = 100 * sum(c for c in ge_counts.values() if c >= 2) / gt if gt else 0.0
        score = abs(n - TARGET_N) / TARGET_N + abs(judg_sp - TARGET_JUDG) / TARGET_JUDG
        rows.append({"clade": clade, "rank": RANKS_GTDB[clade.count(";")],
                     "sequences": n_all[clade], "over_1200": n,
                     "judgeable_species_pct": round(judg_sp, 1),
                     "judgeable_species_two_genomes_pct": round(two_genomes, 1),
                     "judgeable_genus_pct": round(judg_ge, 1),
                     "n_species": len(sp_counts), "score": round(score, 4)})
    rows.sort(key=lambda r: r["score"])

    print(f"{'clade':52}{'rank':7}{'all':>8}{'>=1200':>8}{'judg sp':>9}{'2 gen':>7}"
          f"{'judg ge':>9}{'species':>9}{'score':>8}")
    for r in rows[: args.top]:
        short = r["clade"].split(";")[-1]
        print(f"{short:52}{r['rank']:7}{r['sequences']:>8}{r['over_1200']:>8}"
              f"{r['judgeable_species_pct']:>9.1f}{r['judgeable_species_two_genomes_pct']:>7.1f}"
              f"{r['judgeable_genus_pct']:>9.1f}{r['n_species']:>9}{r['score']:>8.3f}")
    chosen = rows[0]
    print(f"\nchosen: {chosen['clade']} ({chosen['over_1200']} sequences over {MIN_LEN} nt, "
          f"{chosen['judgeable_species_pct']} % judgeable at species) against the archaeal "
          f"{TARGET_N} and {TARGET_JUDG} %")
    if args.out:
        Path(args.out).write_text(json.dumps({
            "targets": {"sequences_over_1200": TARGET_N, "judgeable_species_pct": TARGET_JUDG},
            "score": "abs(n - 7051) / 7051 + abs(judg - 72.7) / 72.7",
            "ranks_considered": args.ranks.split(","),
            "minimum_sequences": 1000,
            "chosen": chosen,
            "candidates": rows[: args.top],
        }, indent=2) + "\n")


if __name__ == "__main__":
    main()
