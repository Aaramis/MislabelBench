#!/usr/bin/env bash
# Send the harness to the cluster. The counterpart of bin/repatriate.sh.
#
#   bin/push_code.sh [user@host]
#
# Code and ground truth only. results/ goes the other way and data/raw is fetched there by sha256,
# so neither belongs in this direction.
#
# --exclude='._*' is not cosmetic: a Mac rsync leaves an AppleDouble resource fork beside every file
# it copies, and eighteen of them landed in ~/bench the first time this was done by hand. They are
# harmless to bash, fatal to any python that globs *.sh -- the timing-flag gate died on one before
# reading a single record -- and they are inodes against a 100 000-file quota.
#
# Never while a pipeline job is running. The cluster copy is not a checkout, so a commit here cannot
# reach a running job, but this sync can, and changing a project file under a job's feet discards its
# resume cache. Six hours of RAxML went that way once.
set -euo pipefail

REMOTE="${1:-agardette@core.cluster.france-bioinformatique.fr}"
cd "$(dirname "$0")/.."

running=$(ssh "${REMOTE%%:*}" 'squeue -u $USER -h -o %j' | grep -v '^$' | tr '\n' ' ' || true)
if [ -n "$running" ]; then
    echo "jobs are running on the cluster: $running" >&2
    echo "syncing now would discard their resume caches; wait or pass FORCE=1" >&2
    [ "${FORCE:-0}" = "1" ] || exit 1
fi

rsync -a --exclude='._*' --relative \
      main.nf nextflow.config conf modules bin slurm assets tests \
      README.md REVIEW.md RESULTS.md "$REMOTE:~/bench/"
rsync -a --exclude='._*' --include='*/' --include='*.truth.json' --include='datasets.json' \
      --exclude='*' data/injected/ "$REMOTE:~/bench/data/injected/"
rsync -a --exclude='._*' --include='*/' --include='*.truth.json' --include='datasets.json' \
      --exclude='*' data/foreign/ "$REMOTE:~/bench/data/foreign/"

ssh "${REMOTE%%:*}" 'cd ~/bench && n=$(find . -name "._*" | wc -l) && echo "AppleDouble files left behind: $n" && [ "$n" = "0" ]'
