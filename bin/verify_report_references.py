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
import sys
from pathlib import Path

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

    print(f"{checked} numbered entries checked, {len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} reference(s) point at nothing")


if __name__ == "__main__":
    main()
