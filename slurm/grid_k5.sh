#!/bin/bash
#SBATCH --job-name=grid-k5
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
source "${BENCH_ROOT:-$BENCH_ROOT}/slurm/prelude.sh"
require_singularity

nextflow_env
nf_serialise
cd "$BENCH_ROOT"

echo "running on $(hostname)"

# Both fold orders at K=5. At K=25 the order changed detection by nothing, which the
# surviving-label law predicts and which a 2.58% co-location rate leaves little room to improve on.
# At K=5 a fold is a fifth of the database, so co-location is much higher and the tool's own
# fold-order option should earn its place here if it earns it anywhere. This also gives the K=5
# arm of the fold-count comparison over all 180 cells rather than the 15 the k sweep covered.
#
# Not a timed comparison, so timing_trusted is false and several cells run at once.
nextflow run . -profile singularity -resume \
  --datasets_json data/injected/datasets.json \
  --datasets all \
  --conditions epang_T8_K5,epang_T8_K5_tree \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --outdir "$BENCH_ROOT/results/grid_fork"
