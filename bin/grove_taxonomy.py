#!/usr/bin/env python3
"""Give a RAxMLGrove tree a seven-rank taxonomy that is a function of the tree alone.

A Grove tree carries no taxonomy, and the simulated control's whole value is that a label cannot be
wrong because the tree *is* the taxonomy. So the ranks cannot be drawn onto the tree by hand: they
have to come out of it. The rule here is one partition per rank, obtained by splitting the tree at
its own shallowest branchings until the clade count reaches a target, with the targets a geometric
ladder in the number of tips: rank r of seven gets round(m ** (r/8)) clades. For 864 tips that is
2, 5, 13, 29, 68, 159, 371, so each rank refines the one above it by the same factor m ** (1/8) =
2.3. The hand-made control this replaces had the same geometric shape, 3, 6, 12, 24, 48, 144 with
ratios of 2 and 3, but those six numbers were chosen; this ladder follows from the tree's size.

Splitting shallowest-first makes the ranks nested by construction -- the node set of one rank is a
subset of the next -- so a sequence's family contains its genus contains its species, and the path
from the root to a sequence is unique. Clades are named after their own smallest tip, so no name
depends on the order the file happens to be written in.

**Why not cut at fixed heights.** The first version of this rule cut at the 1/8 ... 7/8 quantiles of
the internal-node height distribution. Measured on a Yule tree
of 864 tips it fails twice over, and the second failure is the fatal one. A tip shallower than a cut
has no clade at that rank, so it has no complete path at all: on a phylogram with lognormal rate
variation, **648 of 864 tips were dropped**, and because lineages keep dropping out the deeper cuts
produce *fewer* clades than the shallower ones (257, 256, 270, 209, 108 from class to species), which
is not a taxonomy. Even on the ultrametric tree where nothing drops, node heights are tip-heavy --
most internal nodes are near the tips -- so the cuts land on top of each other: 110 domains and 756
species of which 666 singletons, judgeable fraction 22.9 %. Counting clades instead keeps every tip,
makes the ranks exactly as fine as asked, and raises the judgeable fraction to 81.1 % and 72.1 % on
those same two trees.

**The judgeable fraction is the number that decides whether this control can replace the hand-made
one, and it is measured, not assumed.** A species clade of one tip cannot be judged by leave-one-out
at all: remove the sequence and its rank has no representative left. An empirical topology produces
such singletons and a balanced hand-made one does not, so the record below reports, for every rank,
what fraction of sequences sit in a clade of two or more.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def parse_newick(text):
    """Flat node list: name, branch length, children, parent. No dependency, no recursion limit."""
    text = re.sub(r"\[[^\]]*\]", "", text).strip()
    text = text[:text.rindex(";")] if ";" in text else text
    nodes, stack, pos = [], [], 0

    def add(parent):
        nodes.append({"name": "", "length": 0.0, "children": [], "parent": parent})
        if parent is not None:
            nodes[parent]["children"].append(len(nodes) - 1)
        return len(nodes) - 1

    cur = None
    while pos < len(text):
        ch = text[pos]
        if ch == "(":
            stack.append(add(stack[-1] if stack else None))
            cur = None                           # the next token belongs to a child, not to this node
            pos += 1
        elif ch == ",":
            cur = None
            pos += 1
        elif ch == ")":
            cur = stack.pop()
            pos += 1
        elif ch in ": \t\n\r":
            if ch == ":":
                pos += 1
                start = pos
                while pos < len(text) and text[pos] not in "(), \t\n\r":
                    pos += 1
                if cur is None:                  # an unnamed tip, which is legal Newick
                    cur = add(stack[-1])
                nodes[cur]["length"] = float(text[start:pos])
            else:
                pos += 1
        else:
            start = pos
            while pos < len(text) and text[pos] not in "(),:":
                pos += 1
            name = text[start:pos].strip().strip("'\"")
            if cur is None:                      # a tip: it has no parentheses of its own
                cur = add(stack[-1] if stack else None)
            nodes[cur]["name"] = name
    if stack:
        raise SystemExit("unbalanced parentheses in the Newick string")
    return nodes


def heights(nodes):
    """Root distance, iteratively: a Grove tree of 1000 taxa is deep enough to matter."""
    h = [0.0] * len(nodes)
    order, stack = [], [0]
    while stack:
        i = stack.pop()
        order.append(i)
        for c in nodes[i]["children"]:
            h[c] = h[i] + nodes[c]["length"]
            stack.append(c)
    return h, order


def partitions(nodes, h, order, targets):
    """One clade set per rank: expand the shallowest branching until the count reaches the target.

    Ascending height guarantees a node's parent is expanded before the node itself, so the frontier
    always holds exactly one ancestor-or-self of every tip. That is what keeps every tip labelled at
    every rank, which a fixed height cut does not.
    """
    inner = sorted((i for i, n in enumerate(nodes) if n["children"]),
                   key=lambda i: (h[i], i))
    frontier, snaps, cut, count, j = {inner[0]}, [], [], 1, 0
    for k in targets:
        while count < k and j < len(inner):
            i = inner[j]
            j += 1
            if i in frontier:
                frontier.discard(i)
                frontier.update(nodes[i]["children"])
                count += len(nodes[i]["children"]) - 1
        snaps.append(set(frontier))
        cut.append(h[inner[j - 1]] if j else 0.0)
    return snaps, cut


def clade_sizes(tips, label, rank):
    out = {}
    for t in tips:
        out.setdefault(label[t][rank], []).append(t)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, help="Newick, as org_script.py generate writes it")
    p.add_argument("--prefix", required=True)
    args = p.parse_args()

    nodes = parse_newick(Path(args.tree).read_text())
    if any(n["length"] < 0 for n in nodes):
        raise SystemExit("negative branch length: the shallowest-first order would not be an "
                         "ancestor order, so the ranks could not be nested")
    h, order = heights(nodes)
    tips = [i for i, n in enumerate(nodes) if not n["children"]]
    if len(tips) < len(RANKS) + 1:
        raise SystemExit(f"{args.tree} has {len(tips)} tips, too few for {len(RANKS)} ranks")
    m = len(tips)
    targets = [max(2, round(m ** ((r + 1) / (len(RANKS) + 1)))) for r in range(len(RANKS))]
    snaps, cut = partitions(nodes, h, order, targets)

    label = [[None] * len(RANKS) for _ in nodes]
    for i in order:
        par = nodes[i]["parent"]
        for r in range(len(RANKS)):
            label[i][r] = i if i in snaps[r] else (label[par][r] if par is not None else i)

    # Name each clade after its own smallest tip, so no index depends on traversal order.
    smallest = [None] * len(nodes)
    for i in reversed(order):
        kids = [smallest[c] for c in nodes[i]["children"] if smallest[c] is not None]
        smallest[i] = min(kids) if kids else (nodes[i]["name"] or None)
    name = {}
    for r, group in enumerate(snaps):
        for k, i in enumerate(sorted(group, key=lambda j: smallest[j] or ""), start=1):
            name[(r, i)] = f"{RANKS[r][0]}__{k:04d}"

    tax = {nodes[t]["name"]: ";".join(name[(r, label[t][r])] for r in range(len(RANKS)))
           for t in tips}
    if len(tax) != m:
        raise SystemExit(f"{m} tips but {len(tax)} distinct tip names in {args.tree}")

    judgeable = {}
    for r, rank in enumerate(RANKS):
        groups = clade_sizes(tips, label, r)
        judgeable[rank] = round(sum(len(v) for v in groups.values() if len(v) > 1) / m, 4)
    species = clade_sizes(tips, label, len(RANKS) - 1)

    Path(f"{args.prefix}.tax").write_text("".join(f"{n}\t{tax[n]}\n" for n in sorted(tax)))

    record = {
        "tree": Path(args.tree).name,
        "tree_sha256": hashlib.sha256(Path(args.tree).read_bytes()).hexdigest(),
        "rule": "rank r of 7 is the partition into round(m ** (r/8)) clades, splitting the "
                "shallowest branchings first",
        "n_tips": m,
        "targets": dict(zip(RANKS, targets)),
        "clades": {RANKS[r]: len(g) for r, g in enumerate(snaps)},
        "cut_height": dict(zip(RANKS, [round(c, 6) for c in cut])),
        "judgeable_fraction": judgeable,
        "n_species": len(species),
        "n_singleton_species": sum(1 for v in species.values() if len(v) == 1),
        "largest_species": max(len(v) for v in species.values()),
        # inject_mislabels.py needs k+1 members in a donor group, so a grid running to k=5 needs
        # species of six. An empirical topology gives a very skewed distribution and this is the
        # column that says whether the grid's high-k cells have anything to inject into.
        "species_of_six_or_more": sum(1 for v in species.values() if len(v) >= 6),
        "sequences_in_species_of_six_or_more": sum(len(v) for v in species.values() if len(v) >= 6),
        "tax_sha256": hashlib.sha256(Path(f"{args.prefix}.tax").read_bytes()).hexdigest(),
    }
    Path(f"{args.prefix}.grove_tax.json").write_text(json.dumps(record, indent=2) + "\n")

    print(f"{m} tips, every one labelled at all {len(RANKS)} ranks")
    for r, rank in enumerate(RANKS):
        print(f"  {rank:8} {len(snaps[r]):5d} clades (asked {targets[r]:5d}) "
              f"below height {cut[r]:.6f}, judgeable {judgeable[rank]:.1%}")
    print(f"{len(species)} species, {record['n_singleton_species']} of them singletons, "
          f"largest {record['largest_species']}, {record['species_of_six_or_more']} with six or "
          f"more members holding {record['sequences_in_species_of_six_or_more']} sequences")


if __name__ == "__main__":
    main()
