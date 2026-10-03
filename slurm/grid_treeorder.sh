#!/bin/bash
#SBATCH --job-name=grid-tree
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
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

nextflow_env
nf_launch_dir grid_tree

echo "running on $(hostname)"

# The same grid with the folds dealt in tree order instead of by name, which cuts same-species
# co-location from 2.58% to 0.64% (slurm/fold_order_check.sh). D21's prediction is a trade-off:
# a sequence keeps its true relatives more reliably, so k=1 should hold or improve, but the
# carriers of a shared wrong label are relatives too and also stay, so k>=2 should hold or get
# worse. Both moving the same way would refute D18's account of the mechanism.
#
# Not a timed comparison, so timing_trusted is false and several cells run at once.
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25_tree \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "grid_tree_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/grid_fork"
