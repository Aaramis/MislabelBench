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

nextflow_env() {
    export PATH=/shared/software/miniconda_deployment/envs/nextflow-26.04.4/bin:$PATH
    export NXF_SINGULARITY_CACHEDIR="$HOME/.singularity_cache"
    mkdir -p "$NXF_SINGULARITY_CACHEDIR"
}
