#!/bin/bash
#SBATCH --job-name=chimera
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# Not --exclusive, for the reason the other untimed grids give: these cells declare
# timing_trusted false, and exclusivity would bill 510 cores against a 600-CPU quota.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir chimera

echo "running on $(hostname)"

# Error kind 7, both tools: 36 cells, four parent distances by three breakpoints by three seeds.
# The question is detection and which parent the proposal sides with, not rank accuracy, which a
# half-correct label has no answer to.
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/chimera/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25,upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "chimera_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/chimera"
