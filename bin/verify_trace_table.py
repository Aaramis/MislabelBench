#!/usr/bin/env python3
"""Every Nextflow trace must be named in the document that enumerates them, with its row count.

results/pipeline_info/README.md exists to say which traces there are and where the gaps in them
are -- "the gaps, which are real and worth stating rather than leaving to be noticed". It listed 13
files while the directory held 41, so 27 files and 620 task rows, more than half as many again as
those listed, were in the directory and in no document. The table had been written once and the
directory kept growing, which is the same way the review report's own coverage table went stale
twice.

Four checks, all mechanical:

  every trace-*.txt in the directory is named somewhere in the README
  every row count the README states for a file or a group is the sum those files actually hold
  the two totals the prose states for each table are that table's own
  every recent run is named by some trace, which is the only one that reads in that direction

The third was added because the first two left the prose free to drift, and it had: the sentence
introducing the second table said 27 files and 620 rows when the table listed 30 and 626, and quoted
719 rows for the first table when it listed 721. Numbers in prose are checked here or they rot.

The fourth closes the gap the first three share: all of them read the directory and ask what the
document says about it, so a trace that never left the cluster is invisible to every one of them. The
k=3 Kexact run's trace sat in results/grid_fork/pipeline_info/ there while the commit carrying its
result said every gate was green. It is "recent" rather than "every" because the jobs collected on
2026-10-02 wrote into one outdir under one trace name and overwrote each other: 574 of those 875 runs
are in no trace and never can be, which is the collision per-tag naming then fixed. From 2026-10-03
on, every run is named -- 242 of them -- so that is where the check starts.

A row count is read from a table row: the first cell names one or more files in backticks, the
second is the number. A group's number is checked against the group's total, which is why the
grouped rows at the end can stay grouped.
"""

import argparse
import json
import re
import sys
from pathlib import Path

FILE_IN_CELL = re.compile(r"`(trace-[^`]+\.txt)`")
CELL_IN_TRACE = re.compile(r"\(([^()]+)\)")
# The prose totals, each naming the table it summarises: the first table's row count, and the second
# table's file and row counts.
FIRST_TOTAL = re.compile(r"as the ([\d\u202f ]+) listed above")
SECOND_TOTAL = re.compile(r"which is ([\d\u202f ]+) files and \*\*([\d\u202f ]+) task rows\*\*")


def number(s):
    return int(s.replace("\u202f", "").replace(" ", ""))


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
    # Per table, so the prose totals below can be checked against the table each one summarises. A
    # table ends at the first line that is not one of its rows.
    tables, cur = [], None
    for line in text.splitlines() + [""]:
        if not line.startswith("|"):
            if cur:
                tables.append(cur)
            cur = None
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
        cur = cur or {"files": 0, "rows": 0}
        cur["files"] += len(named)
        cur["rows"] += have

    checked_totals = 0
    if len(tables) != 2:
        problems.append(f"{readme.name}: {len(tables)} table(s) of traces, expected 2; the prose "
                        f"totals cannot be checked")
    else:
        for label, pattern, want_from, got_from in (
                ("first", FIRST_TOTAL, lambda m: (("rows", number(m.group(1))),), tables[0]),
                ("second", SECOND_TOTAL, lambda m: (("files", number(m.group(1))),
                                                    ("rows", number(m.group(2)))), tables[1])):
            m = pattern.search(text)
            if not m:
                problems.append(f"{readme.name}: no prose total matching {pattern.pattern}")
                continue
            for field, want in want_from(m):
                checked_totals += 1
                if want != got_from[field]:
                    problems.append(f"{readme.name}: the prose says {want} {field} for the {label} "
                                    f"table, which holds {got_from[field]}")

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

    # "checked", not "all named": the fourth gate of mine to have claimed a result above the lines
    # that denied it. The summary line gets written before the failure path is exercised, every time,
    # so the rule is now to write it after.
    print(f"{len(traces)} traces, {checked_rows} row counts and {checked_totals} prose totals "
          f"checked against {readme.name}, and {checked_runs} runs since {args.runs_from} for a "
          f"trace that names them; {len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} trace(s) or count(s) the document and the directory disagree on")


if __name__ == "__main__":
    main()
