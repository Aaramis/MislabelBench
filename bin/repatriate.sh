#!/usr/bin/env bash
# Bring the run directories and the Nextflow traces back from the cluster, then repair what the
# copy undoes.
#
#   bin/repatriate.sh [user@host]
#
# Three things this exists for rather than typing an rsync.
#
# The include list. Only run.json, the .mis and the tool's own log are wanted; stdout.log
# duplicates the log and score.json is derived from committed inputs, so both stay out. Getting
# that list wrong by hand is how 949 run directories first arrived with nothing but their
# run.json.
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
rsync -a --exclude='._*' --include='*/' --include='run.json' --include='*.mis' --include='*.log' \
      --exclude='stdout.log' --exclude='score.json' --exclude='*' \
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
