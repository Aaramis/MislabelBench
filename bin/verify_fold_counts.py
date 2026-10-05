#!/usr/bin/env python3
"""The fold count a condition declares must be the one the tool actually used.

Four of the benchmark's conditions differ only in how the leave-one-out is batched --
epang_T8_K25, epang_T8_K5 and their _tree variants -- so every comparison between them, and the
whole fold-split ceiling in the scaling report, rests on K5 having run five folds and K25
twenty-five. Nothing checked it. `folds` in run.json is copied from the condition's meta, which is
the declaration and not the measurement; it would read 5 just as happily if the environment
variable had never reached the container. The tool's own line -- "wrote N fold tasks" -- is the
only independent evidence in the repository, and it was never compared to anything.

Three invariants, over every fork run that has a log:

  the condition name's K, the run.json folds field, and the tool's reported count all agree
  a staged run's shards partition that count exactly, summing to K with no index missing
  a run with no reported count is named rather than passed over

Upstream runs are skipped: SATIVA 0.9.3 has no fold batching, which is the modification being
benchmarked.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

COND_K = re.compile(r"__epang_T\d+_K(\d+)")
# epang_T8_Kexact is the strict leave-one-out and names no number, so the pattern above skipped it --
# silently, and it is the one condition where the fold count IS the claim: one sequence per fold is
# what makes it separate the engine from the fold scheme. nextflow.config declares folds: 999999 and
# the tool caps at min(folds, leaves), verified in its source, so the count to expect is the cell's
# own sequence count, which run.json records as n_seqs.
COND_EXACT = re.compile(r"__epang_T\d+_Kexact")
WROTE = re.compile(r"wrote (\d+) fold tasks")
PLACED = re.compile(r"placed \d+/(\d+) folds")
SHARD = re.compile(r"_shard(\d+)of(\d+)\.stage\.log$")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="results")
    args = p.parse_args()
    root = Path(args.results)
    # `matched` counts logs that belong to a condition this gate covers; `checked` counts those it
    # could actually compare. They differ when a run is unusable -- a Kexact run with no n_seqs, say --
    # and conflating them made a tree of nothing but unusable runs report "no fork run log found",
    # which is the empty-tree guard swallowing the finding it exists beside.
    problems, checked, shard_runs, matched = [], 0, 0, 0

    for log in sorted(root.rglob("*__epang_*__rep*/*.log")):
        cell = log.parent.name
        if SHARD.search(log.name):
            continue
        m = COND_K.search(cell)
        exact = COND_EXACT.search(cell)
        if not m and not exact:
            continue
        if exact:
            # The expectation comes from the data, not from the condition's name: one fold per
            # sequence. A run.json that records n_seqs is required, since without it there is
            # nothing to check against and silence is what this whole gate exists to prevent.
            rj = log.parent / "run.json"
            n_seqs = json.loads(rj.read_text()).get("n_seqs") if rj.exists() else None
            matched += 1
            if not n_seqs:
                problems.append(f"{log}: strict leave-one-out with no n_seqs to check against")
                continue
            want = int(n_seqs)
        else:
            matched += 1
            want = int(m.group(1))
        text = log.read_text(errors="replace")
        got = WROTE.search(text) or PLACED.search(text)
        # A stage log of the reference or scoring stage never mentions folds, and that is correct;
        # only a log that is a whole run, or a placement stage, is expected to.
        if not got:
            if log.name.endswith(".stage.log"):
                continue
            problems.append(f"{log}: no fold count reported by the tool")
            continue
        checked += 1
        if int(got.group(1)) != want:
            problems.append(f"{log}: tool used {got.group(1)} folds, condition says {want}")
        # The declared field is checked only where a declaration can be compared: for Kexact it
        # holds the uncapped 999999 and the tool's count is the capped one, so they differ by design.
        if not exact:
            rj = log.parent / "run.json"
            if rj.exists():
                declared = json.loads(rj.read_text()).get("folds")
                if declared is not None and int(declared) != want:
                    problems.append(f"{rj}: records folds={declared}, condition says {want}")

    # Staged runs: the shards must partition the fold count rather than each run all of it, which
    # is what the scaling report's ceiling is computed against.
    by_cell = defaultdict(dict)
    for log in sorted(root.rglob("*/staged/*/looplace_shard*.stage.log")):
        s = SHARD.search(log.name)
        i, n = int(s.group(1)), int(s.group(2))
        got = PLACED.search(log.read_text(errors="replace"))
        if not got:
            problems.append(f"{log}: a placement shard that reports no folds")
            continue
        by_cell[(log.parent, n)][i] = int(got.group(1))

    for (cell, n), shards in sorted(by_cell.items()):
        shard_runs += 1
        m = COND_K.search(cell.name)
        if not m:
            continue
        want = int(m.group(1))
        if sorted(shards) != list(range(n)):
            problems.append(f"{cell}: shards {sorted(shards)} of {n} expected")
        elif sum(shards.values()) != want:
            problems.append(f"{cell}: shards place {sum(shards.values())} folds, condition "
                            f"says {want}")

    if not matched:
        sys.exit(f"no fork run log found under {root}/; run this from the benchmark root")
    # "checked" and not "agree": the count is of runs examined, and saying they agree while the
    # lines below name the ones that do not is how a gate ends up read as a pass.
    print(f"{checked} fork runs checked against their condition's fold count, "
          f"{shard_runs} staged runs against its partition; {len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} fold-count problem(s): a condition did not run what it claims")


if __name__ == "__main__":
    main()
