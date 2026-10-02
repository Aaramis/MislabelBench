#!/bin/bash
#SBATCH --job-name=grid-fork
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --output=%x-%j.log
set -euo pipefail

# Not every node here has singularity and no Slurm feature distinguishes them; land, check,
# and let Slurm reschedule us if we drew one without it.
if ! command -v singularity >/dev/null 2>&1; then
    attempt="${SLURM_RESTART_COUNT:-0}"
    if [ "$attempt" -lt 8 ]; then
        echo "no singularity on $(hostname), requeueing (attempt $attempt)"
        scontrol requeue "$SLURM_JOB_ID"
        exit 0
    fi
    echo "no singularity after $attempt attempts, giving up" >&2
    exit 1
fi

export PATH=/shared/software/miniconda_deployment/envs/nextflow-26.04.4/bin:$PATH
export NXF_SINGULARITY_CACHEDIR=$HOME/.singularity_cache
cd "$HOME/bench"

echo "running on $(hostname)"

# The whole grid on the fork. These are not timed comparisons, they answer a detection
# question, so timing_trusted is false and several cells run at once.
nextflow run . -profile singularity -resume \
  --datasets_json data/injected/datasets.json \
  --datasets all \
  --conditions epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --outdir "$HOME/bench/results/grid_fork"
