#!/usr/bin/env python3
"""A reference in the review report must point at something.

REVIEW.md is this repository's deliverable for the final read-through, and it cross-references
itself constantly: a finding says "the same shape as finding 75" and a reader follows it. A
reference to a number that does not exist, or to one that appears twice, costs the reader the time
it takes to discover there is nothing there -- and it is the easiest thing in the document to get
wrong, because findings are appended and numbered by hand.

Written after producing thirteen dangling links in the decision log at once: `[[d147-...]]` in a
document whose headings are `## D147.` and which has no such anchors. Nobody would have noticed
until someone followed one.

Four things, all mechanical:

  every finding number is used once, and the sequence has no gaps
  every "finding N" reference names a finding that exists
  no wiki-style [[link]] survives, since neither document defines anchors for them
  with --decisions, every "Dnnn" in the decision log has a heading of its own
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def git_ls(*patterns):
    """Tracked files, so an untracked scratch file cannot change a published count."""
    out = subprocess.run(["git", "ls-files", *patterns], capture_output=True, text=True)
    return [f for f in out.stdout.splitlines() if f]

HEADING = re.compile(r"^\*\*(\d+)\. ", re.M)
REFERENCE = re.compile(r"\bfindings?\s+(\d+)(?:\s*,\s*(\d+))*(?:\s+and\s+(\d+))?", re.I)
WIKI = re.compile(r"\[\[[^\]]*\]\]")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", default="REVIEW.md")
    p.add_argument("--decisions", help="the decision log, checked only if given: it lives outside "
                                       "this repository, so a clone must pass without it")
    args = p.parse_args()

    text = Path(args.report).read_text()
    nums = [int(m) for m in HEADING.findall(text)]
    problems = []

    if not nums:
        sys.exit(f"{args.report} has no numbered findings; the pattern or the file is wrong")

    seen = set()
    for n in nums:
        if n in seen:
            problems.append(f"{args.report}: finding {n} is numbered twice")
        seen.add(n)
    gaps = sorted(set(range(min(nums), max(nums) + 1)) - seen)
    if gaps:
        problems.append(f"{args.report}: no finding numbered {gaps[:5]}")

    for match in REFERENCE.finditer(text):
        for g in match.groups():
            if g and int(g) not in seen:
                problems.append(f"{args.report}: refers to finding {g}, which does not exist")

    # Inside backticks a wiki link is a quotation, not a link: finding 109 has to be able to show
    # the form it is reporting. Code spans are stripped before looking, which is also why the report
    # may name a dangling link without tripping the gate that found it.
    for doc in [args.report] + ([args.decisions] if args.decisions else []):
        prose = re.sub(r"`[^`]*`", "", Path(doc).read_text())
        for link in WIKI.findall(prose):
            problems.append(f"{doc}: {link} points at an anchor neither document defines")

    checked = len(nums)
    if args.decisions:
        dec = Path(args.decisions).read_text()
        headings = {m for m in re.findall(r"^## D(\d+)\.", dec, re.M)}
        for ref in sorted({m for m in re.findall(r"\bD(\d{1,3})\b", dec)}):
            if ref not in headings:
                problems.append(f"{args.decisions}: refers to D{ref}, which has no entry")
        checked += len(headings)

    # The report's own coverage table, recomputed from the repository. It went stale twice before
    # anyone noticed: it once claimed four modules where there were eight and 42 bin/ scripts where
    # there were 55, and a review stating a coverage it no longer has is worse than one stating none.
    # The labels are matched loosely because the table's left column is prose; what is pinned is the
    # number beside each.
    counted = {
        "findings in this report": len(seen),
        "`bin/` scripts": len(git_ls("bin/*.py", "bin/*.sh")),
        "`slurm/` job scripts": len(git_ls("slurm/*.sh")),
        "`modules/local/`": len([d for d in Path("modules/local").iterdir() if d.is_dir()])
                            if Path("modules/local").is_dir() else None,
        "dataset manifests": len([f for f in git_ls() if re.search(r"datasets.*\.json$", f)]),
        "run records": len([f for f in git_ls() if re.search(r"runs/.*/run\.json$", f)]),
        "result tables": len([f for f in git_ls("results/*") if f.count("/") == 1]),
        "tests over the scripts": sum(Path(f).read_text().count("def test_")
                                      for f in git_ls("tests/*.py")),
    }
    for label, n in counted.items():
        if n is None:
            continue
        row = re.search(rf"^\|\s*{re.escape(label)}[^|]*\|\s*(\d+)\s*\|", text, re.M)
        if not row:
            problems.append(f"{args.report}: no coverage row starting '{label}'")
        elif int(row.group(1)) != n:
            problems.append(f"{args.report}: '{label}' says {row.group(1)}, repository has {n}")

    print(f"{checked} numbered entries and {len(counted)} coverage counts checked, "
          f"{len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        # Named for what it found rather than for what the script is mostly about: this exits on a
        # drifted coverage count as readily as on a dangling reference, and a summary line that says
        # the wrong one is the third habit of mine this review has had to correct.
        sys.exit(f"{len(problems)} problem(s) in {args.report}: a reference pointing at nothing, "
                 f"or a stated count the repository contradicts")


if __name__ == "__main__":
    main()
