#!/bin/bash
#SBATCH --job-name=baseline
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --output=%x-%j.log
set -euo pipefail

# Not every compute node on this cluster has singularity installed, and nothing in the Slurm
# features distinguishes them: cpu-node-121 and cpu-node-129 both report epyc-9754, and only
# the first has it. Rather than maintain a node list by hand, land somewhere, check, and let
# Slurm reschedule us if we drew a node without it.
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

echo "running on $(hostname), singularity at $(command -v singularity)"

nextflow run . -profile singularity -resume \
  --datasets_json data/gtdb/datasets.json \
  --datasets gtdb_arc1200 \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --outdir "$HOME/bench/results/baseline"
