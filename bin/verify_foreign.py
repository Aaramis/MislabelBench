#!/usr/bin/env python3
"""Check the kind-6 cells: the base must be untouched and every donor must be a bacterium
carrying a lineage that exists in the base."""
import argparse
import json
import sys
from pathlib import Path

def read_tax(p):
    return dict(l.split("\t", 1) for l in Path(p).read_text().splitlines() if l.strip())

p = argparse.ArgumentParser()
p.add_argument("--base", default="data/gtdb/gtdb_arc2k.tax", help="the un-injected taxonomy")
p.add_argument("--foreign-dir", default="data/foreign")
args = p.parse_args()

base = read_tax(args.base)
base_lineages = set(base.values())
problems, checked = [], 0
for truth_p in sorted(Path(args.foreign_dir).glob("*/*.truth.json")):
    t = json.loads(truth_p.read_text())
    cur = read_tax(str(truth_p).replace(".truth.json", ".tax"))
    inj = t["injected"]
    checked += 1
    name = truth_p.parent.name
    if {k: v for k, v in cur.items() if k in base} != base:
        problems.append(f"{name}: the base taxonomy was modified")
    if set(cur) - set(base) != set(inj):
        problems.append(f"{name}: added sequences do not match the declared ones")
    for n, rec in inj.items():
        if not rec["true"].startswith("d__Bacteria"):
            problems.append(f"{name}/{n}: donor is not bacterial")
            break
        if cur[n] != rec["wrong"] or rec["wrong"] not in base_lineages:
            problems.append(f"{name}/{n}: declared lineage is not one the base carries")
            break
print(f"{checked} cells checked, {checked - len(problems)} sound")
for p in problems[:5]:
    print(" ", p, file=sys.stderr)
sys.exit(1 if problems else 0)
