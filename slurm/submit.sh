#!/bin/bash
# Submit a job script, excluding the nodes already known to lack singularity.
#
#   slurm/submit.sh slurm/detection/grid_fork.sh
#
# The exclude list is built by the jobs themselves, in prelude.sh, so it converges: a node
# that fails once is never drawn again.
set -euo pipefail

export BENCH_ROOT="${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BAD_NODES="$BENCH_ROOT/slurm/bad_nodes.txt"
script="${1:?usage: submit.sh <job script> [extra sbatch args]}"
shift || true

exclude=""
if [ -s "$BAD_NODES" ]; then
    # sort -u, because the list can hold a name twice. prelude.sh appends with
    # `grep -qxF "$host" || echo "$host" >>`, which is a read and a write and not one step, so two
    # jobs landing on the same singularity-less node at the same moment both see it absent and both
    # append. bin/repatriate.sh takes the union with the cluster's copy and would clean it up later;
    # until it runs, the count printed here would overstate and Slurm would get a name twice.
    # Deduplicating at the point of use costs nothing and needs no lock.
    exclude="--exclude=$(sort -u "$BAD_NODES" | paste -sd, -)"
    echo "excluding $(sort -u "$BAD_NODES" | wc -l | tr -d ' ') node(s) known to lack singularity"
fi

# shellcheck disable=SC2086
sbatch $exclude "$@" "$script"
