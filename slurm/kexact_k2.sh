#!/bin/bash
#SBATCH --job-name=kexact-k2
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# What produces the fork's advantage at intermediate k? It is not the engine alone: at k=1, where no
# shared label anchors anything, the two tools differ by 0.018. It is not the fold count: five folds
# against twenty-five is worth 0.035, and only at k=10. At k=2 the gap is 0.246 and most of it is
# unexplained.
#
# epang_T8_Kexact places one sequence per fold, which is strict leave-one-out with EPA-ng. It therefore
# separates the two changes cleanly:
#
#   Kexact against upstream_raxml_T8   the engine, with the folding removed
#   Kexact against epang_T8_K25        the folding, with the engine held fixed
#
# Six cells rather than the grid: k=2 at family distance, both rates, three seeds, which is where the gap
# is largest and where both other conditions already exist. One sequence per fold on 2023 sequences is
# about 2000 EPA-ng placements per cell, so the full grid would be a hundred hours and six cells is two.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir kexact_k2

cells=$(ls "$BENCH_ROOT/data/injected" | grep '^inj_family_r[0-9.]*_k2_' | paste -sd, -)
echo "running on $(hostname), cells: $cells"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets "$cells" \
  --conditions epang_T8_Kexact \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag kexact_k2 \
  --outdir "$BENCH_ROOT/results/grid_fork"
