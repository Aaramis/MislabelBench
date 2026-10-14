#!/bin/bash
#SBATCH --job-name=determinism
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=%x-%j.log
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir determinism
# Same cell, same seed, fresh work directory: the .mis must come back byte identical.
# Absolute, because nf_launch_dir has already changed the working directory to $BENCH_ROOT/.nf/
# determinism: `results/determinism` resolved under there, where nothing of the sort exists, so the
# outdir this job claims to clear was never cleared. Found when a stray run of this script wrote a
# trace file into results/determinism and left every other file in it dated three days earlier.
# work_det stays relative: the launch directory is where it belongs, one per job.
rm -rf work_det "$BENCH_ROOT/results/determinism"
nextflow run "$BENCH_ROOT" -profile singularity -w work_det \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets inj_species_r0.05_k3_s1 \
  --conditions epang_T8_K25 \
  --sativa_taxcode BAC --timing_trusted false \
  --trace_tag "determinism_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/determinism"
