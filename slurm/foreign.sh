#!/bin/bash
#SBATCH --job-name=foreign
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
nf_launch_dir foreign

echo "running on $(hostname)"

# Error kind 6: bacterial sequences under an archaeal label. Both tools, because the question
# is whether a foreign sequence is detected at all, and upstream is the reference for that.
# Not a timed comparison, so timing_trusted is false and several cells run at once.
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/foreign/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25,upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "foreign_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/foreign"
