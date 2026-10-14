#!/bin/bash
#SBATCH --job-name=placements
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# Re-run a few cells keeping the placement files, which every run so far threw away.
#
# Two questions need them and neither can be answered from a .mis. The protocol's type-2 mechanism
# -- removing one of k co-labelled relatives leaves the placement to land among the k-1 that still
# carry the wrong label -- has only ever been inferred from recall; with the jplace and the fold's
# tree one can see where each injected sequence actually landed. And the co-author's suggestion on
# the engine disagreement, "compare the placements for those cases where results deviate", needs
# both engines' placements of the same sequence in the same cell.
#
# Which cells. inj_family_r0.05_k2_s1 is the Kexact cell with the largest one-sided set (30 flags
# the fork makes alone), run under both tools with one fold per sequence so every deviating
# sequence has its own jplace in each. One Kexact cell and not three: at 2 023 folds a staged
# Kexact cell is six thousand small files, against a home quota of 100 000, and the question is
# answered by the sequences a cell holds, not by the count of cells. Then two K25 cells for the k-1
# question at the k where the law bites, species k=5 and family k=10, under the production condition.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env

echo "running on $(hostname)"
room_for 20000

nf_launch_dir placements_kexact
nextflow run "$BENCH_ROOT" -profile ifb -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets inj_family_r0.05_k2_s1 \
  --conditions epang_T8_Kexact,upstream_raxml_T8 \
  --staged true \
  --folds_per_job 506 \
  --keep_placements true \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "placements_kexact_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/placements_kexact"

nf_launch_dir placements_k25
nextflow run "$BENCH_ROOT" -profile ifb -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets inj_species_r0.05_k5_s1,inj_family_r0.05_k10_s1 \
  --conditions epang_T8_K25 \
  --staged true \
  --folds_per_job 7 \
  --keep_placements true \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "placements_k25_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/placements_k25"

echo "placement files kept:"
find "$BENCH_ROOT/results/placements_kexact" "$BENCH_ROOT/results/placements_k25" -name '*.jplace' | wc -l
