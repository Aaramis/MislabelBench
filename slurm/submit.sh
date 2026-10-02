#!/bin/bash
# Submit a job script, excluding the nodes already known to lack singularity.
#
#   slurm/submit.sh slurm/grid_fork.sh
#
# The exclude list is built by the jobs themselves, in prelude.sh, so it converges: a node
# that fails once is never drawn again.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$HOME/bench}"
BAD_NODES="$BENCH_ROOT/slurm/bad_nodes.txt"
script="${1:?usage: submit.sh <job script> [extra sbatch args]}"
shift || true

exclude=""
if [ -s "$BAD_NODES" ]; then
    exclude="--exclude=$(paste -sd, "$BAD_NODES")"
    echo "excluding $(wc -l < "$BAD_NODES") node(s) known to lack singularity"
fi

# shellcheck disable=SC2086
sbatch $exclude "$@" "$script"
