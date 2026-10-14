# Sourced by every job script. Sets BENCH_ROOT and the helpers below.
#
# Not every IFB compute node has singularity, and no Slurm feature tells them apart. A job that
# lands on one records the node in slurm/bad_nodes.txt (node names only, ignored by git) and fails.
# slurm/submit.sh passes that file as --exclude, so one resubmission clears each bad node. The
# diagnosis goes to an append-only log (slurm/node_checks.log) because a requeue truncates the job
# output file.

BENCH_ROOT="${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
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
    grep -qxF "$host" "$BAD_NODES" 2>/dev/null || echo "$host" >> "$BAD_NODES"
    # No requeue: Slurm would put the job back on the same free node.
    echo "no singularity on $host; recorded in $BAD_NODES, resubmit with slurm/submit.sh" >&2
    exit 1
}

# Nextflow 26.04.4 produced every result. Set NEXTFLOW_ENV to a directory whose bin/ holds nextflow;
# the default is the IFB environment of that version. Without a usable one, nextflow_env fails
# instead of falling back to whatever else is on the PATH.
NEXTFLOW_ENV="${NEXTFLOW_ENV:-/shared/software/miniconda_deployment/envs/nextflow-26.04.4}"

nextflow_env() {
    [ -x "$NEXTFLOW_ENV/bin/nextflow" ] || {
        echo "no nextflow at $NEXTFLOW_ENV/bin; set NEXTFLOW_ENV to an environment with nextflow 26.04.4" >&2
        ls -d "$(dirname "$NEXTFLOW_ENV")"/nextflow-* 2>/dev/null >&2
        exit 1
    }
    export PATH="$NEXTFLOW_ENV/bin:$PATH"
    export NXF_SINGULARITY_CACHEDIR="${NXF_SINGULARITY_CACHEDIR:-$HOME/.singularity_cache}"
    mkdir -p "$NXF_SINGULARITY_CACHEDIR"
}

# Nextflow holds a lock on its launch directory, so concurrent jobs each launch from their own.
nf_launch_dir() {
    local name="${1:?nf_launch_dir needs a name}"
    local dir="$BENCH_ROOT/.nf/$name"
    mkdir -p "$dir"
    cd "$dir"
    echo "nextflow launching from $dir"
}

# The IFB quota on $HOME counts files (100 000), not bytes. A job that writes many small files
# checks first; the argument is how many it is about to need. Returns 0 silently where the
# filesystem exposes no quota.
room_for() {
    local need="${1:?room_for needs a file count}" used limit free
    used=$(getfattr --only-values -n ceph.dir.rfiles "$HOME" 2>/dev/null) || return 0
    limit=$(getfattr --only-values -n ceph.quota.max_files "$HOME" 2>/dev/null) || return 0
    free=$((limit - used))
    echo "$free of $limit files free on $HOME, this step needs about $need"
    [ "$free" -gt "$need" ] || {
        echo "not enough file quota left; clear a scratch tree first, for instance:" >&2
        echo "  find \$BENCH_ROOT/results/minimal_case -type d -name 'fold_*' -exec rm -rf {} +" >&2
        exit 1
    }
}
