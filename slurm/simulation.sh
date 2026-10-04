#!/bin/bash
#SBATCH --job-name=simulation
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#
# Not --exclusive, for the reason the other untimed grids give: these cells declare
# timing_trusted false, and exclusivity would bill 510 cores against a 600-CPU quota.

#SBATCH --output=%x-%j.log
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir simulation

echo "running on $(hostname)"

# Protocol.md 2.1's control. Thirteen cells: the un-injected simulated reference, whose flags are
# false positives in the strict sense that 2.4 says real data cannot offer, and twelve injected ones
# across three distances and four k.
#
# Both tools, because the control is about the method rather than about the fork: if recall is low
# here, where every label is certain and the alignment is exact by construction, the limit is not
# in the data.
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/simulated/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25,upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "simulation_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/simulated"
