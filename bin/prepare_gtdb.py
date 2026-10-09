#!/usr/bin/env python3
"""Turn a GTDB ssu_all release into the (sequences, taxonomy) pair SATIVA expects.

GTDB carries the lineage in the FASTA header, after the accession:

    >GB_GCA_030638685.1 d__Archaea;p__Asgardarchaeota;...;s__ [location=...] [ssu_len=...]

so there is no join to do. One genome can contribute several SSU copies, which GTDB
disambiguates with a ~suffix; those are kept, since several copies of one genome are exactly
the sibling sequences leave-one-out needs.

Writes the counts it saw at every step to a JSON sidecar, so the provenance record in
assets/datasets.yml can be checked rather than trusted.
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

# SATIVA rewrites anything outside this set, so do it here and keep the two files in step.
UNSAFE = re.compile(r"[^A-Za-z0-9_.|/-]")


def opener(path):
    return gzip.open(path, "rt", errors="replace") if str(path).endswith(".gz") else open(path, errors="replace")


def records(path):
    name, lineage, chunks = None, None, []
    for line in opener(path):
        if line.startswith(">"):
            if name:
                yield name, lineage, "".join(chunks)
            head = line[1:].rstrip("\n")
            parts = head.split(" ", 1)
            name = parts[0]
            lineage = parts[1].split(" [")[0].strip() if len(parts) == 2 else ""
            chunks = []
        else:
            chunks.append(line.strip())
    if name:
        yield name, lineage, "".join(chunks)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fasta", help="ssu_all_r226.fna.gz")
    # A lineage prefix, not only a domain: "d__Bacteria;p__Bacillota;c__Clostridia;o__Lachnospirales"
    # selects the bacterial clade the archaeal results are replicated on. The flag keeps its name so
    # the archaeal commands recorded in assets/datasets.yml still run as written.
    p.add_argument("--domain", default="d__Archaea", help="keep lineages starting with this prefix")
    p.add_argument("--min-len", type=int, default=0, help="drop sequences shorter than this")
    p.add_argument("--prefix", default="gtdb_archaea")
    args = p.parse_args()

    counts = Counter()
    seen = set()
    out_fa = Path(f"{args.prefix}.fasta").open("w")
    out_tx = Path(f"{args.prefix}.tax").open("w")

    for name, lineage, seq in records(args.fasta):
        counts["in_release"] += 1
        if not lineage.startswith(args.domain):
            continue
        counts["in_domain"] += 1
        if len(seq) < args.min_len:
            counts["too_short"] += 1
            continue
        safe = UNSAFE.sub("_", name)
        if safe in seen:
            # GTDB already disambiguates multiple copies; a collision here would mean two
            # different accessions collapsing onto one name, which must not pass silently.
            counts["name_collision"] += 1
            continue
        seen.add(safe)
        counts["kept"] += 1
        out_fa.write(f">{safe}\n{seq}\n")
        out_tx.write(f"{safe}\t{lineage}\n")

    out_fa.close()
    out_tx.close()

    if counts["name_collision"]:
        print(f"warning: {counts['name_collision']} name collisions dropped", file=sys.stderr)

    Path(f"{args.prefix}.counts.json").write_text(json.dumps(dict(counts), indent=2))
    print(json.dumps(dict(counts), indent=2))


if __name__ == "__main__":
    main()
