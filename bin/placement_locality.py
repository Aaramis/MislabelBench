#!/usr/bin/env python3
"""Where an injected sequence's placement actually landed, read off the jplace and not off recall.

The protocol's type-2 mechanism says that removing one of k co-labelled relatives leaves the
placement to land among the k-1 that still carry the wrong label, so the error is confirmed rather
than found. Every number supporting that so far was recall against the share of wrong-labelled
relatives, which is consistent with the mechanism and is not the mechanism. A co-author asked "did
you check". This reads the placement files slurm/placements.sh keeps and checks.

Per injected sequence, from the fold that held it out: the edge carrying the most placement weight,
that weight, the leaves on either side of the edge, the lowest rank the leaves below the edge share
with the declared (wrong) label and with the true one, and whether the edge sits inside the clade
spanned by the sequence's k-1 co-carriers -- the other injected sequences given the same wrong label
from the same donor group. Summed per cell and per k, split by whether the sequence was flagged.

jplace: Matsen et al. 2012. The tree carries `{n}` edge labels; `placements[].p` rows are read by
the file's own `fields` list, so column order is never assumed.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def dataset_name(n):
    """SATIVA prefixes every sequence with r_ in its own files; the dataset, truth and .mis do not."""
    return n[2:] if n.startswith("r_") else n


def parse_edge_tree(text):
    """A jplace tree: like Newick, with `{n}` after each node naming the edge above it.

    Returns nodes as dicts (name, children, parent, edge) and a map edge number -> node index.
    """
    text = text.strip().rstrip(";")
    nodes, stack, cur, pos = [], [], None, 0

    def add(parent):
        nodes.append({"name": "", "children": [], "parent": parent, "edge": None})
        if parent is not None:
            nodes[parent]["children"].append(len(nodes) - 1)
        return len(nodes) - 1

    while pos < len(text):
        ch = text[pos]
        if ch == "(":
            stack.append(add(stack[-1] if stack else None))
            cur = None
            pos += 1
        elif ch == ",":
            cur = None
            pos += 1
        elif ch == ")":
            cur = stack.pop()
            pos += 1
        elif ch == ":":
            pos += 1
            while pos < len(text) and text[pos] not in "(),{;":
                pos += 1
        elif ch == "{":
            end = text.index("}", pos)
            if cur is None:
                cur = add(stack[-1])
            nodes[cur]["edge"] = int(text[pos + 1:end])
            pos = end + 1
        elif ch in " \t\n\r":
            pos += 1
        else:
            start = pos
            while pos < len(text) and text[pos] not in "(),:{":
                pos += 1
            if cur is None:
                cur = add(stack[-1] if stack else None)
            nodes[cur]["name"] = dataset_name(text[start:pos].strip().strip("'\""))
    if stack:
        raise SystemExit("unbalanced parentheses in the jplace tree")
    edges = {n["edge"]: i for i, n in enumerate(nodes) if n["edge"] is not None}
    return nodes, edges


def leaves_below(nodes, i):
    out, stack = [], [i]
    while stack:
        j = stack.pop()
        if nodes[j]["children"]:
            stack.extend(nodes[j]["children"])
        else:
            out.append(nodes[j]["name"])
    return out


def shared_depth(a, b):
    """How many leading ranks two lineages share."""
    n = 0
    for x, y in zip(a.split(";"), b.split(";")):
        if x != y:
            break
        n += 1
    return n


def lineage_depth_of_clade(leaves, tax, lineage):
    """Lowest rank at which every leaf below the edge agrees with `lineage`; -1 for none."""
    depth = len(RANKS)
    for leaf in leaves:
        if leaf not in tax:
            return -1
        depth = min(depth, shared_depth(tax[leaf], lineage))
    return depth - 1 if leaves else -1


def read_jplace(path, tree=None):
    doc = json.loads(Path(path).read_text())
    fields = doc["fields"]
    if "tree" not in doc and tree is None:
        sys.exit(f"{path} carries no tree; upstream's leave-one-out jplace (RAxML -f O) never does, "
                 "pass --tree with the run's .refjson, whose tree carries the same edge numbers")
    nodes, edges = parse_edge_tree(doc.get("tree", tree))
    out = {}
    for pl in doc["placements"]:
        names = [dataset_name(n[0] if isinstance(n, list) else n) for n in pl.get("nm", pl.get("n", []))]
        rows = [dict(zip(fields, p)) for p in pl["p"]]
        best = max(rows, key=lambda r: r["like_weight_ratio"])
        for name in names:
            out[name] = {"edge": best["edge_num"], "lwr": best["like_weight_ratio"],
                         "n_edges": len(rows)}
    return nodes, edges, out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--truth", required=True, help="the cell's truth.json")
    p.add_argument("--tax", required=True, help="the cell's .tax, which carries the wrong labels")
    p.add_argument("--mis", required=True, help="the run's .mis, for which sequences were flagged")
    p.add_argument("--jplace", nargs="+", required=True,
                   help="placement files; a staged run has one per fold, upstream has one for all")
    p.add_argument("--tree", help="edge-labelled tree for jplace files without one: upstream's "
                                  ".refjson, or a Newick with {n} labels")
    p.add_argument("--out")
    args = p.parse_args()

    tree = None
    if args.tree:
        text = Path(args.tree).read_text()
        tree = json.loads(text)["tree"] if text.lstrip().startswith("{") else text

    truth = json.loads(Path(args.truth).read_text())
    injected = truth["injected"]
    tax = {}
    for line in Path(args.tax).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            tax[name] = lineage
    flagged = {l.split("\t")[0] for l in Path(args.mis).read_text().splitlines()
               if l.strip() and not l.startswith(";")}
    r = RANKS.index(truth["distance"])

    # Co-carriers: the other injected sequences from the same donor group with the same wrong label.
    group = defaultdict(set)
    for name, rec in injected.items():
        group[(rec.get("donor_group", rec["true"]), rec["wrong"])].add(name)

    rows = []
    for jp in args.jplace:
        nodes, edges, placed = read_jplace(jp, tree)
        for name, hit in placed.items():
            if name not in injected:
                continue
            rec = injected[name]
            node = edges[hit["edge"]]
            # Upstream numbers edges on the full tree, the held-out leaf included, so a placement
            # back on that leaf's own edge is "where it was": read the clade it hung from.
            if nodes[node]["name"] == name and nodes[node]["parent"] is not None:
                node = nodes[node]["parent"]
            below = [x for x in leaves_below(nodes, node) if x != name]
            sibs = group[(rec.get("donor_group", rec["true"]), rec["wrong"])] - {name}
            # Among the k-1: the edge's clade is within the clade the co-carriers span, which is
            # the smallest subtree holding all of them. Equivalent, and cheaper: every leaf below
            # the edge is a co-carrier or shares the co-carriers' true lineage down to the rank.
            among = bool(sibs) and bool(below) and all(
                x in sibs or (x in tax and shared_depth(tax[x], rec["true"]) > r) for x in below)
            rows.append({
                "sequence": name, "k": truth.get("k"), "flagged": name in flagged,
                "edge": hit["edge"], "lwr": round(hit["lwr"], 4), "edges_with_weight": hit["n_edges"],
                "leaves_below": len(below),
                "below_agree_with_wrong_to_rank": lineage_depth_of_clade(below, tax, rec["wrong"]),
                "below_agree_with_true_to_rank": lineage_depth_of_clade(below, tax, rec["true"]),
                "co_carriers": len(sibs), "co_carriers_below": sum(1 for x in below if x in sibs),
                "among_co_carriers": among,
            })
    if not rows:
        sys.exit("no injected sequence was placed in the given jplace files")

    summary = {}
    for flagged_state in (True, False):
        sub = [x for x in rows if x["flagged"] == flagged_state]
        if sub:
            summary["flagged" if flagged_state else "missed"] = {
                "n": len(sub),
                "among_co_carriers": sum(1 for x in sub if x["among_co_carriers"]),
                "median_lwr": sorted(x["lwr"] for x in sub)[len(sub) // 2],
            }
    print(f"{len(rows)} injected sequences placed, k={truth.get('k')}, distance {truth['distance']}")
    for state, v in summary.items():
        print(f"  {state:8} {v['n']:4}  landed among the k-1: {v['among_co_carriers']:4}  "
              f"median LWR on the best edge {v['median_lwr']:.3f}")
    if args.out:
        Path(args.out).write_text(json.dumps({
            "truth": args.truth, "mis": args.mis, "distance": truth["distance"], "k": truth.get("k"),
            "summary": summary, "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
