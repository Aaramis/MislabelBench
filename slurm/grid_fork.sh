#!/bin/bash
#SBATCH --job-name=grid-fork
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --output=%x-%j.log
set -euo pipefail

source "$(dirname "$0")/prelude.sh"
require_singularity

nextflow_env
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
