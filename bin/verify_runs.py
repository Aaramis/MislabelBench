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

It also cross-checks the two fields collect_run.py derives rather than measures. n_mislabels is counted
from the .mis, so the record and the file must agree. The three phase timings come from one regex over
SATIVA's own log, and parse_sativa_log returns an empty dict and says nothing when that regex misses, so
a future tool whose log is worded differently would lose them silently. A missing phase timing is not
fatal, since wall_sec is measured independently, so that one is reported and does not fail the gate.
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

    seen, bad, unparsed, modelless = Counter(), [], [], []
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

        # n_mislabels is counted from the .mis, so the two must agree.
        mis = sorted(f.parent.glob("*.mis"))
        if mis:
            real = sum(1 for line in mis[0].open(errors="replace")
                       if line.strip() and not line.startswith(";"))
            if d.get("n_mislabels") != real:
                bad.append(f"{f}: n_mislabels says {d.get('n_mislabels')}, "
                           f"{mis[0].name} holds {real}")

        # A trusted run whose CPU model was not recorded cannot be compared with another: the
        # cluster mixes four generations at about a factor of two per core. Not fatal, because
        # five such records predate the field and their model is recoverable from the node's
        # Slurm features, but it has to be visible rather than left to be noticed.
        if d.get("timing_trusted") and not d.get("cpu_model"):
            modelless.append(f"{f} (host {d.get('host')})")

        # sativa_timing says which of the two causes applies; records written before it
        # existed carry neither it nor the timings, so absence of the keys still counts.
        if "sativa_timing" in d:
            if d["sativa_timing"] != "parsed":
                unparsed.append(f"{f} ({d['sativa_timing']})")
        elif not all(k in d for k in ("sativa_total_sec", "reftree_sec", "l1out_sec")):
            unparsed.append(f"{f} (cause not recorded)")

    print(f"{len(records)} run records checked: "
          + ", ".join(f"{n} {s}" for s, n in sorted(seen.items())))
    if unparsed:
        print(f"  {len(unparsed)} without parsed phase timings, e.g. {unparsed[0]}; "
              "wall_sec is unaffected.", file=sys.stderr)
    if modelless:
        print(f"  {len(modelless)} trusted runs with no recorded cpu_model, e.g. {modelless[0]}; "
              "their seconds are not comparable without the node's Slurm features.",
              file=sys.stderr)
    for b in bad[:20]:
        print(f"  {b}", file=sys.stderr)
    if bad:
        # Not "did not finish cleanly": the list also holds records whose derived fields disagree
        # with the files they describe, which is a different fault with the same consequence.
        print(f"{len(bad)} problem(s) found; these runs must not enter a table", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
