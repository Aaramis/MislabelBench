#!/bin/bash
#SBATCH --job-name=width
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=%x-%j.log
#
# The fork on the same 2 023 sequences at five alignment widths, one thread and eight, so that the
# memory law's width term is measured and not deduced from what EPA-ng stores. Only the peak RSS of
# each run is read (bin/memory_width.py); it does not depend on the node's other occupants, so this
# job is not pinned and its timings are marked untrusted.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
echo "running on $(hostname)"
bash "$BENCH_ROOT/slurm/make_width.sh"
room_for 2000
nf_launch_dir width

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/width/datasets.json" \
  --datasets all \
  --conditions epang_T1_K25,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "width_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/width"
