# Sourced by every job script. Two things the IFB cluster makes necessary.
#
# 1. Not every compute node has singularity, and no Slurm feature distinguishes them:
#    cpu-node-121 and cpu-node-129 both report epyc-9754 and only the first has it.
#
# 2. Requeueing does not converge: Slurm puts the job back and picks the same free node, so
#    cpu-node-127 and then cpu-node-130 each absorbed eight retries without ever landing
#    elsewhere. A node that fails now records itself in bad_nodes.txt and the job stops.
#    submit.sh passes that list as --exclude, so one resubmission clears each bad node and the
#    cluster is learned once rather than rediscovered by every job.
#
# Requeueing also truncates the job's output file, so the diagnosis goes to an append-only
# log instead: without it the only surviving line is the last attempt's.

BENCH_ROOT="${BENCH_ROOT:-$HOME/bench}"
# Every path in every job script hangs off this one, so a wrong value is silent and total: the
# scripts would read and write somewhere else entirely, or at the filesystem root. The ${VAR:-...}
# form above already absorbs an empty value from the caller, so what this checks is the two cases
# it cannot: a root that does not exist, which is the usual typo, and an empty one arriving from a
# broken default: a self-referential one, where the fallback is the variable itself, yields an
# empty root. A mechanical rewrite produced exactly that in thirteen scripts here once.
[ -n "$BENCH_ROOT" ] && [ -d "$BENCH_ROOT" ] || {
    echo "BENCH_ROOT does not name an existing directory: '$BENCH_ROOT'" >&2
    exit 1
}
BAD_NODES="$BENCH_ROOT/slurm/bad_nodes.txt"
NODE_LOG="$BENCH_ROOT/slurm/node_checks.log"

require_singularity() {
    mkdir -p "$(dirname "$BAD_NODES")"
    if command -v singularity >/dev/null 2>&1; then
        echo "$(date -Is) $(hostname) ok job=${SLURM_JOB_ID:-none}" >> "$NODE_LOG"
        return 0
    fi

    local host
    host="$(hostname)"
    echo "$(date -Is) $host MISSING job=${SLURM_JOB_ID:-none}" >> "$NODE_LOG"

    # Record it so the next submission excludes it, whatever happens to this job.
    grep -qxF "$host" "$BAD_NODES" 2>/dev/null || echo "$host" >> "$BAD_NODES"

    # No requeue. Slurm puts the job straight back on the same free node, so retrying only
    # burned eight cycles on cpu-node-130 before giving up on it. Failing here instead costs
    # one resubmission per bad node, which is the same rate of convergence without the waste,
    # because the node is now in bad_nodes.txt and submit.sh will exclude it.
    echo "no singularity on $host; recorded in $BAD_NODES, resubmit with slurm/submit.sh" >&2
    exit 1
}

# The one absolute path in this repository's executable code, and it is a pin rather than an
# assumption: twelve nextflow environments sit side by side on this cluster, from 22.10.0 to 26.04.4,
# and the campaign's 43 pipeline jobs all ran the one named here. Checked rather than trusted, because
# `export PATH=` to a directory that no longer exists succeeds, and the cluster prunes old environments
# eventually. Nothing else on this cluster provides `nextflow` -- verified on a login shell, where
# `command -v nextflow` finds none -- so the failure would be loud rather than a silent downgrade to
# another version. It would also be five lines and one confusing message away from its cause.
NEXTFLOW_ENV=/shared/software/miniconda_deployment/envs/nextflow-26.04.4

nextflow_env() {
    [ -x "$NEXTFLOW_ENV/bin/nextflow" ] || {
        echo "no nextflow at $NEXTFLOW_ENV/bin: the pinned environment is gone. Available:" >&2
        ls -d "$(dirname "$NEXTFLOW_ENV")"/nextflow-* 2>/dev/null >&2
        echo "pick one, update NEXTFLOW_ENV in slurm/prelude.sh, and record the change" >&2
        exit 1
    }
    export PATH="$NEXTFLOW_ENV/bin:$PATH"
    export NXF_SINGULARITY_CACHEDIR="$HOME/.singularity_cache"
    mkdir -p "$NXF_SINGULARITY_CACHEDIR"
}

# Nextflow keeps its resume cache in the launch directory and holds a lock on it, so two jobs
# launched from the same directory make the second die with "unable to acquire lock on session".
#
# This used to be handled by making the second job wait on a flock, to keep one shared resume cache
# across jobs. That cost more than it bought: it serialised every pipeline job, so an upstream run
# of sixteen hours held a node for over an hour doing nothing while another job finished. And the
# cache it protected is only worth sharing while cells are being recomputed, which they no longer
# are. So each job now launches from its own directory and they run at once.
#
# The cost is that a new job cannot resume cells another job computed. For a job running a new
# condition, which is every job from here on, there is nothing to resume anyway.
nf_launch_dir() {
    local name="${1:?nf_launch_dir needs a name}"
    local dir="$BENCH_ROOT/.nf/$name"
    mkdir -p "$dir"
    cd "$dir"
    echo "nextflow launching from $dir"
}

# The ceph quota on $HOME counts files, not bytes: 100 000 of them. Four concurrent minimal cases once
# filled it and the first failure's debris looked like three more failures, so a job that writes many
# small files checks first. The argument is how many files the caller is about to need; the margin
# above it is the caller's own, since there is no sensible default for "about to need".
#
# Returns 0 and says nothing when the attributes are missing, because a filesystem without them is not
# a filesystem with no room.
room_for() {
    local need="${1:?room_for needs a file count}" used limit free
    used=$(getfattr --only-values -n ceph.dir.rfiles "$HOME" 2>/dev/null) || return 0
    limit=$(getfattr --only-values -n ceph.quota.max_files "$HOME" 2>/dev/null) || return 0
    free=$((limit - used))
    echo "$free of $limit files free on $HOME, this step needs about $need"
    [ "$free" -gt "$need" ] || {
        echo "not enough file quota left. Clear a scratch tree first, for instance:" >&2
        echo "  find \$BENCH_ROOT/results/minimal_case -type d -name 'fold_*' -exec rm -rf {} +" >&2
        exit 1
    }
}
