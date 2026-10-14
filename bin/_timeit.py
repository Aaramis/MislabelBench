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
import socket
import subprocess
import sys
import time


def where():
    """The machine this run is on, recorded here because here is where the run happens.

    COLLECTRUN is a separate Nextflow process, so under -profile ifb it is a separate Slurm job that
    the scheduler places on its own node, and the host and model collect_run.py reads from its own
    /proc/cpuinfo describe the collector. No committed record is known to be wrong: twenty of the
    twenty-one job scripts use -profile singularity, the local executor inside one allocation, where
    every task is on the allocation's node, and the one on ifb has tool and collector alike on
    cpu-node-121 in all three rounds. The field still read as a property of the measured machine
    without being measured there, which is the reason to move it rather than to argue about it.
    """
    model = None
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    # A null model is left out rather than written, so it cannot overwrite a value the collector
    # does have: there is no /proc/cpuinfo on a Mac, where this script is run in development.
    return {"host": socket.gethostname(), **({"cpu_model": model} if model else {})}


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
        # The argv, because nothing else recorded it. -m, -C, -x, -p and -S decide what the tool does
        # and they come from params with defaults, one --sativa_mode away from being something else;
        # conf/modules.config's own comment says a stage once ran -m thorough by accident and cost a
        # scaling measurement. No run record written before this line says which flags produced it,
        # and none written since does either: the nine staged rounds of 8 October ran from the
        # cluster's copy of this file, which predated the change, so the field and the agreement check
        # in bin/verify_runs.py are armed and have never met a real run. The first measured run after
        # the next bin/push_code.sh will be the first. No count is given here on purpose -- a corpus
        # number inside a comment is checked by nothing and this one was wrong within twelve hours.
        #
        # Taken from the command actually executed rather than rebuilt from the params, which is the
        # difference between evidence and a second copy that can drift.
        "cmd": cmd,
        **where(),
    }))


if __name__ == "__main__":
    main()
