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

The seconds are reported too, for the opposite reason. Byte-identity is only evidence of
reproducibility if the two runs are genuinely separate, and the thing that shows they are is that
they do not share a wall clock: no pair of the 42 does, and the widest is 39 % apart. The
supplementary states that spread and nothing here produced it -- it was computed by hand once -- so
it is printed with the identity count it qualifies.
"""

import hashlib
import json
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

    timed = []
    for side, main in PAIRS:
        for d in sorted(Path(side).glob("*")):
            other = Path(main) / d.name
            try:
                wa = json.loads((d / "run.json").read_text())["wall_sec"]
                wb = json.loads((other / "run.json").read_text())["wall_sec"]
            except (OSError, KeyError, ValueError):
                continue
            if wa and wb:
                timed.append((d.name, max(wa, wb), min(wa, wb)))
    shared = sum(1 for _, hi, lo in timed if hi == lo)
    print(f"{total} cells were run twice in separate jobs, {same} produced a byte-identical .mis")
    if timed:
        name, hi, lo = max(timed, key=lambda r: r[1] / r[2])
        print(f"{len(timed)} of those pairs carry both wall clocks, {shared} share one, and the "
              f"widest is {hi:.1f} s against {lo:.1f} s, {100 * (hi - lo) / lo:.0f} % apart "
              f"({name})")
    for p in problems[:10]:
        print(f"  {p}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} problem(s): the pipeline is not reproducing across jobs")


if __name__ == "__main__":
    main()
