#!/usr/bin/env python3
# What the numbers mean: ../README.md
"""Run one command, report wall time and peak child RSS as JSON on stdout.

A fresh process per measured run, so `RUSAGE_CHILDREN.ru_maxrss` covers this
run only (there is no /usr/bin/time on this host). The command runs in its own
process group, so a timeout kills the whole RAxML/EPA-ng subtree, not just the
python parent.
"""

import argparse
import json
import os
import resource
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--stdout", default=None)
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        sys.exit("no command given")

    out = open(args.stdout, "wb") if args.stdout else subprocess.DEVNULL
    # monotonic, not time(): a duration must not be measurable by a clock that NTP can step. At the
    # precision this benchmark quotes -- a spread of 0.67 s on 195.59 for the placement step -- a
    # correction of a few hundred milliseconds would be visible. It demonstrably never bit: across
    # the 430 runs that appear in both a run.json and a Nextflow trace, the two independent
    # measurements differ by more than 2 s or 2% in three, and those three are bidirectional, where
    # a clock step would show as a one-sided outlier.
    start = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(cmd, cwd=args.cwd, stdout=out, stderr=subprocess.STDOUT,
                            start_new_session=True)
    try:
        rc = proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        rc = proc.wait()
    wall = time.monotonic() - start
    if out is not subprocess.DEVNULL:
        out.close()

    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    print(json.dumps({
        "wall_sec": round(wall, 2),
        "returncode": rc,
        "timed_out": timed_out,
        # ru_maxrss is kilobytes on Linux and bytes on macOS, so the divisor is not a constant.
        # Getting it wrong is a factor of 1024 in a published memory figure, and the wrong answer
        # looks like a plausible one: a `sleep 0.4` on a Mac reported 11 808 MB.
        "max_rss_mb": round(usage.ru_maxrss / (1048576.0 if sys.platform == "darwin" else 1024.0), 1),
        "user_cpu_sec": round(usage.ru_utime, 2),
        "sys_cpu_sec": round(usage.ru_stime, 2),
    }))


if __name__ == "__main__":
    main()
