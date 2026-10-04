#!/usr/bin/env bash
# Bring the run directories and the Nextflow traces back from the cluster, then repair what the
# copy undoes.
#
#   bin/repatriate.sh [user@host]
#
# Three things this exists for rather than typing an rsync.
#
# The include list. Only run.json, the .mis and the tool's own log are wanted, and score.json is
# derived from committed inputs so it stays out. Getting that list wrong by hand is how 949 run
# directories first arrived with nothing but their run.json.
#
# .stderr is wanted too, for the experiments whose result is a failure. before_after.sh and
# ragged_check.sh answer "does SATIVA accept this input" and the answer for two of their five
# inputs is no; the .log stops at "Loading taxonomy from file" and the traceback -- IndexError in
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

REMOTE="${1:-agardette@core.cluster.france-bioinformatique.fr}"
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
rsync -a --exclude='._*' --exclude='runs/' --exclude='runs_injected/' --exclude='m1_check/' \
      --include='*/' --include='run.json' --include='*.mis' --include='*.log' \
      --include='*.stderr' --exclude='score.json' --exclude='*' \
      "$REMOTE:~/bench/results/" results/

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
rsync -a --exclude='._*' --include='*/' --include='trace*.txt' --exclude='*' "$REMOTE:~/bench/results/" "$tmp/"
mkdir -p results/pipeline_info
for f in "$tmp"/*/pipeline_info/trace*.txt; do
    [ -e "$f" ] || continue
    outdir=$(basename "$(dirname "$(dirname "$f")")")
    name=$(basename "$f")
    [ "$name" = "trace.txt" ] && name="trace-$outdir.txt"
    cp "$f" "results/pipeline_info/$name"
done

find results -type d -empty -delete

bin/verify_timing_flags.py --fix
bin/verify_runs.py
