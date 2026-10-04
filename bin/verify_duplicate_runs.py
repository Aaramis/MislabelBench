#!/usr/bin/env python3
"""The cells that were run twice must have produced the same answer twice.

results/kaxis and results/ksweep are earlier, smaller runs of cells the 180-cell grid now also
covers: kaxis is species distance at every k and rate 0.05, ksweep is species and genus at k=10.
Both read the same injected cells from data/injected, so every one of their run directories has a
counterpart under results/grid_fork/runs produced by a different Slurm job at a different time.

That makes them a reproducibility check rather than evidence, and it is the largest one here: 42 run
directories against the determinism script's one cell produced three times. Their summaries used to
be rebuilt alongside the grid's, which was worse than useless -- four records carrying the grid's own
numbers, which a reader could take for independent measurements of the same quantity.

A pair that disagrees means the pipeline is not deterministic across jobs, which would invalidate
every table here, so this exits non-zero rather than reporting.
"""

import hashlib
import sys
from pathlib import Path

PAIRS = [("results/kaxis/runs", "results/grid_fork/runs"),
         ("results/ksweep/runs", "results/grid_fork/runs")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    total = same = 0
    problems = []
    for side, main in PAIRS:
        side_dir = Path(side)
        if not side_dir.is_dir():
            continue
        for d in sorted(side_dir.iterdir()):
            if not d.is_dir():
                continue
            a = d / f"{d.name}.mis"
            b = Path(main) / d.name / f"{d.name}.mis"
            if not a.exists():
                problems.append(f"{a} is missing")
                continue
            if not b.exists():
                problems.append(f"{d.name} has no counterpart under {main}")
                continue
            total += 1
            if digest(a) == digest(b):
                same += 1
            else:
                problems.append(f"{d.name} differs between {side} and {main}")

    # A check that compared nothing must not report success, which four gates in this repository
    # once did.
    if not total:
        sys.exit("no run directory under results/kaxis or results/ksweep had a counterpart to "
                 "compare; run this from the benchmark root")

    print(f"{total} cells were run twice in separate jobs, {same} produced a byte-identical .mis")
    for p in problems[:10]:
        print(f"  {p}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} problem(s): the pipeline is not reproducing across jobs")


if __name__ == "__main__":
    main()
