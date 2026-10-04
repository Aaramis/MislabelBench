#!/usr/bin/env python3
"""Turn a UNITE general FASTA release into the (sequences, taxonomy) pair SATIVA expects.

UNITE headers are '|'-separated:

    >Abrothallus_subhalei|MT153946|SH1227328.10FU|refs|k__Fungi;p__Ascomycota;...;s__...

Field 4 marks the subset: refs, refs_singleton or reps. RepS is what this benchmark uses,
because RefS holds one sequence per species hypothesis and leave-one-out cannot judge a
sequence with no sibling. The counts are in assets/datasets.yml with the reasoning.

This produces unaligned sequences. UNITE ships no alignment and ITS is hard to align well,
which is an open question in the protocol rather than something settled here.
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

UNSAFE = re.compile(r"[^A-Za-z0-9_.|/-]")
SUBSETS = ("refs", "refs_singleton", "reps")


def opener(path):
    return gzip.open(path, "rt", errors="replace") if str(path).endswith(".gz") else open(path, errors="replace")


def records(path):
    name, chunks = None, []
    for line in opener(path):
        if line.startswith(">"):
            if name:
                yield name, "".join(chunks)
            name, chunks = line[1:].rstrip("\n"), []
        else:
            chunks.append(line.strip())
    if name:
        yield name, "".join(chunks)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fasta", help="sh_general_release_dynamic_*.fasta")
    p.add_argument("--subset", default="reps", choices=SUBSETS + ("refs_all",),
                   help="refs_all means refs plus refs_singleton, the published RefS count")
    p.add_argument("--min-len", type=int, default=0)
    p.add_argument("--prefix", default="unite")
    args = p.parse_args()

    wanted = {"refs", "refs_singleton"} if args.subset == "refs_all" else {args.subset}
    counts = Counter()
    seen = set()
    out_fa = Path(f"{args.prefix}.fasta").open("w")
    out_tx = Path(f"{args.prefix}.tax").open("w")

    for header, seq in records(args.fasta):
        counts["in_release"] += 1
        fields = header.split("|")
        if len(fields) < 5:
            counts["malformed_header"] += 1
            continue
        counts[f"subset_{fields[3]}"] += 1
        if fields[3] not in wanted:
            continue
        counts["in_subset"] += 1
        if len(seq) < args.min_len:
            counts["too_short"] += 1
            continue
        # The accession is the stable identifier; the species name is not unique.
        safe = UNSAFE.sub("_", f"{fields[1]}_{fields[2]}")
        if safe in seen:
            counts["name_collision"] += 1
            continue
        seen.add(safe)
        counts["kept"] += 1
        out_fa.write(f">{safe}\n{seq}\n")
        out_tx.write(f"{safe}\t{fields[4]}\n")

    out_fa.close()
    out_tx.close()

    # A subset that matches nothing wrote two empty files and exited 0. That is how an upstream
    # rename would arrive -- field 4 is a string this script compares by equality, and UNITE is
    # free to spell it differently in v11 -- and the next step would build a reference on an empty
    # FASTA. The subsets actually seen are already counted, so the error can name them.
    if not counts["kept"]:
        seen = ", ".join(f"{k[len('subset_'):]}={v}" for k, v in sorted(counts.items())
                         if k.startswith("subset_")) or "none"
        sys.exit(f"--subset {args.subset} matched nothing. subsets present: {seen}")

    if counts["malformed_header"] or counts["name_collision"]:
        print(f"warning: {counts['malformed_header']} malformed headers, "
              f"{counts['name_collision']} collisions", file=sys.stderr)

    Path(f"{args.prefix}.counts.json").write_text(json.dumps(dict(counts), indent=2))
    print(json.dumps(dict(counts), indent=2))


if __name__ == "__main__":
    main()
