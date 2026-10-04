#!/usr/bin/env python3
"""Which files does REVIEW.md never mention?

Not a measure of whether a file was reviewed -- nothing can measure that -- but of whether the
report leaves a trace of it. A file the report never names has at best been read without record,
and this review found out the hard way what that costs: bin/_timeit.py produces every second and
every memory figure in the benchmark and went unexamined through forty-eight findings, because it
was inside a coverage count that had quietly stopped being true.

So the count is replaced by a list that cannot drift: the repository's own files, checked against
the text of the report. Run it from the benchmark root.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# What a defect could live in. Data, results and the generated cells are checked by the gates in
# bin/analyses.sh rather than read, and listing them here would bury the signal.
REVIEWABLE = ("bin/", "slurm/", "modules/", "conf/", "tests/")
# Version 1 used to live outside the list above -- scripts/, sativa_epang/, data_ascii/, data_injected/
# and config.sh, 97 files that were frozen rather than reviewed. It has been removed from the
# repository, so there is nothing to exclude and nothing to print about the exclusion. The tuple is
# kept empty rather than deleted because the lesson it carried is worth a line: a coverage tool that
# silently omits a tree invites the inference that the tree is dead, and that inference was made here
# about sativa_epang/ while scripts/README.md was building RAxML from it.
FROZEN = ()
# The documents at the root carry the claims, and they were outside this list while the code was
# inside it -- so DISTRIBUTION.md could hold four aggregate figures measured wrong and PUBLISHING.md
# could open by saying nothing was public when version 1 had been pushed, with the coverage list
# reporting 92 of 92 throughout. A claim is as reviewable as a line of code.
ALSO = ("main.nf", "nextflow.config", "README.md", "RESULTS.md", "DISTRIBUTION.md",
        "PUBLISHING.md", "data/README.md")
SKIP_SUFFIX = (".pyc",)


def tracked():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.endswith(SKIP_SUFFIX):
            continue
        if line in ALSO or line.startswith(REVIEWABLE):
            yield line


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", default="REVIEW.md")
    args = p.parse_args()

    text = Path(args.report).read_text()
    files = sorted(tracked())
    frozen = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                            check=True).stdout.splitlines()
    frozen = [f for f in frozen if f.startswith(FROZEN) or f in FROZEN]
    if not files:
        sys.exit("git ls-files matched nothing reviewable; run this from the benchmark root")

    missing = []
    for f in files:
        name = Path(f).name
        # By full path or by basename: the report writes `main.nf` and `bin/verify_runs.py` both.
        if f not in text and not re.search(rf"\b{re.escape(name)}\b", text):
            missing.append(f)

    print(f"{len(files)} reviewable files, {len(files) - len(missing)} named in {args.report}")
    if frozen:
        print(f"{len(frozen)} files excluded on purpose: {', '.join(FROZEN)}")
    if missing:
        print(f"\n{len(missing)} not named anywhere in the report:")
        for f in missing:
            print(f"  {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
