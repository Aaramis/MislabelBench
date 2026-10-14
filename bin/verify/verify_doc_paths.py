#!/usr/bin/env python3
"""Every repository path or relative link a document names must exist.

Checks the markdown files at the top level, under docs/, results/ and data/. A `code span` that begins
with a repository directory (bin/, slurm/, data/, results/, docs/, assets/, tests/, modules/, conf/) or
names a top-level file is looked up. Spans with <placeholders>, $variables or * are globs or templates:
a glob must match something, the others are skipped. A markdown link to a relative target is looked up
from the document's own folder.
"""
import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRS = ("bin/", "slurm/", "data/", "results/", "docs/", "assets/", "tests/", "modules/", "conf/")
TOP = {p.name for p in ROOT.iterdir() if p.is_file() and not p.name.startswith(".")}
SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")


def documents():
    yield from ROOT.glob("*.md")
    for d in ("docs", "results", "data"):
        yield from (ROOT / d).glob("*.md")
    yield from (ROOT / "results" / "pipeline_info").glob("*.md")


def exists(rel):
    if any(c in rel for c in "<>$"):
        return True
    if "*" in rel:
        return bool(glob.glob(str(ROOT / rel)))
    return (ROOT / rel).exists()


def main():
    problems, checked = [], 0
    for doc in sorted(documents()):
        text = doc.read_text()
        name = doc.relative_to(ROOT)
        for span in SPAN.findall(text):
            token = span.split()[0].rstrip(".,;:")
            if token.startswith(DIRS) or token in TOP:
                checked += 1
                if not exists(token):
                    problems.append(f"{name}: `{token}` does not exist")
        for target in LINK.findall(text):
            if re.match(r"[a-z]+:|#", target):
                continue
            checked += 1
            if not (doc.parent / target.split("#")[0]).exists():
                problems.append(f"{name}: link {target} does not resolve")
    print(f"{checked} paths and links checked in the documents; {len(problems)} problem(s)")
    for p in problems:
        print(f"  {p}", file=sys.stderr)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
