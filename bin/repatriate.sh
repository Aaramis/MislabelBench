#!/usr/bin/env bash
# Bring the run directories and the Nextflow traces back from the cluster, then repair what the
# copy undoes.
#
#   bin/repatriate.sh [user@host]
#
# Three things this exists for rather than typing an rsync.
#
# The include list. Only run.json, the .mis and the tool's own log are wanted, and score.json is
# derived from committed inputs so it stays out.
#
# *.timing.json is on it because the staged rounds' seconds live nowhere else. Without it nine
# finished rounds came home as `incomplete: []`: bin/staged_scaling.py reads one timing.json per
# stage and per shard, the .stage.log beside it carries the fold count and not the wall clock, and
# the three rounds already published had been fetched by hand before this script existed.
# shard_nodes-*.tsv likewise, which is the only record of which node each shard ran on. Getting that list wrong by hand is how 949 run
# directories first arrived with nothing but their run.json.
#
# .stderr is wanted too, for the experiments whose result is a failure. Some experiments
# ask "does SATIVA accept this input" and the answer for some inputs is no; the .log stops at "Loading taxonomy from file" and the traceback -- IndexError in
# epac/taxonomy_util.py line 337 -- is on stderr, which was not collected. So the fact of the
# failure was committed and its diagnosis was not.
#
# stdout.log is a third thing and the rule below used to pretend otherwise. rsync takes the first
# matching filter rule, --include='*.log' comes before --exclude='stdout.log', so the exclude was
# dead and 1022 of them arrived anyway -- 6.2 MB. It did no harm, because .gitignore keeps them out
# of git, which is where "stays out" actually mattered. But the claim that stdout.log duplicates the
# .log is false: they differ in every run directory checked, the .log being the tool's own and
# stdout.log the wrapper's. So it is included deliberately now and the dead rule is gone.
#
# The trace names. A job that writes into results/<outdir>/pipeline_info leaves either trace.txt
# or trace-<tag>.txt there, and nine outdirs each holding a trace.txt cannot be collected under
# one name. A bare one is renamed after its outdir on the way in.
#
# The repair. The cluster is where these records come from and it still holds the timing_trusted
# bug's output, so every repatriation puts 737 wrong flags back; the last one was committed before
# anyone looked. verify_timing_flags.py --fix is part of copying, not something to remember after.
set -euo pipefail

REMOTE="${1:-${BENCH_REMOTE:?usage: $0 user@cluster, or set BENCH_REMOTE}}"
cd "$(dirname "$0")/.."

# --exclude='._*' in both directions. A Mac rsync leaves an AppleDouble resource fork beside
# every file it copies, and eighteen of them landed in ~/bench once: harmless to bash, fatal to
# any python that globs *.sh, and inodes against a 100 000-file quota.
# Version 1's run trees stay on the cluster. results/runs (170 directories), results/runs_injected (36)
# and results/m1_check (3) are the `port_py3_*` conditions on the ITS sets, and the repository no longer
# holds the datasets they ran on, the conditions that name them or the job scripts that produced them --
# they were removed with version 1. Without this they arrive on every repatriation and have to be
# recognised and deleted by hand each time, which is how something unwanted eventually gets committed.
# They are excluded here rather than deleted there: they are the evidence behind version 1's published
# figures, which are still on origin/main.
#
# The leading slashes are not decoration. Written `runs/`, an rsync filter matches a directory of that
# name at ANY depth, so the pattern meant to skip one top-level tree skipped every
# `results/*/runs/` as well -- which is every run directory this script exists to fetch. Nothing came
# back from any repatriation between that change and the day a real job produced output that failed to
# arrive. Measured rather than reasoned: at the real transfer root, `runs/` transfers 0 of the
# determinism run's files and `/runs/` transfers 2.
#
# verdicts.tsv and case.json are the minimal-case experiment's result and its record of what was
# built. The case.fasta and case.tax they describe are deliberately not fetched: case.json carries
# the sha256 of the two source files and the selection is deterministic, so any case can be rebuilt
# byte for byte by bin/minimal_case.py, and the full-reference ones are 3 MB each.
# 'tmp/' unanchored, which is the opposite of the lesson above and deliberate. A tool's scratch
# directory is named tmp wherever it sits, and --include='*.log' matches the per-fold epang.log and
# epa_info.log inside it: one strict leave-one-out run on 2 023 sequences is two thousand folds, and a
# single repatriation brought back 3 314 of those files, from a job that was still running and would
# delete them itself. Nothing in results/ wants a directory named tmp, so the pattern that matches
# every depth is the right one here. It is first in the list because rsync takes the first match.
rsync -a --exclude='tmp/' \
      --exclude='._*' --exclude='/runs/' --exclude='/runs_injected/' --exclude='/m1_check/' \
      --include='*/' --include='run.json' --include='*.mis' --include='*.log' \
      --include='*.stderr' --include='verdicts.tsv' --include='case.json' \
      --include='*.timing.json' \
      --include='*.jplace' --include='ref.nwk' --include='query.fasta' \
      --exclude='score.json' --exclude='*' \
      "$REMOTE:~/bench/results/" results/

# The learned bad-node list comes back as a union, not a copy. It is written on the cluster, by
# whichever job met the node, and committed here so the knowledge survives a fresh ~/bench. Taking the
# union in this direction and never overwriting in the other means neither side can erase what the
# other learned. Sorted, so the file has one order rather than an insertion order that depends on
# which job failed first.
remote_bad=$(mktemp)
trap 'rm -f "$remote_bad"' EXIT
if rsync -a "$REMOTE:~/bench/slurm/bad_nodes.txt" "$remote_bad" 2>/dev/null && [ -s "$remote_bad" ]; then
    before=$(sort -u slurm/bad_nodes.txt 2>/dev/null | wc -l | tr -d ' ')
    sort -u "$remote_bad" slurm/bad_nodes.txt -o slurm/bad_nodes.txt
    after=$(wc -l < slurm/bad_nodes.txt | tr -d ' ')
    echo "bad nodes: $after known, $((after - before)) learned on the cluster since last time"
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"; rm -f "$remote_bad"' EXIT
rsync -a --exclude='._*' --include='*/' --include='trace*.txt' --include='shard_nodes-*.tsv' \
      --exclude='*' "$REMOTE:~/bench/results/" "$tmp/"
mkdir -p results/pipeline_info
# trace*.txt and shard_nodes-*.tsv: the trace and, where slurm/shard_nodes.sh has been run, which
# node each placement shard was on. Both are tagged with the job, which is what lets every round's
# pipeline_info flatten into this one directory without collisions.
for f in "$tmp"/*/pipeline_info/trace*.txt "$tmp"/*/pipeline_info/shard_nodes-*.tsv; do
    [ -e "$f" ] || continue
    outdir=$(basename "$(dirname "$(dirname "$f")")")
    name=$(basename "$f")
    [ "$name" = "trace.txt" ] && name="trace-$outdir.txt"
    cp "$f" "results/pipeline_info/$name"
done

find results -type d -empty -delete

bin/verify_timing_flags.py --fix
bin/verify_runs.py
