#!/bin/bash
#SBATCH --job-name=raggedgrid
#SBATCH --cpus-per-task=140
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# What does an incomplete lineage cost detection? The cells are the grid's own, at family distance
# and the top rate, with a quarter of the untouched lineages cut to genus and a quarter to family
# (slurm/make_ragged.sh). The injected sequences keep their full lineage, so the truth is unchanged
# and recall is comparable cell for cell with results/grid_fork and results/grid_upstream.
#
# Both tools, because slurm/ragged_check.sh only ever ran the fork: whether SATIVA accepts ragged
# lineages at all is unmeasured, and if the two differ that is itself the answer.
#
# Not --exclusive and no pinned model: these cells answer a detection question and declare
# timing_trusted false, so no figure can pick their seconds up.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir ragged
echo "running on $(hostname)"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/ragged/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25,upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "ragged_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/ragged"
