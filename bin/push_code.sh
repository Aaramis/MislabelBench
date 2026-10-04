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
    echo "jobs are running or queued on the cluster: $running" >&2
    # Which job scripts this sync would actually change. A queued replicate reads its script when it
    # starts, not when it was submitted, so a sync between the replicates of one experiment can
    # leave the later ones running something else -- and nothing would say so afterwards. Three N=4
    # scaling replicates sat in the queue through one such sync; the checksums were equal and it was
    # checked by hand, which is not a method.
    #
    # The file list goes over stdin and is never part of the command string. Interpolating it was
    # the worst mistake made on this project: `ssh host "cd ~/bench && md5sum $files"` with a
    # newline-separated list made every name after the first a command for the remote shell, so the
    # login node ran slurm/submit.sh, slurm/scaling.sh and the rest of the repository in sequence.
    # scaling.sh built a reference tree and placed folds there for fourteen minutes before failing,
    # and two srun allocations were created. Nothing was lost -- determinism.sh and make_foreign.sh
    # both begin with rm -rf and both targets are committed and deterministic -- but that was luck.
    #
    # One ssh for all of them rather than one per file: the per-file version dropped the connection
    # part way through and reported the file it was on as changed, which is a check that invents
    # findings when the network hiccups.
    files=$(ls slurm/*.sh nextflow.config main.nf conf/*.config modules/local/*/main.nf bin/*.py \
            bin/*.sh 2>/dev/null)
    remote=$(printf '%s\n' "$files" | ssh "${REMOTE%%:*}" \
             'cd ~/bench && tr -d "\r" | xargs -d "\n" md5sum 2>/dev/null' || true)
    changed=""
    for f in $files; do
        want=$(printf '%s\n' "$remote" | awk -v f="$f" '$2 == f {print $1}')
        [ "$want" = "$(md5 -q "$f")" ] || changed="$changed $f"
    done
    if [ -n "$changed" ]; then
        echo "and this sync would change:$changed" >&2
    else
        echo "this sync changes nothing: every file already matches" >&2
    fi
    echo "wait, or pass FORCE=1 having read the list above" >&2
    [ "${FORCE:-0}" = "1" ] || exit 1
fi

rsync -a --exclude='._*' --relative \
      main.nf nextflow.config conf modules bin slurm assets tests \
      README.md REVIEW.md DISTRIBUTION.md "$REMOTE:~/bench/"
rsync -a --exclude='._*' --include='*/' --include='*.truth.json' --include='datasets.json' \
      --exclude='*' data/injected/ "$REMOTE:~/bench/data/injected/"
rsync -a --exclude='._*' --include='*/' --include='*.truth.json' --include='datasets.json' \
      --exclude='*' data/foreign/ "$REMOTE:~/bench/data/foreign/"

ssh "${REMOTE%%:*}" 'cd ~/bench && n=$(find . -name "._*" | wc -l) && echo "AppleDouble files left behind: $n" && [ "$n" = "0" ]'
