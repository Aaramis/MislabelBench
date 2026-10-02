#!/bin/bash
#SBATCH --job-name=baseline
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --exclusive

#SBATCH --output=%x-%j.log
set -euo pipefail

# Slurm copies the batch script to /var/spool, so $0 does not point at the repo.
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

nextflow_env
nf_serialise
cd "$HOME/bench"

echo "running on $(hostname), singularity at $(command -v singularity)"

nextflow run . -profile singularity -resume \
  --datasets_json data/gtdb/datasets.json \
  --datasets gtdb_arc1200 \
  --timing_trusted true \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --outdir "$HOME/bench/results/baseline"
