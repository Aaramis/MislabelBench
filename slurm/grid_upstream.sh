#!/bin/bash
#SBATCH --job-name=grid-up
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#
# Not --exclusive. These cells declare timing_trusted false, so exclusivity buys them nothing,
# and on this cluster it costs everything: a node has 254 effective cores and --exclusive bills
# all of them, so one such job takes 510 of the 600-CPU per-user quota and starves every other
# job of our own. That is what serialised the whole queue for hours.

#SBATCH --output=%x-%j.log
set -euo pipefail

# Slurm copies the batch script to /var/spool, so $0 does not point at the repo.
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

nextflow_env
nf_serialise
cd "$HOME/bench"

echo "running on $(hostname)"

# The comparator on the same grid. It was missing: grid_fork.sh ran only the fork, so there was
# no upstream column for any injected cell and the detection comparison rested on the smaller k
# sweep instead. Upstream takes 734 s per cell at 8 threads on this subset, so 180 cells is about
# 37 h of 8-thread work; 32 cpus and -resume carry it across more than one allocation if needed.
#
# Not a timed comparison, so timing_trusted is false and several cells run at once.
nextflow run . -profile singularity -resume \
  --datasets_json data/injected/datasets.json \
  --datasets all \
  --conditions upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --outdir "$HOME/bench/results/grid_fork"   # same tree: one run directory per cell and condition
