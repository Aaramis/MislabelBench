#!/usr/bin/env python3
"""Refuse to analyse anything if a run did not finish cleanly.

collect_run.py records a status of ok, error or timeout, derived from the tool's exit code and
whether it was killed on timeout. It warns on stderr and exits 0, so a failed run becomes a valid
run.json and the pipeline carries on. Nothing downstream looks at that field: the timing scripts read
wall_sec, and the detection scripts read the .mis directly and never see the run record at all. A
tool that died halfway would contribute the seconds it survived to a timing median and a truncated
.mis to a recall, as zero detections, with nothing to distinguish either from a real measurement.

So this is a gate rather than a filter in twelve places: run it before the analyses and let a bad run
stop them. All 927 runs were ok when it was written, which is why the hole had never cost anything.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--glob", default="results/*/runs/*/run.json",
                   help="run records to check, relative to the working directory")
    args = p.parse_args()

    records = sorted(Path(".").glob(args.glob))
    if not records:
        sys.exit(f"no run record matched {args.glob}")

    seen, bad = Counter(), []
    for f in records:
        try:
            d = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            bad.append(f"{f}: unreadable ({exc.__class__.__name__})")
            seen["unreadable"] += 1
            continue
        status = d.get("status", "missing")
        seen[status] += 1
        if status != "ok":
            bad.append(f"{f}: status {status}, returncode {d.get('returncode')}, "
                       f"wall {d.get('wall_sec')} s")

    print(f"{len(records)} run records checked: "
          + ", ".join(f"{n} {s}" for s, n in sorted(seen.items())))
    for b in bad[:20]:
        print(f"  {b}", file=sys.stderr)
    if bad:
        print(f"{len(bad)} run(s) did not finish cleanly; their numbers must not enter a table",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
