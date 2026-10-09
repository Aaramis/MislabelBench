#!/usr/bin/env python3
"""Which files does REVIEW.md never mention, and which does it name that are gone?

Not a measure of whether a file was reviewed -- nothing can measure that -- but of whether the
report leaves a trace of it. A file the report never names has at best been read without record,
and this review found out the hard way what that costs: bin/_timeit.py produces every second and
every memory figure in the benchmark and went unexamined through forty-eight findings, because it
was inside a coverage count that had quietly stopped being true.

So the count is replaced by a list that cannot drift: the repository's own files, checked against
the text of the report. Run it from the benchmark root.

The check runs the other way too. A report that names a file the repository no longer has is wrong in
the direction nothing else catches: `slurm/m1_check.sh` was described here as a live assertion script
for months after it was deleted, and the paragraph saying so also said its reference data was tracked
when that had gone with version 1. Deletions are the one edit that cannot make a document stale by
touching it.
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
# Paths the report names on purpose although they are gone: version 1's tree, which several findings
# are about, and the directory whose removal broke the default manifest path and the guard probe. Each
# entry is a path the text must be free to discuss, not a file that may be missing by accident.
REMOVED = ("scripts/", "sativa_epang/", "data_ascii/", "data_injected/", "config.sh",
           "modules/local/fetchdataset/", "bin/_timeit.py",
           # Renamed, and the findings about the rename have to be able to name the old path.
           "bin/figure_candidates.py", "bin/unite_shape.py", "results/kexact_fork_only.tsv",
           # Version 1's, deleted with it; findings 14 and the plot one are about the deletion.
           "bin/plot.py", "conf/ifb.config",
           # A runtime log on the cluster, gitignored here, which is the subject of its finding.
           "slurm/node_checks.log",
           # Deleted with version 1, and the paragraph that used to call it live now says so. An entry
           # here is a record that an absence is known, which is the point: the check catches the first
           # run after a deletion, and acknowledging it is what moves the path into this tuple.
           "slurm/m1_check.sh")
# The lookbehind is the same boundary the forward check needed: without it `/usr/local/bin/sativa.py`,
# the entry point inside the comparator's container, read as a missing `bin/sativa.py` here.
PATHLIKE = re.compile(r"(?<![\w/.-])(?:bin|slurm|modules|conf|tests|data|assets)/[\w./-]*[\w]")


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

    # A basename shared by several tracked files cannot stand for any of them. Nine files here are
    # called main.nf -- the pipeline and eight modules -- so one mention of `main.nf` was certifying
    # all nine, and two of the modules had in fact never been named at all. The rule is derived from
    # the file list rather than listed by hand, so it cannot go stale the way an exemption list does.
    shared = {n for n in (Path(f).name for f in files)
              if sum(1 for g in files if Path(g).name == n) > 1}

    missing = []
    for f in files:
        name = Path(f).name
        # The path is matched with a boundary, not as a substring. `main.nf` is a suffix of every
        # `modules/local/*/main.nf`, so the substring form certified the pipeline file whenever any
        # module path appeared -- the same defect as the shared basename above, one layer in, and in
        # the fix for it. It happens to be named on its own eleven times, which is luck and not a
        # check.
        if re.search(rf"(?<![\w/.-]){re.escape(f)}(?![\w])", text):
            continue
        # By basename only when that basename belongs to one file.
        if name not in shared and re.search(rf"\b{re.escape(name)}\b", text):
            continue
        missing.append(f)

    # The other direction: a path the report names that git does not have. Only paths carrying an
    # extension are checked, since a bare directory in prose is a subject and not a reference.
    all_tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                                     check=True).stdout.splitlines())
    gone = sorted({m for m in PATHLIKE.findall(text)
                   if "." in Path(m).name and m not in all_tracked
                   and not m.startswith(REMOVED) and m not in REMOVED})

    print(f"{len(files)} reviewable files, {len(files) - len(missing)} named in {args.report}")
    if gone:
        print(f"\n{len(gone)} named in the report but not tracked:")
        for f in gone:
            print(f"  {f}")
    if frozen:
        print(f"{len(frozen)} files excluded on purpose: {', '.join(FROZEN)}")
    if missing:
        print(f"\n{len(missing)} not named anywhere in the report:")
        for f in missing:
            print(f"  {f}")
    if missing or gone:
        sys.exit(1)


if __name__ == "__main__":
    main()
