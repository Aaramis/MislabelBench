#!/usr/bin/env python3
"""The staged path's shard scaling, as medians over replicates rather than as nine separate files.

bin/staged_scaling.py reports one round. Nine of them have now run -- three shard counts by three
replicates, chained on --dependency=afterany so no two of ours overlapped -- and reading a scaling
claim off nine files leaves the medians to whoever is reading. This repository's own rule, stated in
bin/resource_usage.py, is medians over replicates and never a single run; three successive wrong
readings of the memory law came from ignoring it.

Two things this reports that no per-round file can.

**The speedup, within one session only.** Every round of the current set ran on cpu-node-121 and so
did the earlier published one, same CPU model and same eight cores, and the same single-shard cell
takes 196 s on 2026-10-03 and a median of 237 s on 2026-10-08. That is 21 % on nothing but the node's
other occupants: our jobs were chained so they never overlapped each other, and the node has 512 CPUs
shared with everyone else. The within-session spread is 3.4 %, so the gap is not run-to-run noise. A
speedup computed across the two sessions would therefore be a measurement of someone else's workload,
and the ratio below is taken inside one set. The cross-session line is printed as its own row, to be
read as a caveat and not as a result.

**Why the speedup can beat the fold-count ceiling, which looks like an error.** A round's shards hold
25 folds between them and the slowest holds 7, so an equal-cost split cannot do better than 25/7 =
3.57x, and the measurement is 3.65x. The per-fold column says where the difference is: 9.48 s a fold on
one shard against 9.27 on four, a 2.2 % drop, which is exactly the 2.2 % the speedup exceeds the
ceiling by. Fewer folds live at once means a smaller resident set -- the memory law here is 1.15 MB per
sequence per live placement -- so the gain is not in the split but in what each shard no longer carries.

**What the distribution actually distributed.** All shards of every round landed on one node, so this
is distribution across Slurm jobs rather than across machines, and the ceiling it demonstrates is the
one a single machine's memory bandwidth allows. docs/distribution.md carries the same caveat; it is here as
well because this is the file the numbers come from.

**The same round with every shard on its own machine**, `--prefix staged_nodes --base staged_timed_f25`:
placement 63.4 s against 64.9 s on one node, 2 % apart, inside the 1 to 4 % the replicates of either
set spread over. One node's memory bandwidth was therefore not what bounded the four-shard round, and
"jobs" against "machines" is a distinction the measurement does not see at this size. The reference
stage, which is not pinned, came back 17 s slower in that set, which is the other node's occupants and
not the pin; the per-stage columns are there so that this can be read rather than guessed.
"""

import argparse
import json
import re
import statistics as st
from pathlib import Path

STAGES = ["reference", "lootasks", "looplace", "looscore"]


def round_seconds(staged_dir):
    """Per stage seconds for one round, placement being the slowest shard: the cell waits for it."""
    cells = sorted(d for d in Path(staged_dir).iterdir() if d.is_dir())
    if len(cells) != 1:
        raise SystemExit(f"{staged_dir} holds {len(cells)} cells; this reads one-cell rounds")
    secs = {}
    shards = []
    for f in cells[0].glob("*.timing.json"):
        stage = f.name.split(".")[0].split("_shard")[0]
        wall = json.loads(f.read_text()).get("wall_sec") or 0.0
        if stage == "looplace":
            shards.append(wall)
        else:
            secs[stage] = wall
    if not shards or any(s not in secs for s in STAGES if s != "looplace"):
        return None
    secs["looplace"] = max(shards)
    # Folds on the slowest shard, read off its own log, so the per-fold cost below is the measured
    # one and not params.folds_per_job divided into 25.
    folds = []
    for f in sorted(cells[0].glob("looplace_shard*.stage.log")):
        m = re.search(r"placed (\d+)/", f.read_text(errors="replace"))
        if m:
            folds.append(int(m.group(1)))
    secs["folds_max"] = max(folds) if folds else 0
    secs["folds_total"] = sum(folds) if folds else 0
    secs["n_shards"] = len(shards)
    secs["shard_spread"] = max(shards) - min(shards)
    secs["sum"] = sum(secs[s] for s in STAGES)
    secs["cell"] = cells[0].name
    return secs


