#!/usr/bin/env python3
"""Does every dataset manifest tell the truth about its files?

`n_seqs` and `aln_len` are declared in a manifest, flow into `meta`, and are recorded in every
`run.json`, where they end up in figures and tables. Nothing checked them against the files they
describe, and the five manifests in this repo were all written by hand.

It also insists each fasta is an alignment of one width, which is the assumption every consumer
makes and which was violated once: a size subset was drawn from the ragged release file instead of
the aligned one, and it looked entirely plausible until the widths were measured.

A check, so it exits non-zero when something disagrees.
"""

import argparse
import json
import sys
from pathlib import Path


def measure(fasta):
    """Sequence count and the set of sequence lengths, counted rather than trusted."""
    n, widths, cur = 0, set(), 0
    for line in Path(fasta).read_text().splitlines():
        if line.startswith(">"):
            if n:
                widths.add(cur)
            n, cur = n + 1, 0
        else:
            cur += len(line.strip())
    if n:
        widths.add(cur)
    return n, widths


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--glob", default="data/*/datasets*.json",
                   help="manifests to check, relative to the working directory")
    args = p.parse_args()

    manifests = sorted(Path(".").glob(args.glob))
    if not manifests:
        sys.exit(f"no manifest matched {args.glob}")

    problems, checked, unsound = [], 0, set()
    for man in manifests:
        for ds in json.loads(man.read_text()).get("datasets", []):
            checked += 1
            before = len(problems)
            # An absolute path in a manifest is a defect, not a style: it binds the file to one
            # machine under one home. All 180 entries of data/injected/datasets.json named
            # /shared/home/agardette/bench, and this check tolerated it, so nothing said so.
            # main.nf resolves a relative path against projectDir.
            for key in ("fasta", "tax"):
                if Path(ds[key]).is_absolute():
                    problems.append(f"{man.name}:{ds['name']}: {key} is an absolute path, "
                                    f"{ds[key]}, which only resolves on one machine")
            fa = Path(ds["fasta"])
            if not fa.exists():
                problems.append(f"{man.name}:{ds['name']}: {ds['fasta']} does not exist")
                unsound.add((man.name, ds["name"]))
                continue
            n, widths = measure(fa)
            if ds.get("n_seqs") != n:
                problems.append(f"{man.name}:{ds['name']}: n_seqs says {ds.get('n_seqs')}, "
                                f"the file holds {n}")
            if len(widths) != 1:
                problems.append(f"{man.name}:{ds['name']}: not an alignment, lengths "
                                f"{min(widths)} to {max(widths)}")
            elif ds.get("aln_len") != widths.pop():
                problems.append(f"{man.name}:{ds['name']}: aln_len says {ds.get('aln_len')}")

            # One dataset can break several ways at once, so count datasets rather than
            # problems: the old arithmetic reported minus 371 sound out of 196.
            if len(problems) > before:
                unsound.add((man.name, ds["name"]))

    print(f"{checked} datasets in {len(manifests)} manifests checked, "
          f"{checked - len(unsound)} sound")
    for pb in problems:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
