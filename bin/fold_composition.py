#!/usr/bin/env python3
"""What ends up in the same fold.

The k-fold leave-one-out places a whole fold at once against the tree with that fold removed.
Two sequences of the same species in one fold therefore leave together, and neither can be
placed against the other: that is the approximation error the fold count hides. The tool offers
SATIVA_EPANG_FOLD_ORDER=tree to avoid it and does not use it by default.

This reads the fold membership straight out of a task directory, so it reports what the tool did
rather than what the fold rule should produce.
"""

import argparse
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path


def fold_members(taskdir):
    """Fold name -> the sequence names in it.

    The tool writes leaves as `r_<name>`, so the prefix comes off here. Without that the join
    against the taxonomy matches nothing and every count comes back as a silent zero.
    """
    out = {}
    for d in sorted(Path(taskdir).glob("fold_*")):
        q = d / "query.fasta"
        if not q.exists():
            continue
        names = []
        for line in q.read_text().splitlines():
            if line.startswith(">"):
                n = line[1:].split()[0]
                names.append(n[2:] if n.startswith("r_") else n)
        out[d.name] = names
    return out


def describe(taskdir, tax_path):
    folds = fold_members(taskdir)
    of_fold = {s: f for f, members in folds.items() for s in members}
    groups = defaultdict(list)
    for line in Path(tax_path).read_text().splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            if name in of_fold:
                groups[lineage].append(name)

    if not groups:
        raise SystemExit(f"no sequence of {tax_path} was found in {taskdir}; "
                         "the fold members and the taxonomy do not share a naming")
    pairs = same = 0
    for members in groups.values():
        for a, b in combinations(members, 2):
            pairs += 1
            same += of_fold[a] == of_fold[b]
    sizes = sorted(len(v) for v in folds.values())
    return {
        "taskdir": str(taskdir),
        "n_folds": len(folds),
        "sequences": len(of_fold),
        "fold_size_min": sizes[0] if sizes else 0,
        "fold_size_max": sizes[-1] if sizes else 0,
        "same_species_pairs": pairs,
        "pairs_sharing_a_fold": same,
        "co_location_rate": round(same / pairs, 5) if pairs else None,
        "membership": {f: sorted(m) for f, m in folds.items()},
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--taskdir")
    p.add_argument("--tax")
    p.add_argument("--out")
    # Both fold orders are measured from the same reused task directory, so the record's own
    # taskdir cannot tell them apart and only the output filename did.
    p.add_argument("--label", help="the condition this record describes, e.g. the fold order")
    p.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = p.parse_args()

    if args.compare:
        a, b = (json.loads(Path(f).read_text()) for f in args.compare)
        # A record written before `membership` existed crashed this with a bare KeyError. The two
        # committed records are exactly that: the job ran against a copy of this script synced two
        # minutes before the field was added, so the record does not have the format the code beside
        # it produces, and the rates below were readable while the partition check was not.
        missing = [f for f, d in zip(args.compare, (a, b)) if "membership" not in d]
        if missing:
            print(f"  cannot compare partitions: no 'membership' in {', '.join(missing)}; "
                  "rerun slurm/fold_order_check.sh to regenerate a complete record")
        ident = None if missing else a["membership"] == b["membership"]
        print(f"{Path(args.compare[0]).stem} vs {Path(args.compare[1]).stem}")
        print(f"  identical partitions: {'unknown' if ident is None else ident}")
        for d, label in ((a, args.compare[0]), (b, args.compare[1])):
            print(f"  {Path(label).stem:12} {d['n_folds']} folds, "
                  f"sizes {d['fold_size_min']}-{d['fold_size_max']}, "
                  f"same-species pairs sharing a fold {d['pairs_sharing_a_fold']}"
                  f"/{d['same_species_pairs']} = {d['co_location_rate']}")
        if ident:
            raise SystemExit("the two orders produced the same partition; the option did nothing")
        if ident is None and a.get("pairs_sharing_a_fold") == b.get("pairs_sharing_a_fold"):
            raise SystemExit("same co-location in both orders and no partition to compare; "
                             "the option may have done nothing")
        return

    if not (args.taskdir and args.tax):
        raise SystemExit("--taskdir and --tax are required unless --compare is used")
    d = describe(args.taskdir, args.tax)
    print(f"{d['n_folds']} folds over {d['sequences']} sequences, "
          f"sizes {d['fold_size_min']}-{d['fold_size_max']}; "
          f"same-species pairs sharing a fold {d['pairs_sharing_a_fold']}"
          f"/{d['same_species_pairs']} = {d['co_location_rate']}")
    if args.out:
        if args.label:
            d = {"label": args.label, **d}
        Path(args.out).write_text(json.dumps(d, indent=2))


if __name__ == "__main__":
    main()