def nodes_of(trace_dir, round_name):
    """Which nodes a round's shards ran on, from slurm/timing/shard_nodes.sh's table.

    The table is named after the trace tag, which is the output directory's own name and not the
    round's short tag -- shard_nodes-staged_timed_f25_r1_<jobid>.tsv for the round called f25_r1.
    Globbing on the short tag matched nothing and the report said "not recorded", which reads as a
    round that was never measured rather than as a pattern that does not match.
    """
    hits = sorted(Path(trace_dir).glob(f"shard_nodes-{round_name}_*.tsv"))
    out = []
    for f in hits:
        for line in f.read_text().splitlines()[1:]:
            if line.strip():
                out.append(line.split()[-1])
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="results")
    p.add_argument("--tags", default="f25,f13,f7",
                   help="round tags, coarsest shard count first")
    p.add_argument("--replicates", default="r1,r2,r3")
    p.add_argument("--prefix", default="staged_timed",
                   help="results/<prefix>_<tag>_<replicate>; staged_nodes for the rounds whose shards "
                        "were pinned to distinct machines")
    p.add_argument("--base", help="results/<base>_<replicate>, the one-shard rounds the pinned set "
                                  "is measured against, printed as its first row; a set of "
                                  "four-shard rounds alone has nothing to divide by")
    p.add_argument("--out")
    args = p.parse_args()

    results = Path(args.results)
    tags = [t.strip() for t in args.tags.split(",")]
    reps = [r.strip() for r in args.replicates.split(",")]
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    sets = [(args.prefix, t) for t in tags]
    if args.base:
        sets.insert(0, tuple(args.base.rsplit("_", 1)))
        tags.insert(0, sets[0][1])
    pooled, singles = {}, {}
    for prefix, tag in sets:
        rounds = []
        for rep in reps:
            d = results / f"{prefix}_{tag}_{rep}" / "staged"
            if d.is_dir():
                r = round_seconds(d)
                if r:
                    r["tag"] = f"{tag}_{rep}"
                    r["round"] = f"{prefix}_{tag}_{rep}"
                    r["prefix"] = prefix
                    rounds.append(r)
        if rounds:
            pooled[tag] = rounds
        # The same tag without a replicate suffix is the earlier session's round, kept for the
        # cross-session line and deliberately not pooled with the others.
        d = results / f"{prefix}_{tag}" / "staged"
        if d.is_dir():
            r = round_seconds(d)
            if r:
                singles[tag] = r

    if not pooled:
        raise SystemExit(f"no round of {tags} has replicates {reps} under {results}")

    say(f"{'shards':>7}{'rounds':>8}{'ref':>8}{'tasks':>7}{'place':>9}{'spread':>8}"
        f"{'score':>7}{'sum':>9}{'speedup':>9}{'s/fold':>9}{'ceiling':>9}"
        f"{'eff place':>11}{'total':>8}{'eff total':>11}")
    base = None
    base_sum = None
    for tag in tags:
        if tag not in pooled:
            continue
        rs = pooled[tag]
        n_shards = rs[0]["n_shards"]
        if any(r["n_shards"] != n_shards for r in rs):
            raise SystemExit(f"{tag}: rounds disagree on the shard count")
        med = {s: st.median(r[s] for r in rs) for s in STAGES + ["sum", "shard_spread"]}
        if base is None:
            base = med["looplace"]
            base_sum = med["sum"]
            # Amdahl: the three stages that do not divide bound the whole, however many shards.
            serial = (med["reference"] + med["lootasks"] + med["looscore"]) / med["sum"]
        fmax = rs[0]["folds_max"]
        ftot = rs[0]["folds_total"]
        per_fold = med["looplace"] / fmax if fmax else 0.0
        ceiling = ftot / fmax if fmax else 0.0
        # Efficiency is speedup over shards, per stage and for the whole run: both are reported, so that the speedup
        # is not overstated against Amdahl's law.
        say(f"{n_shards:>7}{len(rs):>8}{med['reference']:>8.1f}{med['lootasks']:>7.1f}"
            f"{med['looplace']:>9.1f}{med['shard_spread']:>8.1f}{med['looscore']:>7.1f}"
            f"{med['sum']:>9.1f}{base / med['looplace']:>8.2f}x"
            + (f"{per_fold:>9.2f}{ceiling:>8.2f}x" if fmax else f"{'-':>9}{'-':>9}")
            + f"{100 * base / med['looplace'] / n_shards:>10.0f}%"
            f"{base_sum / med['sum']:>7.2f}x{100 * base_sum / med['sum'] / n_shards:>10.0f}%")
        place = sorted(r["looplace"] for r in rs)
        span = 100 * (place[-1] - place[0]) / place[0]
        say(f"{'':15}placement over {len(rs)} rounds: "
            + ", ".join(f"{x:.1f}" for x in place) + f"  -> {span:.1f}% apart")
        hosts = [h for r in rs for h in nodes_of(results / "pipeline_info", r["round"])]
        if hosts:
            uniq = sorted(set(hosts))
            per_round = [nodes_of(results / "pipeline_info", r["round"]) for r in rs]
            distinct = all(len(set(h)) == len(h) for h in per_round if h)
            say(f"{'':15}nodes: {', '.join(uniq)}"
                + ("  -> one machine, so this is distribution across jobs" if len(uniq) == 1
                   else "  -> one shard per machine in every round" if distinct
                   else "  -> shards shared a machine in some round"))
            # A set that claims distinct machines and has two shards on one is not that set.
            if rs[0]["prefix"] == "staged_nodes" and not distinct:
                raise SystemExit(f"{tag}: shards shared a node in a round meant to pin them apart")
        else:
            say(f"{'':15}nodes: not recorded; run slurm/timing/shard_nodes.sh on these rounds")

    say(f"{'':15}serial share at one shard {100 * serial:.1f}% (reference, tasks, scoring), "
        f"so the whole run cannot beat {1 / serial:.2f}x however many shards: Amdahl")

    # The caveat, as its own rows. Same cell, same node, same CPU model, different day.
    cross = [(t, singles[t]["looplace"], st.median(r["looplace"] for r in pooled[t]))
             for t in tags if t in singles and t in pooled]
    if cross:
        say()
        say("the same rounds measured in an earlier session, which is why the speedup above is "
            "taken inside one set:")
        for tag, old, new in cross:
            say(f"{'':7}{tag:6} placement {old:7.1f} then {new:7.1f}  -> {100 * (new / old - 1):+.1f}%")
        say("same cell, same node, same CPU model; our own jobs were chained so they never "
            "overlapped, so what differs is the node's other occupants.")

    if args.out:
        Path(args.out).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
