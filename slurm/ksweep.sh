#!/bin/bash
#SBATCH --job-name=ksweep
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --output=%x-%j.log
set -euo pipefail

# Slurm copies the batch script to /var/spool, so $0 does not point at the repo.
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

nextflow_env
cd "$HOME/bench"

echo "running on $(hostname)"

# The whole grid on the fork. These are not timed comparisons, they answer a detection
# question, so timing_trusted is false and several cells run at once.
nextflow run . -profile singularity -resume \
  --datasets_json data/injected/datasets.json \
  --datasets inj_species_r0.05_k10_s1,inj_species_r0.05_k10_s2,inj_species_r0.05_k10_s3,inj_genus_r0.05_k10_s1,inj_genus_r0.05_k10_s2,inj_genus_r0.05_k10_s3 \
  --conditions epang_T8_K5,epang_T8_K25,epang_T8_Kexact \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --outdir "$HOME/bench/results/ksweep"
