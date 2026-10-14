#!/usr/bin/env python3
"""Records read by main_figure.py: the size gradient and peak memory, the staged rounds, and the
mean judgement of each sequence by the two tools. Nothing here draws."""
import collections
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")


def resource_blocks():
    """The size gradient (wall seconds) and the peak-memory table (child MB), by sequences."""
    lines = (ROOT / "results/resource_usage.txt").read_text().splitlines()
    wall, mem = {}, {}
    mode = None
    for ln in lines:
        if ln.startswith("size gradient"):
            mode = "wall"
        elif ln.startswith("peak memory, both tools"):
            mode = "mem"
        elif ln.startswith("peak memory on the thread"):
            mode = None
        parts = ln.split()
        if mode and parts and parts[0].isdigit():
            n = int(parts[0])
            if mode == "wall":
                wall[n] = (float(parts[1]), float(parts[2]))          # fork, upstream
            else:
                # The process-tree peak, not run.json's ru_maxrss. ru_maxrss is the largest single
                # child, and the two diverge exactly where concurrency does -- 1.07x at one thread,
                # 3.55x at eight. What decides whether a run fits is the tree: that is what Slurm
                # and the OOM killer act on. Drawn as the largest child, this panel would support a
                # ceiling of 1.5 million sequences on a 2 TB node where the real one is 400 000.
                mem[n] = (float(parts[1]), float(parts[3]))           # fork tree, up tree
    return wall, mem


def staged_rows():
    """One row per round, averaged over whatever replicates of it exist.

    The rounds are no longer exclusive -- an exclusive job is charged all 510 cores of the node
    against a QOS cap of 600, so two shards could never both have it -- so the quantity that bounds
    the interference is the spread over replicates, and the panel has to be read off all of them
    rather than off one. `results/staged_scaling_f25.txt` and `..._f25_r2.txt` are both rounds of
    f25; the glob takes either shape, so a single-run round still plots.
    """
    rows = []
    for fpj in (25, 13, 7):
        # Replicates when there are any, and then only replicates. Pooling them with the
        # unsuffixed round would average across dates, and the dates do not agree: the same cell on
        # the same node with a byte-identical .mis took 194.5 s for its placement on 5 October and
        # 237.0 and 243.4 s in two rounds minutes apart on 8 October. Within a session the spread is
        # 2.7 %, across sessions 23 %, because the node is shared and the QOS will not let a timed
        # task have it alone. A mean over both dates would be a number from no machine.
        files = sorted(ROOT.glob(f"results/staged_scaling_f{fpj}_r*.txt")) \
            or sorted(ROOT.glob(f"results/staged_scaling_f{fpj}.txt"))
        reps = []
        for f in files:
            ln = f.read_text().splitlines()[1].split()
            reps.append({"shards": int(ln[1]), "ref": float(ln[2]), "tasks": float(ln[3]),
                         "place": float(ln[4]), "spread": float(ln[5]), "score": float(ln[6])})
        if not reps:
            raise SystemExit(f"no results/staged_scaling_f{fpj}*.txt to read")
        totals = [r["ref"] + r["tasks"] + r["place"] + r["score"] for r in reps]
        row = {k: st.median(r[k] for r in reps) for k in ("ref", "tasks", "place", "spread", "score")}
        row["total_min"], row["total_max"] = min(totals), max(totals)
        row["shards"] = reps[0]["shards"]
        row["reps"] = len(reps)
        # Range and not a standard deviation: at three replicates the range is what a reader can
        # check against the three numbers, and the claim it has to survive is a factor of 1.9.
        row["total_range"] = max(totals) - min(totals)
        rows.append(row)
    return sorted(rows, key=lambda r: r["shards"])


def upset_counts(floor):
    """Mean per dataset of every way the two tools can judge a sequence, split by what the sequence is:
    flagged by SATIVA on the unmodified database (baseline), an injected error, or an untouched
    sequence that neither of those covers. SATIVA's baseline is the reference for both tools."""
    import background_stability as bs
    cond = lambda c: f"gtdb_arc2k__{c}__rep1/gtdb_arc2k__{c}__rep1.mis"
    base = set(bs.flagged(ROOT / "results/baseline2k/runs" / cond("upstream_raxml_T8"), floor))
    out, n, per = collections.Counter(), 0, []
    for d in sorted((ROOT / "data/injected").glob("inj_*")):
        cell = d.name
        if "_r0.05_" not in cell:
            continue
        runs = ROOT / "results/grid_fork/runs"
        inj = set(json.loads((d / f"{cell}.truth.json").read_text())["injected"])
        u = set(bs.flagged(runs / f"{cell}__upstream_raxml_T8__rep1/{cell}__upstream_raxml_T8__rep1.mis", floor))
        e = set(bs.flagged(runs / f"{cell}__epang_T8_K25__rep1/{cell}__epang_T8_K25__rep1.mis", floor))
        n += 1
        here = collections.Counter()
        for seq in base | inj | u | e:
            kind = "baseline" if seq in base and seq not in inj else "injected" if seq in inj else "collateral"
            out[(kind, seq in u, seq in e)] += 1
            here[(kind, seq in u, seq in e)] += 1
        per.append((cell.rsplit("_", 1)[1], here))
    quart = {}
    for k in out:
        by_seed = collections.defaultdict(list)
        for seed, h in per:
            by_seed[seed].append(h[k])
        means = [sum(v) / len(v) for v in by_seed.values()]
        quart[k] = (min(means), max(means))
    return {k: v / n for k, v in out.items()}, quart
