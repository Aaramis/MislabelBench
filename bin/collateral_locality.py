#!/usr/bin/env python3
"""Are the collateral flags neighbours of the injected sequences?

If `gained` is perturbation, the newly flagged sequences should sit in the clades the
injection touched: either the donor taxon (where the wrong label points) or the recipient
taxon (which lost a member to a wrong label). If instead they are scattered, the injection is
destabilising the whole tree and the background cannot be reasoned about locally.
"""
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--base-tax", default="data/gtdb/gtdb_arc2k.tax")
p.add_argument("--baseline", required=True, help=".mis of the un-injected run for this condition")
p.add_argument("--injected-dir", default="data/injected")
p.add_argument("--runs-dir", default="results/grid_fork/runs")
p.add_argument("--condition", required=True, help="condition suffix; without it the glob would mix "
                                                 "every condition in the runs directory")
args = p.parse_args()

# The canonical order, not a hand-written map: the first version of this omitted "class" and
# died on the cells that were added for it.
RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]
RANK = {r: i for i, r in enumerate(RANKS)}

def lineages(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            n, _, lin = line.partition("\t")
            out[n] = lin.split(";")
    return out

def flagged(p):
    return {l.split("\t")[0] for l in Path(p).read_text().splitlines()
            if l.strip() and not l.startswith(";")}

base_tax = lineages(args.base_tax)
base = flagged(args.baseline)

tot_near = tot_gained = ref_near = ref_n = 0
per_dist = {}
for mis in sorted(Path(args.runs_dir).glob(f"*__{args.condition}/*.mis")):
    cell = mis.parent.name.split("__")[0]
    truth_p = Path(args.injected_dir) / cell / f"{cell}.truth.json"
    if not truth_p.exists():
        continue
    truth = json.loads(truth_p.read_text())
    r = RANK[truth["distance"]]
    inj = truth["injected"]
    gained = (flagged(mis) - set(inj)) - (base - set(inj))

    # The two clades the injection actually renamed: the one the wrong label claims and the
    # one the sequence really belongs to, taken at the rank that was changed. Taking them one
    # rank higher would make the phylum row vacuous, since every clade above phylum here is
    # d__Archaea and any sequence would count as a neighbour.
    touched = set()
    for rec in inj.values():
        touched.add(tuple(rec["true"].split(";")[:r + 1]))
        touched.add(tuple(rec["wrong"].split(";")[:r + 1]))

    near = sum(1 for g in gained if tuple(base_tax[g][:r + 1]) in touched)
    # The same test on the baseline flags that survived: if they sit in the touched clades as often,
    # a collateral flag being there says nothing about contamination.
    kept = (base - set(inj)) & (flagged(mis) - set(inj))
    ref_near += sum(1 for g in kept if tuple(base_tax[g][:r + 1]) in touched)
    ref_n += len(kept)
    tot_near += near
    tot_gained += len(gained)
    d = truth["distance"]
    a, b = per_dist.get(d, (0, 0))
    per_dist[d] = (a + near, b + len(gained))

print(f"collateral flags: {tot_gained}, of which {tot_near} ({100*tot_near/tot_gained:.1f}%) "
      f"lie in a clade the injection touched")
print(f"baseline flags kept: {ref_n}, of which {ref_near} ({100*ref_near/ref_n:.1f}%) "
      f"lie in a clade the injection touched")
for d in RANKS[1:]:
    if d not in per_dist:
        continue
    n, t = per_dist[d]
    print(f"  {d:9} {n:5}/{t:<5} {100*n/t:5.1f}%")
