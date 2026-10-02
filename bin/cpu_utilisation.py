#!/usr/bin/env python3
"""Wall clock, cores actually used, and CPU time, per dataset and condition.

Two reasons this is not just a wall-clock table.

Open question O4 asked whether SATIVA's -T 1 gives it one core. It does not: user CPU over wall
clock is 1.98 on a nominally single-threaded run. The same ratio says upstream saturates the eight
threads it is given, 7.97, while the fork uses 3.1 at 400 sequences rising to 5.5 at 7051. So the
fork's advantage in CPU time is larger than its advantage in wall clock, and reporting only the
latter understates it.

Medians over replicates, never a single run: upstream differs by a third between two nodes of the
same CPU model while the fork differs by one percent across the same pair, so one run of upstream is
not a measurement.
"""
import json, glob, statistics as st
from collections import defaultdict
g = defaultdict(list)
for f in glob.glob("results/*/runs/*/run.json"):
    d = json.load(open(f))
    if d.get("timing_trusted") and d.get("wall_sec"):
        g[(d["dataset"], d["condition"])].append((d["wall_sec"], d.get("user_cpu_sec") or 0))
print(f"{'dataset':14}{'condition':20}{'n':>3}{'wall':>10}{'cores':>7}{'CPU-s':>9}")
for (ds, c), v in sorted(g.items()):
    if not ds.startswith("gtdb"):
        continue
    print(f"{ds:14}{c:20}{len(v):>3}{st.median(x[0] for x in v):10.1f}"
          f"{st.median(x[1] / x[0] for x in v):7.2f}{st.median(x[1] for x in v):9.0f}")
print()
for ds in sorted({k[0] for k in g if k[0].startswith("gtdb")}):
    up, fk = g.get((ds, "upstream_raxml_T8")), g.get((ds, "epang_T8_K25"))
    if up and fk:
        uw, uc = st.median(x[0] for x in up), st.median(x[1] for x in up)
        fw, fc = st.median(x[0] for x in fk), st.median(x[1] for x in fk)
        print(f"{ds:14} wall {uw / fw:5.1f}x   CPU-time {uc / fc:5.1f}x"
              f"   (n={len(up)} upstream, {len(fk)} fork)")
