#!/usr/bin/env python3
"""Would a cluster-level label check catch what leave-one-out misses?

Leave-one-out loses shared mislabels because removing one carrier leaves the others anchoring the
placement onto the wrong label, and recall falls steeply with k. But in the injected grid the
carriers come from one donor group and the group keeps a correctly labelled member, so the
conflict is between near-identical sequences carrying different labels. That is visible without
any placement at all: dereplicate, and look for a cluster holding two labels.

This asks, for every injected sequence, whether some *correctly labelled* sequence in the database
is similar enough to it that a clustering step would put the two together. The alignment is
fixed-width (cmalign --matchonly), so identity is counted over the columns where both have a base.

The answer bounds what a pipeline-level check buys over the tool, which is the honest way to
report the kind 2 limit: not as a method that fails, but as one whose failures belong to a
different stage.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--alignment", required=True)
    p.add_argument("--base-tax", required=True)
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--thresholds", default="0.99,0.97")
    p.add_argument("--out")
    args = p.parse_args()

    aln = read_fasta(args.alignment)
    # identity() compares column i to column i, so this is only meaningful on an alignment, and
    # the file names here do not say which is which: gtdb_arc2k.fasta is aligned (2023 rows of
    # 1478 columns, subsampled from gtdb_arc1200.aligned.fasta), while gtdb_arc1200.fasta is the
    # unaligned release at 1200-2684 nt and gtdb_arc1200.aligned.fasta is its alignment. Handed
    # the unaligned one, every identity below would be a plausible-looking number about nothing.
    widths = {len(v) for v in aln.values()}
    if len(widths) != 1:
        raise SystemExit(f"{args.alignment} is not an alignment: {len(widths)} distinct widths, "
                         f"{min(widths)} to {max(widths)}")
    by_group = defaultdict(list)
    for line in Path(args.base_tax).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            by_group[lineage].append(name)

    thresholds = [float(t) for t in args.thresholds.split(",")]
    counts = {t: defaultdict(lambda: [0, 0]) for t in thresholds}
    for truth_p in sorted(Path(args.injected_dir).glob("*/*.truth.json")):
        truth = json.loads(truth_p.read_text())
        k = truth["k"]
        for name, rec in truth["injected"].items():
            # Members of this sequence's true group that still carry the correct label.
            correct = [m for m in by_group[rec["true"]] if m not in truth["injected"]]
            best = max((identity(aln[name], aln[m]) for m in correct), default=0.0)
            for t in thresholds:
                counts[t][k][0] += best >= t
                counts[t][k][1] += 1

    # A run that matched no cell printed this header, wrote {"by_k": []} and exited 0, and
    # analyses.sh discards stdout, so the empty file was the only trace. Same shape as the four
    # gates in D110.
    if not counts[thresholds[0]]:
        raise SystemExit(f"no cell matched {args.injected_dir}/*/*.truth.json")

    print("share of injected sequences with a correctly labelled near-identical neighbour")
    print(f"{'k':>4}" + "".join(f"{'>=' + str(t):>12}" for t in thresholds))
    rows = []
    for k in sorted(counts[thresholds[0]]):
        line = f"{k:>4}"
        row = {"k": k}
        for t in thresholds:
            hit, tot = counts[t][k]
            line += f"{hit / tot:12.3f}"
            row[str(t)] = round(hit / tot, 4)
            row["injected"] = tot
        print(line)
        rows.append(row)
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"thresholds": thresholds, "by_k": rows}, indent=2))


if __name__ == "__main__":
    main()
