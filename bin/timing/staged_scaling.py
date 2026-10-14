#!/usr/bin/env python3
"""Per-stage timings of the staged pipeline, in the shape slurm/timing/scaling.sh reports.

The point of comparison is slurm/timing/scaling.sh, which drives the tool with srun from inside one
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


def round_files(trace_dir, pattern, round_name):
    """The files of one round, when several rounds share a directory.

    bin/ops/repatriate.sh flattens every round's pipeline_info into results/pipeline_info, where nine
    staged rounds of the same cell now sit side by side. Their names carry the round --
    trace-staged_timed_f25_r1_2302505.txt against the directory staged_timed_f25_r1 -- so the round
    is selected by name and not by matching the cell, which would take all nine. Falls back to every
    match when the name selects nothing, which is the case for the three rounds that keep their own
    pipeline_info directory.
    """
    files = sorted(Path(trace_dir).glob(pattern))
    mine = [f for f in files if round_name and round_name in f.name]
    return mine or files


def trace_span(trace_dir, run_name, round_name=None):
    """First submit to last completion, over the tasks of one run, in seconds."""
    best = None
    for path in round_files(trace_dir, "trace-*.txt", round_name):
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


def shard_nodes(cell_dir, trace_dir, n_shards, round_name=None):
    """Which node each placement shard ran on, if anything recorded it.

    This replaces what --exclusive used to guarantee and the QOS will not allow: an exclusive job is
    charged all 510 cores of an epyc-9754 against a 600-core cap, so two shards could never both have
    it. Two shards on one node is the disturbance that changes what the measurement means, so it has
    to be read off a record rather than assumed.

    Two records, in order of preference, and deliberately not the trace. Nextflow's `hostname` trace
    field is empty under the Slurm executor on this cluster and "-" under the local one, checked on
    every round here, so a route through it would never answer.

      the shard's own timing.json, where _timeit.py writes the host of the task it measured
      pipeline_info/shard_nodes.tsv, which slurm/timing/shard_nodes.sh resolves from Slurm accounting
    """
    hosts = []
    for f in sorted(cell_dir.glob("looplace_shard*.timing.json")):
        h = (json.loads(f.read_text()).get("host") or "").strip()
        if h:
            hosts.append(h)
    if hosts:
        return hosts
    if trace_dir:
        # shard_nodes-<tag>.tsv, one per round, all of them flattened into results/pipeline_info by
        # bin/ops/repatriate.sh. Rows are kept on the dataset and on n_shards, which is what tells one
        # round from another once nine of them share a directory.
        for tsv in round_files(trace_dir, "shard_nodes*.tsv", round_name):
            for line in tsv.read_text().splitlines()[1:]:
                parts = line.split("\t")
                # The trace writes a cell as dataset/condition/rep and the published directory as
                # dataset__condition__rep, so they are compared on the dataset, the way trace_span
                # above does it. Matching the whole string found nothing and printed "not recorded"
                # over a file that was sitting right there.
                if (len(parts) >= 5 and parts[0].split("/")[0] == cell_dir.name.split("__")[0]
                        and parts[2] == str(n_shards)):
                    hosts.append(parts[4])
            if hosts:
                break
    return hosts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--staged-dir", required=True, help="results/<outdir>/staged")
    p.add_argument("--trace-dir", default=None, help="where the trace-*.txt live")
    p.add_argument("--round", default=None,
                   help="round name, to pick this round's trace out of a shared directory")
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
        span = (trace_span(args.trace_dir, cell.name, args.round)
                if args.trace_dir else None)
        print(f"{cell.name:34}{len(shards):>7}{secs['reference'][0]:>8.1f}"
              f"{secs['lootasks'][0]:>7.1f}{place:>9.1f}{spread:>8.1f}"
              f"{secs['looscore'][0]:>7.1f}{total:>9.1f}"
              + (f"{span:>9.1f}" if span else f"{'-':>9}"))
        if len(shards) > 1:
            print(f"{'':34}shards: " + ", ".join(f"{x:.1f}" for x in sorted(shards)))
            hosts = shard_nodes(cell, args.trace_dir, len(shards), args.round)
            if not hosts:
                print(f"{'':34}nodes: not recorded; run slurm/timing/shard_nodes.sh on this round")
            elif len(set(hosts)) < len(hosts):
                dup = sorted(h for h in set(hosts) if hosts.count(h) > 1)
                print(f"{'':34}nodes: " + ", ".join(sorted(hosts))
                      + f"  -> {', '.join(dup)} carried more than one shard")
                collisions.append((cell.name, dup))
            else:
                print(f"{'':34}nodes: " + ", ".join(sorted(hosts)) + "  -> one shard each")
        if folds:
            ceiling = sum(folds) / max(folds)
            print(f"{'':34}folds: " + ", ".join(str(x) for x in folds)
                  + f"  -> no split of these beats {ceiling:.2f}x on {len(folds)} shards")

    # Not a warning. A round whose shards shared a node did not measure what the panel says it
    # measured, and the table is written by a job script that would otherwise publish it anyway.
    if collisions:
        # Printed, not fatal. Every round measured on this cluster has had its shards co-located --
        # all four of f7's on cpu-node-121, in the published round and in the new one alike -- so
        # exiting here would refuse every table there is. What the co-location changes is what the
        # numbers mean, and that belongs in the figure's caption and in docs/distribution.md, where it now
        # is, rather than in a gate that would delete the measurement instead of qualifying it.
        print("\nshards shared a node: "
              + "; ".join(f"{c} on {', '.join(d)}" for c, d in collisions)
              + "\nso this round distributes across Slurm jobs and not across machines.")


if __name__ == "__main__":
    main()
