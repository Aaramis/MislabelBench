#!/usr/bin/env python3
"""The Grove control's taxonomy must be the tree, and this is the check.

The protocol requires of the simulated control that "the taxonomy matches the
generating tree". bin/data/grove_taxonomy.py builds the labels from the tree by construction, and its
tests pin that construction on synthetic trees; this is the gate on the committed data, so that a
reference whose labels were edited, regenerated from another tree, or truncated by a copy is refused
before either tool sees it.

Three properties, each a sentence when it fails:

  every tip in the tree has a lineage, and every lineage names a tip in the tree
  every label at every rank is a clade: the tips that carry it are exactly the tips below one node
  ranks nest: a label at rank r sits under exactly one label at rank r-1

Monophyly is checked by the most recent common ancestor of the label's tips having exactly that many
tips below it. That is the whole definition of "the tree is the taxonomy", and it is what makes a
flag on an untouched sequence a false positive in the strict sense.
"""

import argparse
import sys
from pathlib import Path

from grove_taxonomy import RANKS, heights, parse_newick


def read_tax(path):
    tax = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            tax[name] = lineage.split(";")
    return tax


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True)
    p.add_argument("--tax", required=True)
    args = p.parse_args()

    nodes = parse_newick(Path(args.tree).read_text())
    _, order = heights(nodes)
    tips = {n["name"]: i for i, n in enumerate(nodes) if not n["children"]}
    tax = read_tax(args.tax)
    problems = []

    missing = sorted(set(tips) - set(tax))
    extra = sorted(set(tax) - set(tips))
    if missing:
        problems.append(f"{len(missing)} tip(s) without a lineage, e.g. {missing[:3]}")
    if extra:
        problems.append(f"{len(extra)} lineage(s) naming no tip, e.g. {extra[:3]}")
    depths = {len(v) for v in tax.values()}
    if depths != {len(RANKS)}:
        problems.append(f"lineage depths {sorted(depths)}, expected {len(RANKS)}")

    # Tips below each node, from the leaves up.
    below = [0] * len(nodes)
    for i in reversed(order):
        below[i] = 1 if not nodes[i]["children"] else sum(below[c] for c in nodes[i]["children"])

    def ancestors(i):
        path = []
        while i is not None:
            path.append(i)
            i = nodes[i]["parent"]
        return path

    shared = {n: tips[n] for n in tax if n in tips}
    checked = 0
    for r, rank in enumerate(RANKS):
        members = {}
        for name, lineage in tax.items():
            if name in shared and len(lineage) == len(RANKS):
                members.setdefault(lineage[r], []).append(shared[name])
        for label, ids in members.items():
            # The MRCA is the deepest node on every member's path to the root.
            common = None
            for i in ids:
                path = ancestors(i)
                common = set(path) if common is None else common & set(path)
            mrca = max(common, key=lambda j: len(ancestors(j)))
            checked += 1
            if below[mrca] != len(ids):
                problems.append(f"{rank} {label}: {len(ids)} tips but their clade holds {below[mrca]}, "
                                f"so the label is not a clade of the tree")
        if r:
            parents = {}
            for lineage in tax.values():
                if len(lineage) == len(RANKS):
                    parents.setdefault(lineage[r], set()).add(lineage[r - 1])
            for label, ups in parents.items():
                if len(ups) > 1:
                    problems.append(f"{rank} {label} sits under {len(ups)} {RANKS[r - 1]} labels: "
                                    f"{sorted(ups)[:3]}")

    print(f"{len(tips)} tips, {len(tax)} lineages, {checked} labels over {len(RANKS)} ranks checked "
          f"for being clades of {args.tree}; {len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
