#!/bin/bash
#SBATCH --job-name=grid-up-miss
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# The comparator on whichever cells do not have it yet, computed from the run directory rather than
# listed by hand.
#
# Why not just -resume: the work directory had to be deleted to free the file quota, so Nextflow's cache
# points at task directories that no longer exist and every cell is a miss. The published cells in
# results/ are still valid -- they are complete run directories with a .mis and a run.json -- so the
# cheapest correct thing is to ask only for what is absent. That turns fifteen hours of recomputation
# into about six hours of new work.
#
# Idempotent by construction: run it again and it asks for whatever is still missing.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env

# The condition is a parameter now. This script is the only one that asks for what is absent rather
# than for everything, which is what the grid needs whenever an axis gains a value -- the 2 % rate added
# 90 cells and `--datasets all` would have recomputed the 180 that already exist, the work directory
# having been deleted for quota so there is no resume cache to save them. The launch directory and the
# trace tag derive from the condition so two arms can run at once.
COND=${GRID_COND:-upstream_raxml_T8}
RUNS=$BENCH_ROOT/results/grid_fork/runs
missing=$(for d in "$BENCH_ROOT/data/injected"/inj_*; do
    cell=$(basename "$d")
    [ -s "$RUNS/${cell}__${COND}__rep1/run.json" ] || echo "$cell"
done | paste -sd, -)

if [ -z "$missing" ]; then
    echo "every cell already has $COND; nothing to do"
    exit 0
fi
n=$(echo "$missing" | tr ',' '\n' | wc -l)
echo "running on $(hostname), $n cells missing $COND"

nf_launch_dir "grid_missing_${COND}"
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets "$missing" \
  --conditions "$COND" \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "grid_missing_${COND}_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/grid_fork"
