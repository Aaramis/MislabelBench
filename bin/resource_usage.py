#!/usr/bin/env python3
"""Wall clock, cores actually used, CPU time and peak memory, per dataset and condition.

Two reasons this is not just a wall-clock table.

Open question O4 asked whether SATIVA's -T 1 gives it one core. It does not: user CPU over wall
clock is 1.98 on a nominally single-threaded run. The same ratio says upstream saturates the eight
threads it is given, 7.97, while the fork uses 3.1 at 400 sequences rising to 5.5 at 7051. So the
fork's advantage in CPU time is larger than its advantage in wall clock, and reporting only the
latter understates it.

Medians over replicates, never a single run: upstream differs by a third between two nodes of the
same CPU model while the fork differs by one percent across the same pair, so one run of upstream is
not a measurement.

Peak memory is ru_maxrss over the waited-for children, which is the maximum of any one child rather
than the sum. That is the right number for both tools here, because upstream threads inside one RAxML
and the fork places folds one after another, so only one memory-heavy process is ever live. It would
understate a tool that ran several at once.
"""
import json, glob, statistics as st
from collections import defaultdict
g = defaultdict(list)
for f in glob.glob("results/*/runs/*/run.json"):
    d = json.load(open(f))
    if d.get("timing_trusted") and d.get("wall_sec"):
        g[(d["dataset"], d["condition"])].append(
            (d["wall_sec"], d.get("user_cpu_sec") or 0, d.get("max_rss_mb") or 0))
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

print()
print("size gradient, both tools at 8 threads: medians, and the pair of speedups")
print(f"{'sequences':>10}{'fork':>9}{'upstream':>10}{'wall':>8}{'CPU':>8}"
      f"{'fork cores':>12}{'up cores':>10}")
sizes = [("gtdb_arc400", 402), ("gtdb_arc800", 801), ("gtdb_arc2k", 2023),
         ("gtdb_arc4000", 4001), ("gtdb_arc1200", 7051)]
for ds, n in sizes:
    f, u = g.get((ds, "epang_T8_K25")), g.get((ds, "upstream_raxml_T8"))
    if not (f and u):
        continue
    # x is (wall, user_cpu). Cores used is the ratio of the two; CPU seconds is user_cpu itself.
    fw, uw = st.median(x[0] for x in f), st.median(x[0] for x in u)
    fs, us = st.median(x[1] for x in f), st.median(x[1] for x in u)
    fc, uc = st.median(x[1] / x[0] for x in f), st.median(x[1] / x[0] for x in u)
    print(f"{n:>10}{fw:9.1f}{uw:10.1f}{uw / fw:8.1f}{us / fs:8.1f}{fc:12.2f}{uc:10.2f}")

print()
print("thread axis at 2023 sequences: what each tool does with the threads it is given")
print(f"{'tool':10}{'T':>4}{'wall':>9}{'cores':>8}{'speedup vs T1':>15}{'efficiency':>12}")
for tool, prefix in (("fork", "epang_T{}_K25"), ("upstream", "upstream_raxml_T{}")):
    base = g.get(("gtdb_arc2k", prefix.format(1)))
    if not base:
        continue
    b = st.median(x[0] for x in base)
    for t in (1, 8, 16):
        v = g.get(("gtdb_arc2k", prefix.format(t)))
        if not v:
            continue
        w, c = st.median(x[0] for x in v), st.median(x[1] / x[0] for x in v)
        print(f"{tool:10}{t:>4}{w:9.1f}{c:8.2f}{b / w:15.2f}{100 * (b / w) / t:11.0f}%")

print()
print("peak memory, both tools at 8 threads, medians over replicates")
print(f"{'sequences':>10}{'fork MB':>10}{'upstream MB':>13}{'ratio':>8}{'fork MB/kseq':>14}")
for ds, n in sizes:
    f, u = g.get((ds, "epang_T8_K25")), g.get((ds, "upstream_raxml_T8"))
    if not (f and u):
        continue
    fm, um = st.median(x[2] for x in f), st.median(x[2] for x in u)
    print(f"{n:>10}{fm:10.0f}{um:13.0f}{fm / um if um else float('nan'):8.2f}"
          f"{1000 * fm / n:14.1f}")

print()
print("peak memory on the thread axis at 2023 sequences")
print(f"{'tool':10}{'T':>4}{'MB':>9}")
for tool, prefix in (("fork", "epang_T{}_K25"), ("upstream", "upstream_raxml_T{}")):
    for t in (1, 8, 16):
        v = g.get(("gtdb_arc2k", prefix.format(t)))
        if v:
            print(f"{tool:10}{t:>4}{st.median(x[2] for x in v):9.0f}")
