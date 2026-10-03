#!/bin/bash
#SBATCH --job-name=determinism
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=%x-%j.log
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir determinism
# Same cell, same seed, fresh work directory: the .mis must come back byte identical.
rm -rf work_det results/determinism
nextflow run "$BENCH_ROOT" -profile singularity -w work_det \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets inj_species_r0.05_k3_s1 \
  --conditions epang_T8_K25 \
  --sativa_taxcode BAC --timing_trusted false \
  --trace_tag "determinism_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/determinism"
