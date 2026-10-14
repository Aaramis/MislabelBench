#!/usr/bin/env python3
"""The chimera cells must be what their truth says, or a result on them says nothing.

Four things, each one a sentence when it fails: the base is unchanged and complete; every chimera
is parent A's aligned columns up to the recorded breakpoint and parent B's after it; the two parents
agree above the recorded rank and differ at it; the chimera carries parent A's lineage.
"""

import argparse
import json
import sys
from pathlib import Path

from inject_chimera import RANKS, read_fasta, read_tax


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-fasta", required=True)
    p.add_argument("--base-tax", required=True)
    p.add_argument("--chimera-dir", required=True)
    args = p.parse_args()

    base_seq, base_tax = read_fasta(args.base_fasta), read_tax(args.base_tax)
    problems, checked = [], 0
    for truth_p in sorted(Path(args.chimera_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        truth = json.loads(truth_p.read_text())
        seqs = read_fasta(truth_p.with_suffix("").with_suffix(".fasta"))
        tax = read_tax(truth_p.with_suffix("").with_suffix(".tax"))
        checked += 1
        r = RANKS.index(truth["distance"])
        if {k: v for k, v in seqs.items() if k in base_seq} != base_seq:
            problems.append(f"{cell}: the base alignment is not unchanged")
        if {k: v for k, v in tax.items() if k in base_tax} != base_tax:
            problems.append(f"{cell}: the base taxonomy is not unchanged")
        if set(seqs) - set(base_seq) != set(truth["injected"]):
            problems.append(f"{cell}: the added sequences are not the declared chimeras")
        for cid, rec in truth["injected"].items():
            a, b, col = rec["parent_a"], rec["parent_b"], rec["breakpoint_column"]
            if seqs.get(cid) != base_seq[a][:col] + base_seq[b][col:]:
                problems.append(f"{cell}/{cid}: not {a}[:{col}] + {b}[{col}:]")
            la, lb = base_tax[a].split(";"), base_tax[b].split(";")
            if la[:r] != lb[:r] or la[r] == lb[r]:
                problems.append(f"{cell}/{cid}: parents do not differ exactly at {truth['distance']}")
            if tax.get(cid) != base_tax[a]:
                problems.append(f"{cell}/{cid}: lineage is not parent A's")
    if not checked:
        sys.exit(f"no cell matched {args.chimera_dir}/*/*.truth.json")
    print(f"{checked} chimera cells checked, {checked - len(set(p.split(':')[0] for p in problems))} sound")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
