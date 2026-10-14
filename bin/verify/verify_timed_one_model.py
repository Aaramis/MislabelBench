#!/usr/bin/env python3
"""Every published timing must be a median over one CPU model.

The rule this repository states for itself is that seconds from two machines cannot be compared: the
cluster mixes four generations and the oldest is about half the per-core speed of the newest, so a
median taken across models is not a measurement of anything. The rule is enforced at submission by
--constraint, and nothing checked it afterwards against what the runs actually recorded.

A run that carries no cpu_model is not treated as a failure, because four of the trusted runs do not
carry one: the field postdates them. It is resolved through its host instead -- other records from
cpu-node-123 report AMD EPYC 9754, so those four are on the same model as everything else, which is
what makes the speed gradient a comparison rather than a mixture. A host that cannot be resolved, or
that reports two models, fails.

Checks the timed conditions only, which are the ones with timing_trusted records: the untimed grid
runs answer detection questions and their seconds are never read.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="results")
    args = p.parse_args()

    host_model = defaultdict(set)
    timed = defaultdict(list)
    for rj in Path(args.results).rglob("run.json"):
        d = json.loads(rj.read_text())
        if d.get("cpu_model"):
            host_model[d.get("host")].add(d["cpu_model"])
        if d.get("timing_trusted") and d.get("wall_sec") is not None:
            timed[(d.get("dataset"), d.get("condition"))].append((rj, d.get("host"),
                                                                  d.get("cpu_model")))

    problems, groups, runs, resolved = [], 0, 0, 0
    for key, records in sorted(timed.items(), key=lambda kv: tuple(map(str, kv[0]))):
        groups += 1
        models = set()
        for rj, host, model in records:
            runs += 1
            if model:
                models.add(model)
                continue
            through_host = host_model.get(host, set())
            if len(through_host) == 1:
                models |= through_host
                resolved += 1
            elif not through_host:
                problems.append(f"{rj}: no cpu_model, and no other record from {host} has one")
            else:
                problems.append(f"{rj}: no cpu_model, and {host} reports {sorted(through_host)}")
        if len(models) > 1:
            problems.append(f"{key[0]}/{key[1]}: timed over {len(models)} CPU models, "
                            f"{sorted(m[:28] for m in models)}")

    if not groups:
        sys.exit(f"no timed run found under {args.results}/; nothing was checked")
    # Says what was checked and how many problems, not that everything passed: the same gate wording
    # was wrong once already in verify_fold_counts.py, printing agreement above the lines that named
    # the disagreements.
    print(f"{groups} timed conditions over {runs} trusted runs checked for a single CPU model "
          f"({resolved} resolved through their host); {len(problems)} problem(s)")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} timing group(s) whose seconds are not comparable")


if __name__ == "__main__":
    main()
