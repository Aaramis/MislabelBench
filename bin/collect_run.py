#!/usr/bin/env python3
"""Assemble one run.json from a tool run, in the shape the analysis scripts already read.

This is the measuring half of what scripts/02_bench.py used to do; the running half is now a
Nextflow process, because sativa and sativa-epang pin different python minor versions and
cannot share an environment. count_mislabels and parse_sativa_log are kept byte for byte so
the records stay comparable with the v1 results.
"""

import argparse
import json
import re
import socket
import sys
from datetime import datetime
from pathlib import Path

TIMING_RE = re.compile(
    r"elapsed time:\s*([\d.]+)\s*seconds\s*\(([\d.]+)s reftree,\s*([\d.]+)s leave-one-out\)"
)


def count_mislabels(mis_path):
    """Number of flagged sequences in a SATIVA .mis file (';' lines are the header)."""
    if not mis_path.exists():
        return None
    n = 0
    with mis_path.open() as handle:
        for line in handle:
            if line.strip() and not line.startswith(";"):
                n += 1
    return n


def parse_sativa_log(log_path):
    """Pull SATIVA's own phase timings out of its log."""
    if not log_path.exists():
        return {}
    match = TIMING_RE.search(log_path.read_text(errors="replace"))
    if not match:
        return {}
    total, reftree, l1out = (float(g) for g in match.groups())
    return {"sativa_total_sec": total, "reftree_sec": reftree, "l1out_sec": l1out}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--meta", required=True, help="JSON describing the condition")
    p.add_argument("--timing", required=True, help="timing.json from _timeit.py")
    p.add_argument("--mis", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--out", default="run.json")
    args = p.parse_args()

    record = json.loads(Path(args.meta).read_text())
    measured = json.loads(Path(args.timing).read_text())

    record["host"] = socket.gethostname()
    record["collected_at"] = datetime.now().isoformat(timespec="seconds")
    record["n_mislabels"] = count_mislabels(Path(args.mis))
    record.update(measured)
    record.update(parse_sativa_log(Path(args.log)))
    record["status"] = ("timeout" if measured.get("timed_out")
                        else "ok" if measured.get("returncode") == 0 else "error")

    Path(args.out).write_text(json.dumps(record, indent=2))
    if record["status"] != "ok":
        print(f"warning: run finished with status {record['status']}", file=sys.stderr)


if __name__ == "__main__":
    main()
