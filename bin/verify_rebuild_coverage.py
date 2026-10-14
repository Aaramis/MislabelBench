#!/usr/bin/env python3
"""Every table in results/ must have been rewritten by the run of analyses.sh that calls this.

analyses.sh opens with "one command rebuilds every committed result, and a change to any script
shows up as a diff". That claim has now been false three times, and each time it was found by
hand: three version 1 tables and four side-grid summaries, then the simulated set's
two detection laws and its paired comparison. The last of those hid a worse problem
than a stale file -- README published figures the record it cites no longer held -- and it
surfaced only because a number that should have moved did not.

This is the check that was missing. The boundary is exact and needs no list to maintain: files
directly under results/ are tables derived by bin/, everything deeper is evidence copied from the
cluster -- run directories, Nextflow traces, the staged timing directories. So every file at that
top level must be newer than the marker analyses.sh wrote when it started.

A table that is not rebuilt is reported rather than tolerated, including when the reason is
legitimate -- an experiment whose second arm is still running on the cluster leaves its tables at
the previous arm's values. That is precisely when nothing here should be quoted, so the script
exits non-zero and names them.
"""

import argparse
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--marker", required=True,
                   help="file stamped when the rebuild started; tables must be newer")
    p.add_argument("--results", default="results")
    args = p.parse_args()

    marker = Path(args.marker)
    if not marker.exists():
        sys.exit(f"no marker at {marker}: analyses.sh must stamp one before its first step")
    started = marker.stat().st_mtime

    tables = sorted(f for f in Path(args.results).iterdir()
                    if f.is_file() and not f.name.startswith("."))
    stale = [f for f in tables if f.stat().st_mtime < started]

    # An empty results/ would otherwise pass silently, which is the shape of gate this repository
    # has caught reporting success four times.
    if not tables:
        sys.exit(f"no table directly under {args.results}/; this cannot be a benchmark root")

    print(f"{len(tables)} tables, {len(tables) - len(stale)} rebuilt by this run")
    for f in stale:
        print(f"  not rebuilt: {f}", file=sys.stderr)
    if stale:
        sys.exit(f"{len(stale)} committed table(s) no step of this script produces, or whose step "
                 f"was skipped; they still hold whatever they held before")


if __name__ == "__main__":
    main()
