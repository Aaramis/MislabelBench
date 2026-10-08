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

Peak memory is read from the Nextflow traces, not from run.json. run.json's max_rss_mb is ru_maxrss
over the waited-for children, which is the largest single child rather than the process tree, and the
comment that used to be here said that was fine "because the fork places folds one after another, so
only one memory-heavy process is ever live" -- while naming its own undoing: "it would understate a
tool that ran several at once." The fork does. At one thread the two measures agree within 7%; at
eight the tree peak is 3.7 times the largest child. Both are printed, because the gap is the finding
and hiding one of them would bury it.
"""
import csv, json, glob, re, sys, statistics as st
from collections import defaultdict

UNITS = {"B": 1 / 1048576, "KB": 1 / 1024, "MB": 1, "GB": 1024, "TB": 1048576}
TASK = re.compile(r"\w+ \((.+?)/(.+?)/rep(\d+)\)")


# A whole run of a tool, which is the only thing whose process-tree peak answers "how much memory
# does this tool need for a reference of n sequences". The staged processes are stages of a
# differently-shaped run of the same (dataset, condition), and pooling them with the whole runs is
# how the published peak at 7 051 sequences became 8 602 MB: the median of six whole runs at 36 250
# and nine stages between 230 and 8 704 is a scoring stage's footprint, four times too low, printed
# beside a MB/seq column where it stood out at 1.22 against 4.4 to 5.1 everywhere else.
WHOLE_RUN = ("SATIVA ", "SATIVAEPANG ")


def trace_peaks():
    """Process-tree peak RSS in MB, per (dataset, condition), from every trace file."""
    out = defaultdict(list)
    for path in glob.glob("results/pipeline_info/trace-*.txt"):
        for r in csv.DictReader(open(path), delimiter="\t"):
            if r["status"] != "COMPLETED" or not r["name"].startswith(WHOLE_RUN):
                continue
            m, raw = TASK.match(r["name"]), r.get("peak_rss", "-")
            unit = re.match(r"([\d.]+)\s*(B|KB|MB|GB|TB)", raw or "")
            if m and unit:
                out[(m.group(1), m.group(2))].append(float(unit.group(1)) * UNITS[unit.group(2)])
    return out


peaks = trace_peaks()
g = defaultdict(list)
# A record missing a field is excluded and named, not defaulted to zero. The previous form was
# `d.get("user_cpu_sec") or 0`, which would have put a zero into a median of CPU time or of memory
# and shifted a published figure down without a word. All 56 trusted records carry all three
# fields, so this has never fired -- which is the reason to make it loud rather than to leave it.
incomplete = []
# And a record whose run shared the machine is excluded by experiment, because nothing in the record
# says so. The staged experiments run the whole-run control and the staged stages as separate Slurm
# jobs with no serialisation -- nextflow.config disables maxForks and queueSize on that path, on the
# argument that "each task is its own Slurm allocation, so nothing shares a node by accident", which
# confuses an allocation with a machine. The measurement says it: the reference build takes
# 71, 71, 72 s in the three staged jobs against 42, 42, 43, 44 in the serialised and exclusive ones,
# while the leave-one-out is 216 against 218 to 220 in both. Only the stage that overlaps is slowed,
# and it is slowed by 67 %. Those three records are honest records of what happened and are not
# comparable seconds, so they stay on disk and out of every median here.
contended = []
for f in glob.glob("results/*/runs/*/run.json"):
    d = json.load(open(f))
    if not (d.get("timing_trusted") and d.get("wall_sec")):
        continue
    if f.split("/")[1].startswith("staged_"):
        contended.append(f)
        continue
    if any(d.get(k) in (None, 0, 0.0) for k in ("user_cpu_sec", "max_rss_mb")):
        incomplete.append(f)
        continue
    g[(d["dataset"], d["condition"])].append(
        (d["wall_sec"], d["user_cpu_sec"], d["max_rss_mb"]))
# On stdout, not stderr. bin/analyses.sh redirects stdout into results/resource_usage.txt and lets
# stderr go to the job log, so a reader of the committed table could not tell that twelve trusted runs
# had been left out of the medians above it or why. An exclusion is a methodological choice and belongs
# where the numbers it shapes are.
if incomplete:
    print(f"excluded {len(incomplete)} trusted runs with no CPU time or no peak memory, "
          f"e.g. {incomplete[0]}")
if contended:
    print(f"excluded {len(contended)} trusted runs from the staged experiments, whose whole-run "
          f"control shares its node with the stages")
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

per_seq, tree_series = [], []
print()
print("peak memory, both tools at 8 threads, medians over replicates.")
print("tree is the Nextflow trace's process-tree peak; child is run.json's ru_maxrss.")
print(f"{'sequences':>10}{'fork tree':>11}{'fork child':>12}{'up tree':>9}{'up child':>10}"
      f"{'tree ratio':>12}{'child ratio':>13}{'fork MB/seq':>13}")
for ds, n in sizes:
    f, u = g.get((ds, "epang_T8_K25")), g.get((ds, "upstream_raxml_T8"))
    tf, tu = peaks.get((ds, "epang_T8_K25")), peaks.get((ds, "upstream_raxml_T8"))
    if not (f and u):
        continue
    fm, um = st.median(x[2] for x in f), st.median(x[2] for x in u)
    ft = st.median(tf) if tf else float("nan")
    ut = st.median(tu) if tu else float("nan")
    print(f"{n:>10}{ft:11.0f}{fm:12.0f}{ut:9.0f}{um:10.0f}{ft / ut:12.1f}"
          f"{fm / um if um else float('nan'):13.1f}{ft / n:13.2f}")
    per_seq.append((n, ft / n))
    tree_series.append((n, ft))

print()
# The two footprints answer different questions and the thread axis is where they separate. The
# largest child is what one process needs and is flat in the thread count; the tree is what the
# machine needs and is not. Which one a reader wants depends on whether they are sizing a node or
# wondering how large a database they can handle, so the last column says the second outright.
print("peak memory on the thread axis at 2023 sequences, tree against largest child")
# The capacity column below is computed from this size, 2 023 sequences, and that is the wrong size
# for it at eight threads: MB per sequence is 4.61 here and reaches its plateau of 5.13 only above
# 2 507, so extrapolating from this row overstates what a machine holds by 11 %. The table at the
# bottom gives the capacity at the largest size each thread count was measured at, which is the
# figure the manuscript's ceiling is taken from.
print(f"{'tool':10}{'T':>4}{'wall s':>8}{'tree MB':>10}{'child MB':>10}{'ratio':>7}"
      f"{'tree MB/seq':>13}{'max seqs in 64 GB':>19}")
for tool, prefix in (("fork", "epang_T{}_K25"), ("upstream", "upstream_raxml_T{}")):
    for t in (1, 8, 16):
        v, tr = g.get(("gtdb_arc2k", prefix.format(t))), peaks.get(("gtdb_arc2k", prefix.format(t)))
        if not v:
            continue
        child = st.median(x[2] for x in v)
        tree = st.median(tr) if tr else float("nan")
        wall = st.median(x[0] for x in v)
        per = tree / 2023
        print(f"{tool:10}{t:>4}{wall:8.0f}{tree:10.0f}{child:10.0f}{tree / child:7.2f}"
              f"{per:13.2f}{int(65536 / per):>19,}")

print()
# What a machine holds, from the largest reference each thread count was measured on rather than from
# the 2 023-sequence row above. At eight threads the law has not reached its plateau at 2 023, so this
# is the honest basis for a ceiling, and it is where the manuscript's two numbers come from.
print("how large a reference fits, from the largest size each thread count was measured on")
print(f"{'tool':10}{'T':>4}{'from n':>8}{'tree MB/seq':>13}{'in 64 GB':>12}{'in 2 TB':>14}")
for tool, prefix in (("fork", "epang_T{}_K25"), ("upstream", "upstream_raxml_T{}")):
    for t in (1, 8, 16):
        cand = [(dict(sizes)[ds], st.median(v)) for (ds, c), v in peaks.items()
                 if c == prefix.format(t) and ds in dict(sizes)]
        if not cand:
            continue
        n, tree = max(cand)
        per = tree / n
        print(f"{tool:10}{t:>4}{n:>8}{per:13.2f}{int(65536 / per):>12,}"
              f"{int(2 * 1024 * 1024 / per):>14,}")


# The law this table states is that the fork's footprint is proportional to the reference, and the
# table is the only place that law is written down. So it is checked against itself here, because the
# one time it was wrong it was wrong in a way the eye should have caught and did not: 1.22 MB per
# sequence at 7 051 in a column reading 4.4 to 5.1 everywhere else, printed for as long as it took
# the staged runs' per-stage tasks to be pooled with the whole runs and nobody to look. REVIEW.md
# finding 31 held the right numbers the whole time, three of them, and nothing compared the two.
problems = []
if per_seq:
    lo, hi = min(v for _, v in per_seq), max(v for _, v in per_seq)
    if hi / lo > 2:
        problems.append(f"the fork's MB per sequence runs from {lo:.2f} to {hi:.2f}, a factor of "
                        f"{hi / lo:.1f}; it is proportional to the reference or this table is wrong")
    for (n0, v0), (n1, v1) in zip(tree_series, tree_series[1:]):
        if v1 < v0:
            problems.append(f"the fork's peak falls from {v0:.0f} MB at {n0} sequences to {v1:.0f} "
                            f"at {n1}, which no larger reference does")
for pb in problems:
    print(f"  {pb}", file=sys.stderr)
if problems:
    sys.exit(f"{len(problems)} implausibility in the memory table")
