#!/usr/bin/env python3
"""Every Nextflow trace must be named in results/pipeline_info/README.md, with its row count.

Three checks:

  every trace-*.txt in the directory is named in the README
  every row count the README states for a file or a group is the sum those files hold
  every run collected since --runs-from is named by some trace

The last one reads in the other direction. The first two start from the directory, so a trace that
never left the cluster is invisible to them. Runs from before 2026-10-03 shared one trace name and
overwrote each other, so they are not expected to be traced.

A row count is read from a table row. The first cell names one or more files in backticks, the second
is the number.
"""

import argparse
import json
import re
import sys
from pathlib import Path

FILE_IN_CELL = re.compile(r"`(trace-[^`]+\.txt)`")
CELL_IN_TRACE = re.compile(r"\(([^()]+)\)")


def rows_in(path):
    """Task rows, which is every line after the header."""
    return len([l for l in path.read_text().splitlines()[1:] if l.strip()])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="results/pipeline_info")
    p.add_argument("--runs-glob", default="results/*/runs/*/run.json")
    # The day per-tag trace naming was in place for every job. Before it, jobs shared one trace name.
    p.add_argument("--runs-from", default="2026-10-03")
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
        named = FILE_IN_CELL.findall(cells[0])
        if len(cells) < 2 or not named or not cells[1].isdigit():
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

    # The other direction: a run whose trace never arrived. The trace names each task's cell as
    # "PROCESS (dataset/condition/repN)", which is exactly what run.json records in three fields.
    cells = set()
    for t in traces:
        cells.update(CELL_IN_TRACE.findall(t.read_text()))
    checked_runs = 0
    for rj in sorted(Path().glob(args.runs_glob)):
        rec = json.loads(rj.read_text())
        if str(rec.get("collected_at", ""))[:10] < args.runs_from:
            continue
        checked_runs += 1
        key = f"{rec['dataset']}/{rec['condition']}/rep{rec['rep']}"
        if key not in cells:
            problems.append(f"{key} was collected on {rec['collected_at'][:10]} and no trace in {d} "
                            f"names it; its job's trace is probably still on the cluster")

    print(f"{len(traces)} traces, {checked_rows} row counts "
          f"checked against {readme.name}, and {checked_runs} runs since {args.runs_from} for a "
          f"trace that names them; {len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} trace(s) or count(s) the document and the directory disagree on")


if __name__ == "__main__":
    main()
