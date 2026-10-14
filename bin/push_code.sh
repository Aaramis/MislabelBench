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

REMOTE="${1:-${BENCH_REMOTE:?usage: $0 user@cluster, or set BENCH_REMOTE}}"
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

# slurm/bad_nodes.txt is excluded from the wholesale sync because it is the one file here the
# cluster writes and this machine does not. prelude.sh appends to it when a node turns out to lack
# singularity, and submit.sh passes it as --exclude, which is what makes "the cluster is learned once
# rather than rediscovered by every job" true. A plain `rsync -a slurm` sends the committed copy over
# it, so any node learned since the last repatriation would be silently forgotten -- a deploy undoing
# what the cluster knows. The two copies happen to be identical today, four nodes each, which is why
# this had never shown itself.
rsync -a --exclude='._*' --exclude='bad_nodes.txt' --relative \
      main.nf nextflow.config conf modules bin slurm assets tests docs \
      README.md "$REMOTE:~/bench/"

# Sent only when the cluster has none, so a fresh ~/bench inherits what is known and an existing one
# keeps what it has learned. bin/repatriate.sh brings the union back the other way.
[ ! -f slurm/bad_nodes.txt ] || rsync -a --ignore-existing slurm/bad_nodes.txt "$REMOTE:~/bench/slurm/"
for d in injected clade simulated chimera; do
    rsync -a --exclude='._*' --include='*/' --include='*.truth.json' --include='datasets.json' \
          --exclude='*' "data/$d/" "$REMOTE:~/bench/data/$d/"
done
rsync -a --exclude='._*' --include='*/' --include='*.truth.json' --include='datasets.json' \
      --exclude='*' data/foreign/ "$REMOTE:~/bench/data/foreign/"

# Over the trees this script writes, not over all of ~/bench. The pinned RAxMLGroveScripts clone has
# carried ._.DS_Store and ._tree.nwk since 2022 -- upstream commit dcdd375, three files -- so a check
# that counts every ._* under the cluster home now fails on every push for content neither this script
# nor the cluster put there. A gate that cannot pass is a gate that gets ignored, and this one guards
# something real: eighteen AppleDouble forks landed here once and the timing-flag gate died on one of
# them before reading a record.
ssh "${REMOTE%%:*}" 'cd ~/bench && n=$(find main.nf nextflow.config conf modules bin slurm assets \
    tests data/injected data/clade data/simulated data/foreign -name "._*" 2>/dev/null | wc -l) \
    && echo "AppleDouble files left behind: $n" && [ "$n" = "0" ]'
