#!/usr/bin/env python3
"""Every regenerable dataset comes back byte for byte, in a tree that is not this one.

data/README.md's central claim is that what is not committed is regenerable, "and that claim is
checked rather than asserted". It was asserted. The check behind it was run by hand, from a fresh
clone, with nothing but the generators -- and a fresh clone is exactly where it cannot work for two
of the four experiments: the clade and simulated cells are committed, every generator skips a cell
whose .tax is already there, so for 103 of the 481 files the comparison compared git's content to
itself. Their reproducibility was unmeasured until this script measured it.

It also hid a defect of its own. The 225 cell alignments are symlinks, and the claim made for them
was that "the link is remade and points where it should". The link was not remade -- `ln -sf` sat
inside the skip guard -- and the 45 committed ones pointed at
/Users/auguste/Documents/git/sativa-epang-benchmark, so every clone on another machine had 45
dangling alignments that no documented command repaired. A link is compared here by its target, which
is what makes that visible.

So: build a root holding only what is kept, run the four generators into it, and compare every file
they write against this tree's. Nothing in this tree is touched -- the kept inputs are copied rather
than linked, because make_foreign.sh writes into data/bacteria on the branch that aligns the donors.

    bin/verify_regeneration.py [--keep]

warn.txt is excluded: it is each generator's stderr, documented as not kept, and its content depends
on which cells were already there.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GENERATED = ("injected", "foreign", "clade", "simulated")
GENERATORS = ("make_grid.sh", "make_foreign.sh", "make_clade.sh", "make_simulation.sh")
KEPT = ("data/gtdb", "data/bacteria")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content(path):
    """A link is its target, a file is its bytes. Comparing a link's contents compares the file it
    points at to itself, which is how 225 of the 235 alignments passed while 45 were dangling."""
    return ("link", os.readlink(path)) if path.is_symlink() else ("file", digest(path))


def files_under(root, sub):
    d = root / "data" / sub
    return {p.relative_to(root): p for p in d.rglob("*")
            if (p.is_symlink() or p.is_file()) and p.name != "warn.txt"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--keep", action="store_true", help="leave the scratch tree for inspection")
    args = p.parse_args()

    here = Path(".").resolve()
    for sub in KEPT:
        if not (here / sub).is_dir():
            sys.exit(f"{sub} is not here; run this from the root of a working copy")

    scratch = Path(tempfile.mkdtemp(prefix="regen_"))
    try:
        for name in ("bin", "slurm"):
            os.symlink(here / name, scratch / name)
        (scratch / "data").mkdir()
        for sub in KEPT:
            shutil.copytree(here / sub, scratch / sub)

        env = dict(os.environ, BENCH_ROOT=str(scratch))
        for g in GENERATORS:
            r = subprocess.run(["bash", str(here / "slurm" / g)], env=env,
                               capture_output=True, text=True)
            if r.returncode != 0:
                print(r.stdout[-2000:], r.stderr[-2000:], file=sys.stderr)
                sys.exit(f"{g} exited {r.returncode}; nothing can be compared")

        same = different = only_here = only_there = 0
        problems = []
        for sub in GENERATED:
            mine, theirs = files_under(here, sub), files_under(scratch, sub)
            for rel in sorted(mine.keys() | theirs.keys()):
                if rel not in theirs:
                    only_here += 1
                    problems.append(f"{rel}: here but not regenerated")
                elif rel not in mine:
                    only_there += 1
                    problems.append(f"{rel}: regenerated but not here")
                elif content(mine[rel]) == content(theirs[rel]):
                    same += 1
                else:
                    different += 1
                    kind, mine_c = content(mine[rel])
                    _, their_c = content(theirs[rel])
                    problems.append(f"{rel}: {kind} differs, {mine_c} here against {their_c}")

        print(f"{same + different + only_here + only_there} regenerable files compared against a "
              f"tree built from the kept inputs alone: {same} identical, {different} differing, "
              f"{only_here} missing from it, {only_there} missing from here")
        for pb in problems[:10]:
            print(f"  {pb}", file=sys.stderr)
        if problems:
            sys.exit(f"{len(problems)} regenerable file(s) do not come back as they are here")
    finally:
        if args.keep:
            print(f"scratch tree left at {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
