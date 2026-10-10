#!/usr/bin/env python3
"""The same sequences at a narrower alignment, for measuring how memory scales with the width.

The memory law was stated per sequence at the one width every archaeal alignment here has, 1 478
columns, and the width term was deduced from what EPA-ng stores rather than measured. This keeps the
first N columns of an alignment and copies the taxonomy unchanged, so that the fork can be run on the
same 2 023 sequences at several widths and the per-process peak read against N. The first N columns
and not a sample: the tree only has to be buildable, and a prefix is the choice with nothing to seed.
"""

import argparse
import shutil
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fasta", required=True)
    p.add_argument("--tax", required=True)
    p.add_argument("--columns", type=int, required=True)
    p.add_argument("--prefix", required=True, help="writes <prefix>.fasta and <prefix>.tax")
    args = p.parse_args()

    records = []
    name, seq = None, []
    for line in Path(args.fasta).read_text().splitlines():
        if line.startswith(">"):
            if name is not None:
                records.append((name, "".join(seq)))
            name, seq = line, []
        else:
            seq.append(line.strip())
    if name is not None:
        records.append((name, "".join(seq)))
    if not records:
        raise SystemExit(f"{args.fasta}: no sequence")
    widths = {len(s) for _, s in records}
    if len(widths) != 1:
        raise SystemExit(f"{args.fasta}: not an alignment, widths {sorted(widths)}")
    width = widths.pop()
    if not 1 <= args.columns <= width:
        raise SystemExit(f"--columns {args.columns} is not within 1..{width}")

    out = Path(args.prefix + ".fasta")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{n}\n{s[:args.columns]}\n" for n, s in records))
    shutil.copyfile(args.tax, args.prefix + ".tax")
    print(f"{len(records)} sequences, {width} -> {args.columns} columns, {out}")


if __name__ == "__main__":
    main()
