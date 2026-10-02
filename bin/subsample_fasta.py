#!/usr/bin/env python3
"""Draw a fixed number of sequences at random, reproducibly.

Taking the head of the file instead would correlate the draw with accession order, which in
GTDB tracks submission date and therefore genome quality.
"""

import argparse
import json
import random
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fasta", required=True)
    p.add_argument("--tax", required=True)
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--prefix", required=True)
    args = p.parse_args()

    seqs = read_fasta(args.fasta)
    tax = dict(l.split("\t", 1) for l in Path(args.tax).read_text().splitlines() if l.strip())
    names = sorted(set(seqs) & set(tax))
    if len(names) < args.n:
        raise SystemExit(f"only {len(names)} sequences available, {args.n} requested")
    picked = random.Random(args.seed).sample(names, args.n)

    Path(f"{args.prefix}.fasta").write_text("".join(f">{n}\n{seqs[n]}\n" for n in picked))
    Path(f"{args.prefix}.tax").write_text("".join(f"{n}\t{tax[n]}\n" for n in picked))
    Path(f"{args.prefix}.subsample.json").write_text(json.dumps(
        {"source_sequences": len(names), "drawn": args.n, "seed": args.seed}, indent=2))
    print(f"{args.n} of {len(names)} drawn with seed {args.seed}")


if __name__ == "__main__":
    main()
