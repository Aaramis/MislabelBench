#!/usr/bin/env python3
"""Check every injected dataset against the truth it claims.

The whole benchmark rests on the injected labels being exactly what truth.json says they
are. That is cheap to verify and expensive to get wrong silently, so it is a check that runs
rather than an assumption that holds.

For each cell: the set of lines that differ from the base taxonomy must equal the set of
injected names, the file must have the same number of entries as the base, and each injected
line must carry the recorded wrong label while differing from the true one at the recorded
rank and agreeing above it.

And the invariant the whole design rests on: every donor taxon keeps at least one correctly
labelled member. inject_mislabels.py enforces it with floor = k + 1, so leave-one-out always has
something true to place an injected sequence against, and a fully relabelled group would be
undetectable by construction -- its sequences sitting in the truth as misses no method could find.
That was reasoned from the code and never measured until it was: 0 orphaned groups across all 180
cells.
"""

import argparse
import json
import sys
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]


def read_tax(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            out[name] = lineage
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="the un-injected taxonomy")
    p.add_argument("--injected-dir", required=True)
    args = p.parse_args()

    base = read_tax(args.base)
    problems, checked = [], 0

    for truth_path in sorted(Path(args.injected_dir).glob("*/*.truth.json")):
        truth = json.loads(truth_path.read_text())
        cur = read_tax(str(truth_path).replace(".truth.json", ".tax"))
        injected = truth["injected"]
        checked += 1
        name = truth_path.parent.name

        if len(cur) != len(base):
            problems.append(f"{name}: {len(cur)} entries against {len(base)} in the base")
            continue

        changed = {n for n in base if cur.get(n) != base[n]}
        if changed != set(injected):
            problems.append(f"{name}: {len(changed)} lines changed, {len(injected)} declared")
            continue

        # Every donor group keeps a correctly labelled member. Membership comes from the base
        # taxonomy and not from the injected file: a wrong label is drawn from a real taxon at the
        # same prefix, so a sequence relabelled *into* a group would make that group look populated
        # when its own members had all been relabelled away.
        by_group = {}
        for seq, lineage in base.items():
            by_group.setdefault(lineage, set()).add(seq)
        orphaned = {rec.get("donor_group") or rec["true"] for rec in injected.values()}
        orphaned = {g for g in orphaned
                    if g in by_group and not (by_group[g] - set(injected))}
        if orphaned:
            problems.append(f"{name}: {len(orphaned)} donor group(s) left with no correctly "
                            f"labelled member, e.g. {sorted(orphaned)[0][-40:]}")
            continue

        r = RANKS.index(truth["distance"])
        for n, rec in injected.items():
            if cur[n] != rec["wrong"]:
                problems.append(f"{name}/{n}: label is not the recorded wrong one")
                break
            a, b = rec["true"].split(";"), rec["wrong"].split(";")
            if a[:r] != b[:r] or a[r] == b[r]:
                problems.append(f"{name}/{n}: wrong label does not differ at {truth['distance']}")
                break

    print(f"{checked} cells checked, {checked - len(problems)} sound")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} cells failed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
