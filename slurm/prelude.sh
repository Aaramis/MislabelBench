# Sourced by every job script. Two things the IFB cluster makes necessary.
#
# 1. Not every compute node has singularity, and no Slurm feature distinguishes them:
#    cpu-node-121 and cpu-node-129 both report epyc-9754 and only the first has it.
#
# 2. Requeueing alone does not converge. Slurm puts the job back and often picks the same
#    free node, so the first attempt at this burned all eight retries on cpu-node-127 without
#    ever landing somewhere else. So a node that fails records itself in bad_nodes.txt, and
#    submit.sh passes that list as --exclude. The list only grows, so the cluster is learned
#    once rather than rediscovered by every job.
#
# Requeueing also truncates the job's output file, so the diagnosis goes to an append-only
# log instead: without it the only surviving line is the last attempt's.

BENCH_ROOT="${BENCH_ROOT:-$HOME/bench}"
BAD_NODES="$BENCH_ROOT/slurm/bad_nodes.txt"
NODE_LOG="$BENCH_ROOT/slurm/node_checks.log"

require_singularity() {
    mkdir -p "$(dirname "$BAD_NODES")"
    if command -v singularity >/dev/null 2>&1; then
        echo "$(date -Is) $(hostname) ok job=${SLURM_JOB_ID:-none}" >> "$NODE_LOG"
        return 0
    fi

    local host attempt
    host="$(hostname)"
    attempt="${SLURM_RESTART_COUNT:-0}"
    echo "$(date -Is) $host MISSING job=${SLURM_JOB_ID:-none} attempt=$attempt" >> "$NODE_LOG"

    # Record it so the next submission excludes it, whatever happens to this job.
    grep -qxF "$host" "$BAD_NODES" 2>/dev/null || echo "$host" >> "$BAD_NODES"

    if [ "$attempt" -lt 8 ]; then
        echo "no singularity on $host, requeueing (attempt $attempt)" >&2
        scontrol requeue "${SLURM_JOB_ID}"
        exit 0
    fi
    echo "no singularity after $attempt attempts, last on $host" >&2
    exit 1
}

nextflow_env() {
    export PATH=/shared/software/miniconda_deployment/envs/nextflow-26.04.4/bin:$PATH
    export NXF_SINGULARITY_CACHEDIR="$HOME/.singularity_cache"
    mkdir -p "$NXF_SINGULARITY_CACHEDIR"
}
