#!/usr/bin/env python3
"""Every Nextflow trace must be named in the document that enumerates them, with its row count.

results/pipeline_info/README.md exists to say which traces there are and where the gaps in them
are -- "the gaps, which are real and worth stating rather than leaving to be noticed". It listed 13
files while the directory held 41, so 27 files and 620 task rows, more than half as many again as
those listed, were in the directory and in no document. The table had been written once and the
directory kept growing, which is the same way the review report's own coverage table went stale
twice.

Two checks, both mechanical:

  every trace-*.txt in the directory is named somewhere in the README
  every row count the README states for a file or a group is the sum those files actually hold

A row count is read from a table row: the first cell names one or more files in backticks, the
second is the number. A group's number is checked against the group's total, which is why the
grouped rows at the end can stay grouped.
"""

import argparse
import re
import sys
from pathlib import Path

FILE_IN_CELL = re.compile(r"`(trace-[^`]+\.txt)`")


def rows_in(path):
    """Task rows, which is every line after the header."""
    return len([l for l in path.read_text().splitlines()[1:] if l.strip()])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="results/pipeline_info")
    args = p.parse_args()
    d = Path(args.dir)
    readme = d / "README.md"
    if not readme.exists():
        sys.exit(f"{readme} does not exist; nothing enumerates the traces")

    text = readme.read_text()
    traces = sorted(d.glob("trace-*.txt"))
    if not traces:
        sys.exit(f"no trace-*.txt under {d}; this cannot be a results directory")

    problems = [f"{t.name} is in {d} and named nowhere in {readme.name}"
                for t in traces if t.name not in text]

    checked_rows = 0
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        named = FILE_IN_CELL.findall(cells[0])
        if not named or not cells[1].isdigit():
            continue
        want = int(cells[1])
        have = 0
        for name in named:
            f = d / name
            if not f.exists():
                problems.append(f"{readme.name} names {name}, which is not in {d}")
                continue
            have += rows_in(f)
        checked_rows += 1
        if have != want:
            problems.append(f"{readme.name}: {', '.join(named)} says {want} rows, the files hold "
                            f"{have}")

    # "checked", not "all named": the fourth gate of mine to have claimed a result above the lines
    # that denied it. The summary line gets written before the failure path is exercised, every time,
    # so the rule is now to write it after.
    print(f"{len(traces)} traces and {checked_rows} row counts checked against {readme.name}; "
          f"{len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} trace(s) or count(s) the document and the directory disagree on")


if __name__ == "__main__":
    main()
