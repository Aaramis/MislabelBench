#!/usr/bin/env python3
"""Mean and spread of the staged timings, grouped by node count and allocation size.

Reported per stage because only placement distributes, and with the spread because node-to-node
variation on this cluster is the same size as the effects being measured: a single run per
condition once made a reserved allocation look 25% faster than an exclusive one when the only
difference was a 2014 xeon against a 2023 epyc. The CPU model each replicate ran on is printed
for the same reason.

Run from the benchmark root, where results/scaling/ lives.
"""
import json, statistics as st
from collections import defaultdict
from pathlib import Path
# Grouped by dataset as well as by allocation. The first round ran on 2023 sequences and recorded
# no dataset, so it groups under "unrecorded, 2023 seqs"; anything later says which set it was.
# Averaging the two would compare a 16-second placement with a 200-second one.
g = defaultdict(list)
for f in sorted(Path("results/scaling").glob("*/timing.json")):
    d = json.loads(f.read_text())
    g[(d.get("dataset") or "unrecorded, 2023 seqs", d["nodes"],
       d["cores_requested_per_node"])].append(d)
print(f"{'dataset':24}{'cond':14}{'reps':>5}{'ref':>15}{'tasks':>8}{'place':>15}"
      f"{'score':>8}{'total':>15}")
for key in sorted(g):
    rs = g[key]
    def ms(f):
        v = [r[f] for r in rs]
        return (st.mean(v), (max(v) - min(v)))
    r, t, p, s, tot = (ms(f) for f in ("reference_sec", "loo_tasks_sec", "loo_place_sec",
                                       "loo_score_sec", "total_sec"))
    print(f"{key[0]:24}N={key[1]} c={key[2]:<8}{len(rs):>5}"
          f"{r[0]:9.2f}±{r[1]:4.2f}{t[0]:8.2f}{p[0]:9.2f}±{p[1]:4.2f}{s[0]:8.2f}"
          f"{tot[0]:9.2f}±{tot[1]:4.2f}")
    print(f"{'':24}models: {sorted({r['cpu_model'][:28] for r in rs})}")

for ds in sorted({k[0] for k in g}):
    one, two = g.get((ds, 1, 140)), g.get((ds, 2, 140))
    if not (one and two):
        continue
    print(f"\n{ds}:")
    p1 = st.mean([r["loo_place_sec"] for r in one])
    p2 = st.mean([r["loo_place_sec"] for r in two])
    t1 = st.mean([r["total_sec"] for r in one])
    t2 = st.mean([r["total_sec"] for r in two])
    serial = t1 - p1
    print(f"  placement speedup N=1->N=2: {p1 / p2:.2f}x of an ideal 2.00 "
          f"({100 * (p1 / p2) / 2:.0f}% efficiency)")
    print(f"  total speedup:              {t1 / t2:.2f}x")
    print(f"  serial share at N=1:        {100 * serial / t1:.1f}%  "
          f"-> Amdahl ceiling {t1 / serial:.2f}x")
