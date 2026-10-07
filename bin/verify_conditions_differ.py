#!/usr/bin/env python3
"""A knob that is an independent variable must change the answer; one that is not must not.

`verify_fold_counts.py` states the hazard this closes the other half of: a condition's `folds` field
in run.json "is the declaration and not the measurement; it would read 5 just as happily if the
environment variable had never reached the container". It then checks the fold *count* against the
tool's own log line. Nothing checked the fold *order*, which is the knob two of the five grid
conditions turn, and whose published result is that it changes detection by nothing -- a null result
that an option never reaching the container would produce just as well.

So the check is on the output rather than on the declaration, in both directions:

  two conditions differing only in fold count or fold order must disagree on at least one cell,
  or the knob did not reach the tool

  two conditions differing only in the thread count must flag the same sequences at the same ranks,
  because threading is not supposed to be an independent variable at all

The second is the stronger statement and it holds with one exception worth stating rather than
tolerating silently: the fork's confidence column moves in the last digit. At 2 023 sequences, 93
flags, one of them reads 0.993 at one thread and 0.992 at eight and sixteen -- same sequence, same
rank, same proposed label. That is summation order under threading, and it is why this compares the
flag set and the rank rather than the bytes. Upstream is byte-identical at 1, 8 and 16 threads.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

UPSTREAM = re.compile(r"^upstream_(\w+?)_T(\d+)$")
FORK = re.compile(r"^epang_T(\d+)_K(\d+|exact)(_tree)?$")


def spec(condition):
    """(impl, threads, folds, fold order) from the condition's name, which is where the harness
    puts them too -- nextflow.config builds the meta from this same name."""
    m = UPSTREAM.match(condition)
    if m:
        return ("sativa", int(m.group(2)), None, None)
    m = FORK.match(condition)
    if m:
        return ("sativaepang", int(m.group(1)), m.group(2), "tree" if m.group(3) else "default")
    return None


def flags(mis):
    """Flagged sequence to its mislabelled rank. The confidence is deliberately not included."""
    out = {}
    for line in Path(mis).read_text().splitlines():
        if line.startswith(";") or not line.strip():
            continue
        f = line.split("\t")
        out[f[0]] = f[1]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs-glob", default="results/*/runs/*")
    args = p.parse_args()

    cells = defaultdict(dict)
    for d in sorted(Path().glob(args.runs_glob)):
        mis = d / (d.name + ".mis")
        if not mis.is_file() or d.name.count("__") != 2:
            continue
        dataset, condition, rep = d.name.split("__")
        if spec(condition):
            cells[(str(d.parent), dataset, rep)][condition] = mis

    problems = []
    knob_pairs, thread_pairs = defaultdict(lambda: [0, 0]), 0
    for key, conds in sorted(cells.items()):
        for a, b in ((a, b) for a in conds for b in conds if a < b):
            sa, sb = spec(a), spec(b)
            if sa[0] != sb[0]:
                continue
            if sa[1] != sb[1] and (sa[2], sa[3]) == (sb[2], sb[3]):
                thread_pairs += 1
                fa, fb = flags(conds[a]), flags(conds[b])
                if fa != fb:
                    moved = len(set(fa) ^ set(fb))
                    ranks = sum(1 for s in set(fa) & set(fb) if fa[s] != fb[s])
                    problems.append(f"{key[1]}/{key[2]}: {a} and {b} differ only in threads, yet "
                                    f"{moved} sequence(s) are flagged by one and not the other and "
                                    f"{ranks} differ in rank")
            elif sa[1] == sb[1] and (sa[2], sa[3]) != (sb[2], sb[3]):
                seen = knob_pairs[(a, b)]
                seen[0] += 1
                if conds[a].read_bytes() != conds[b].read_bytes():
                    seen[1] += 1

    for (a, b), (n, differing) in sorted(knob_pairs.items()):
        if differing == 0:
            problems.append(f"{a} and {b} declare different batching and produced the same output "
                            f"on all {n} cells: the knob did not reach the tool")

    print(f"{thread_pairs} thread pairs checked for the same flags, {len(knob_pairs)} batching pairs "
          f"over {sum(n for n, _ in knob_pairs.values())} cells checked for any difference; "
          f"{len(problems)} problem(s)")
    for (a, b), (n, differing) in sorted(knob_pairs.items()):
        print(f"  {a} vs {b}: {differing}/{n} cells differ")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} condition pair(s) the output contradicts")


if __name__ == "__main__":
    main()
