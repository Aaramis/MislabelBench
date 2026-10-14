#!/bin/bash
#SBATCH --job-name=baselinebac2k
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --constraint=epyc-9754
#SBATCH --output=%x-%j.log
#
# The un-injected bacterial subset under both tools, which bac.sh did not run: its fifteen cells are
# injected into gtdb_bac2k, and aggregate_grid.py reports each cell's flags against the same tool's
# flags on the un-injected subset (added_vs_baseline), which for the archaea is results/baseline2k.
# Without this the bacterial grid summaries carry no baseline column. Timed, same CPU model as the
# clade baseline, so the two tools' seconds on 2 008 bacterial sequences are usable beside the
# archaeal 2 023.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env
echo "running on $(hostname)"

nf_launch_dir baseline_bac2k
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets_bac.json" \
  --datasets gtdb_bac2k \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted true \
  --trace_tag "baseline_bac2k_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/baseline_bac2k"
