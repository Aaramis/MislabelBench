#!/bin/bash
#SBATCH --job-name=ksweep
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#
# Not --exclusive. These cells declare timing_trusted false, so exclusivity buys them nothing,
# and on this cluster it costs everything: a node has 254 effective cores and --exclusive bills
# all of them, so one such job takes 510 of the 600-CPU per-user quota and starves every other
# job of our own. That is what serialised the whole queue for hours.

#SBATCH --output=%x-%j.log
set -euo pipefail

# Slurm copies the batch script to /var/spool, so $0 does not point at the repo.
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity

nextflow_env
nf_launch_dir ksweep

echo "running on $(hostname)"

# The k axis on the fork at two fold counts: six cells, species and genus distance at the top rate,
# three seeds each. Not the whole grid -- that is grid_fork.sh, and this comment was a copy of its.
# Not timed comparisons, they answer a detection question, so timing_trusted is false and several
# cells run at once.
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets inj_species_r0.05_k10_s1,inj_species_r0.05_k10_s2,inj_species_r0.05_k10_s3,inj_genus_r0.05_k10_s1,inj_genus_r0.05_k10_s2,inj_genus_r0.05_k10_s3 \
  --conditions epang_T8_K5,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "ksweep_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/ksweep"
