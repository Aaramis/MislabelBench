#!/usr/bin/env python3
"""Per-stage timings of the staged pipeline, in the shape slurm/scaling.sh reports.

The point of comparison is slurm/scaling.sh, which drives the tool with srun from inside one
allocation and measures t0..t4 around each stage. Two things make the pipeline's numbers not
directly comparable unless they are kept apart, so this prints both.

  stage sum   reference + lootasks + max(placement shards) + looscore, from each stage's own
              timing.json. This is the same quantity scaling.sh reports and excludes everything
              Nextflow does between stages.
  trace span  first submit to last completion, from the Nextflow trace. This includes staging,
              scheduling and the gaps, which is what a user actually waits for.

The placement step ends when its slowest shard ends, so it is a maximum and not a sum, and the
spread across shards is printed because at four shards the srun version found one straggler per
allocation every time.

Fold counts per shard are printed with them, because a speedup read against the shard count
conflates two things. 25 folds over 4 shards split 7, 6, 6, 6, so the slowest shard carries 7 of 25
and no distribution of them can beat 25/7 = 3.57x however free it is. Measured against 4 the
pipeline is 86 % efficient; measured against the ceiling the fold split leaves it is 96.6 %, and the
difference between those two numbers is arithmetic, not overhead.
"""

import argparse
import csv
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

STAGES = ("reference", "lootasks", "looplace", "looscore")
TASK = re.compile(r"\w+ \((.+?)/(.+?)/rep(\d+)")


def duration(text):
    """Nextflow's human durations to seconds."""
    total = 0.0
    for part in text.split():
        for unit, mult in (("ms", 0.001), ("s", 1), ("m", 60), ("h", 3600)):
            if part.endswith(unit):
                total += float(part[: -len(unit)]) * mult
                break
    return total


def trace_span(trace_dir, run_name):
    """First submit to last completion, over the tasks of one run, in seconds."""
    best = None
    for path in Path(trace_dir).glob("trace-*.txt"):
        starts, ends = [], []
        for row in csv.DictReader(path.open(), delimiter="\t"):
            if row["status"] != "COMPLETED" or run_name.split("__")[0] not in row["name"]:
                continue
            t0 = row["submit"]
            starts.append(t0)
            ends.append((t0, duration(row["duration"])))
        if starts:
            from datetime import datetime
            fmt = "%Y-%m-%d %H:%M:%S.%f"
            first = min(datetime.strptime(s, fmt) for s in starts)
            last = max(datetime.strptime(s, fmt).timestamp() + d for s, d in ends)
            span = last - first.timestamp()
            best = span if best is None else max(best, span)
    return best


def shard_hosts(trace_dir, run_name):
    """Which host each placement shard ran on, from the trace's hostname field.

    This replaces what --exclusive used to guarantee. The QOS charges an exclusive job the whole
    node, 510 CPUs against a cap of 600, so two shards could never both be exclusive and the
    distributed rounds run on shared nodes. Two shards on one node is then possible, and it is the
    one disturbance that would corrupt the measurement rather than just add noise to it: finding 152
    measured two tasks of one run building the same tree at 71 s each where one alone takes 42.5.

    Nextflow's local executor writes "-" in this field and old traces have no field at all, so an
    absent or "-" host is reported as not recorded rather than counted as a collision.
    """
    best = []
    for path in sorted(Path(trace_dir).glob("trace-*.txt")):
        # Per file, not pooled across them. A round that timed out and was resubmitted leaves a second
        # trace in the same outdir under a different job id, and pooling the two would report every
        # host twice and call it a collision. One round is one trace, so the file with the most
        # placement rows is the round, and a repeat inside one file is a real repeat.
        hosts = []
        for row in csv.DictReader(path.open(), delimiter="\t"):
            if row["status"] != "COMPLETED" or "LOOPLACE" not in row["name"].upper():
                continue
            if run_name.split("__")[0] not in row["name"]:
                continue
            h = (row.get("hostname") or "-").strip()
            if h and h != "-":
                hosts.append(h)
        if len(hosts) > len(best):
            best = hosts
    return best


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--staged-dir", required=True, help="results/<outdir>/staged")
    p.add_argument("--trace-dir", default=None, help="where the trace-*.txt live")
    args = p.parse_args()

    cells = sorted(d for d in Path(args.staged_dir).iterdir() if d.is_dir())
    if not cells:
        raise SystemExit(f"no cells under {args.staged_dir}")

    collisions = []
    print(f"{'cell':34}{'shards':>7}{'ref':>8}{'tasks':>7}{'place':>9}{'spread':>8}"
          f"{'score':>7}{'sum':>9}{'span':>9}")
    for cell in cells:
        secs = defaultdict(list)
        for f in cell.glob("*.timing.json"):
            stage = f.name.split(".")[0].split("_shard")[0]
            secs[stage].append(json.loads(f.read_text()).get("wall_sec") or 0.0)
        if not all(secs.get(s) for s in STAGES):
            print(f"{cell.name:34}  incomplete: {sorted(secs)}")
            continue
        # Folds per shard, from each shard's own log, so the ceiling below is read off the run and
        # not off params.folds_per_job.
        folds = []
        for f in sorted(cell.glob("looplace_shard*.stage.log")):
            m = re.search(r"placed (\d+)/", f.read_text(errors="replace"))
            if m:
                folds.append(int(m.group(1)))

        shards = secs["looplace"]
        place = max(shards)
        spread = (max(shards) - min(shards)) if len(shards) > 1 else 0.0
        total = secs["reference"][0] + secs["lootasks"][0] + place + secs["looscore"][0]
        span = trace_span(args.trace_dir, cell.name) if args.trace_dir else None
        print(f"{cell.name:34}{len(shards):>7}{secs['reference'][0]:>8.1f}"
              f"{secs['lootasks'][0]:>7.1f}{place:>9.1f}{spread:>8.1f}"
              f"{secs['looscore'][0]:>7.1f}{total:>9.1f}"
              + (f"{span:>9.1f}" if span else f"{'-':>9}"))
        if len(shards) > 1:
            print(f"{'':34}shards: " + ", ".join(f"{x:.1f}" for x in sorted(shards)))
            hosts = shard_hosts(args.trace_dir, cell.name) if args.trace_dir else []
            if not hosts:
                print(f"{'':34}hosts: not recorded")
            elif len(set(hosts)) < len(hosts):
                dup = sorted(h for h in set(hosts) if hosts.count(h) > 1)
                print(f"{'':34}hosts: " + ", ".join(sorted(hosts))
                      + f"  -> {', '.join(dup)} carried more than one shard")
                collisions.append((cell.name, dup))
            else:
                print(f"{'':34}hosts: " + ", ".join(sorted(hosts)) + "  -> one shard each")
        if folds:
            ceiling = sum(folds) / max(folds)
            print(f"{'':34}folds: " + ", ".join(str(x) for x in folds)
                  + f"  -> no split of these beats {ceiling:.2f}x on {len(folds)} shards")

    # Not a warning. A round whose shards shared a node did not measure what the panel says it
    # measured, and the table is written by a job script that would otherwise publish it anyway.
    if collisions:
        raise SystemExit("shards shared a node: "
                         + "; ".join(f"{c} on {', '.join(d)}" for c, d in collisions))


if __name__ == "__main__":
    main()
