#!/usr/bin/env bash
# Rebuild ~/bench on the cluster from this repository.
#
#   bin/restore_cluster.sh --dry-run [user@host]     print the plan, touch nothing
#   bin/restore_cluster.sh [user@host]               do it
#
# Written after a cleanup command deleted the cluster home directory. Nothing was lost -- every run
# record, every .mis and every table is committed here, and every generated cell rebuilds from its
# seed -- but nothing in the repository knew how to put the cluster back, and the knowledge was in
# one person's head.
#
# bin/push_code.sh sends code only, deliberately: data/raw is fetched on the cluster by sha256 and
# results/ travels the other way. That is right for a cluster that already holds the datasets and
# wrong for one that holds nothing, which is the case this exists for. The kept datasets are 38 MB
# across 28 committed files and they are copied rather than refetched, because the copy is exact and
# a refetch depends on GTDB still serving release 226.
#
# What this does NOT do, on purpose: it never deletes anything on the remote, and it refuses to run
# against a ~/bench that already holds results. A restore that can overwrite a working cluster is a
# second incident waiting for the first.
#
# No caller, by design: this belongs with bin/push_code.sh and bin/repatriate.sh, the operator scripts
# that move things between here and the cluster. The rule that a script in bin/ has a caller or does
# not belong there is about analysis scripts, whose silence means a result nobody rebuilds.
set -euo pipefail

DRY=0
if [ "${1:-}" = "--dry-run" ]; then DRY=1; shift; fi
REMOTE="${1:-${BENCH_REMOTE:?usage: $0 user@cluster, or set BENCH_REMOTE}}"
HOST="${REMOTE%%:*}"
cd "$(dirname "$0")/.."

run() {
    if [ "$DRY" = "1" ]; then printf '  would run: %s\n' "$*"; else "$@"; fi
}

echo "== 1. the remote must be reachable and must not already hold results"
if [ "$DRY" = "1" ]; then
    echo "  would check: ssh $HOST 'ls ~/bench/results | wc -l'"
else
    # The remote command is single-quoted here and contains no $: every path it needs is literal.
    # A "$HOME" inside such a string was once expanded by the remote
    # shell and deleted the home directory.
    existing=$(ssh "$HOST" 'ls ~/bench/results 2>/dev/null | wc -l' | tr -d ' ')
    if [ "${existing:-0}" != "0" ]; then
        echo "~/bench/results already holds ${existing} entries on ${HOST}." >&2
        echo "This script only restores an empty or missing ~/bench. Repatriate first, or move it aside by hand." >&2
        exit 1
    fi
fi

# push_code.sh sends the per-cell truth files into data/injected/ and data/foreign/ with rsync, and
# rsync will not create a parent chain: on a cluster that already has ~/bench/data this never shows,
# and on an empty one -- the case this script exists for -- step 2 dies with
# `mkdir "~/bench/data/injected" failed: No such file or directory`. Found on the first real run,
# because the local replay of the delivery created its own target directory and so could not.
echo "== 1b. the directory skeleton, which rsync will not create for itself"
run ssh "$HOST" 'mkdir -p ~/bench/data/injected ~/bench/data/foreign ~/bench/data/clade ~/bench/data/simulated ~/bench/results'

echo "== 2. code, which is what push_code.sh already sends"
run bash bin/push_code.sh "$REMOTE"

echo "== 3. the kept datasets, which push_code.sh does not send"
# data/gtdb holds the base sets, their subsets and the covariance model; data/bacteria the donor
# pool for error kind 6. Both are committed and both are inputs no generator can recreate without
# the raw release.
run rsync -a --exclude='._*' data/gtdb data/bacteria "$REMOTE:~/bench/data/"

echo "== 4. the generated cells, rebuilt on the cluster from their seeds"
# Not copied: they are 92 MB and they regenerate in a couple of minutes from committed truth files,
# which the clone test checks byte for byte on every run of bin/analyses.sh.
for g in make_grid make_foreign make_clade make_simulation; do
    run ssh "$HOST" "cd ~/bench && BENCH_ROOT=\$PWD bash slurm/${g}.sh"
done

echo "== 5. the container images, which Nextflow caches and the timing scripts find by glob"
# The name below only has to satisfy the glob those scripts use -- slurm/scaling.sh looks for
# *sativa-epang*0.10.2*py314hab16a5f_0* precisely because Nextflow and `singularity pull` name the
# same image differently. A Nextflow run would populate the cache on its own, but then every timing
# script would fail until one had been launched, which is the wrong order for a restore.
run ssh "$HOST" 'mkdir -p ~/.singularity_cache'
for img in sativa:0.9.3--py312h031d066_0 sativa-epang:0.10.2--py314hab16a5f_0; do
    run ssh "$HOST" "cd ~/.singularity_cache && singularity pull --name depot.galaxyproject.org-singularity-${img%%:*}-${img#*:}.img https://depot.galaxyproject.org/singularity/${img}"
done

echo "== 6. what remains for a person"
cat <<'NOTES'
  - data/raw/ssu_all_r226.fna.gz is not restored here. It is fetched by URL and sha256 from
    assets/datasets.yml, and only slurm/rebuild_primary.sh needs it; the base sets themselves came
    across in step 3.
  - slurm/bad_nodes.txt arrives with the code, so the cluster starts with what was learned.
  - Verify before submitting anything: ssh HOST 'cd ~/bench && BENCH_ROOT=$PWD bin/analyses.sh'
    rebuilds nothing there (results/ is empty by construction) but verify_manifests.py and
    verify_injection.py will confirm the datasets are sound.
NOTES
