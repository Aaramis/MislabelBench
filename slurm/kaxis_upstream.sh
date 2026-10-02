#!/bin/bash
#SBATCH --job-name=kaxis-up
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
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

echo "running on $(hostname)"

# The whole grid on the fork. These are not timed comparisons, they answer a detection
# question, so timing_trusted is false and several cells run at once.
nextflow run . -profile singularity -resume \
  --datasets_json data/injected/datasets.json \
  --datasets inj_species_r0.05_k1_s1,inj_species_r0.05_k1_s2,inj_species_r0.05_k1_s3,inj_species_r0.05_k2_s1,inj_species_r0.05_k2_s2,inj_species_r0.05_k2_s3,inj_species_r0.05_k3_s1,inj_species_r0.05_k3_s2,inj_species_r0.05_k3_s3,inj_species_r0.05_k5_s1,inj_species_r0.05_k5_s2,inj_species_r0.05_k5_s3,inj_species_r0.05_k10_s1,inj_species_r0.05_k10_s2,inj_species_r0.05_k10_s3 \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --outdir "$HOME/bench/results/kaxis"
