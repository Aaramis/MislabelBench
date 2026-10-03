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
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env

COND=upstream_raxml_T8
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

nf_launch_dir grid_up_missing
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets "$missing" \
  --conditions "$COND" \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "grid_up_missing_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/grid_fork"
