#!/usr/bin/env python3
"""Did every condition of a cell read the same database?

Protocol.md 2.5 rests on it: "Both run on the identical database in every cell, so whatever errors
the base already contains are shared between them and the comparison between the two tools does not
depend on knowing what those errors are." Nothing recorded it. run.json carried the dataset's name,
which is a label, and the guarantee came from main.nf resolving one path per cell and handing it to
both branches -- true by construction and unprovable from the records.

The tool modules now write the sha256 of the files they read and collect_run.py folds them into
run.json, so this compares them. A cell whose conditions disagree is a cell whose tool comparison
means nothing, and it would otherwise be invisible.

Records written before the field existed are counted and named rather than passed over, because
"no disagreement found" over records that cannot disagree is not a result.
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--glob", default="results/*/runs/*/run.json")
    args = p.parse_args()

    by_cell = defaultdict(dict)
    without = []
    for f in sorted(Path(".").glob(args.glob)):
        d = json.loads(f.read_text())
        if "inputs" not in d:
            without.append(str(f))
            continue
        key = (f.parts[1], d.get("dataset"), d.get("rep"))
        by_cell[key][d.get("condition")] = d["inputs"]

    problems = []
    for key, conds in sorted(by_cell.items()):
        digests = {name: {c: i.get(name) for c, i in conds.items()}
                   for i in conds.values() for name in i}
        for name, per_cond in digests.items():
            seen = {v for v in per_cond.values() if v is not None}
            if len(seen) > 1:
                problems.append(f"{key[0]}/{key[1]} rep{key[2]}: {name} differs between "
                                f"conditions: {per_cond}")

    # And the stronger claim, which cross-condition agreement does not make: that the file the run
    # read is the file in the repository. Two conditions can agree on a database neither of them got
    # from here. Every recorded name is looked for under data/ and compared.
    matched_repo = unmatched = 0
    for key, conds in sorted(by_cell.items()):
        for cond, inputs in conds.items():
            for name, digest in inputs.items():
                here = next(Path("data").rglob(name), None)
                if here is None:
                    unmatched += 1
                    continue
                matched_repo += 1
                have = hashlib.sha256(here.read_bytes()).hexdigest()
                if have != digest:
                    problems.append(f"{key[0]}/{key[1]} rep{key[2]} {cond}: {name} was read as "
                                    f"{digest[:12]} and is {have[:12]} in the repository")

    # A gate that checked nothing must not report success. The first run of this script matched no
    # files at all -- the job had left the working directory at the Nextflow launch dir, so the
    # relative glob resolved under .nf/ -- and it printed "0 cells, 0 consistent" and exited 0. The
    # second shape of the same fault outlived that fix: with records present but none carrying the
    # field, `not by_cell and not without` was false and nothing was compared, so 1022 published
    # records all predating the field read as a pass.
    if not by_cell:
        sys.exit(f"{len(without)} run records matched {args.glob} from {Path('.').resolve()} and "
                 f"none carries an input digest, so nothing was compared")

    print(f"{len(by_cell)} cells with recorded input digests, "
          f"{len(by_cell) - len({p.split(':')[0] for p in problems})} consistent")
    print(f"{matched_repo} recorded input(s) found under data/ and compared, {unmatched} not found")
    if without:
        print(f"  {len(without)} records predate the field and cannot be checked, "
              f"e.g. {without[0]}", file=sys.stderr)
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} disagreement(s); those cells compare two tools on two databases",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
