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
# The name says k2 because that is where it started and renaming it would orphan the trace files and
# the job-script declarations verify_runs.py checks every run against. KEXACT_CELL chooses the cell, and
# the arm now runs along k rather than at one value: k=2 seeds 1 and 2, then k=10, then k=5, at family
# distance and rate 0.05 where the other three conditions already exist.
#
# One sequence per fold on 2023 sequences is about 2000 EPA-ng placements, measured at 71 minutes a cell
# against 38 seconds at K=25, so the full grid would be a hundred hours and the axis is sampled instead.
#
# The file cost below was the other reason for one cell at a time, and the estimate was wrong. A cell was
# put at 14 500 files against a 100 000 quota, which killed a planned six-cell job before it ran.
# Measured on the k=10 run: the home went from 1 115 files to 1 164, forty-nine more, because Nextflow
# removes the work directory on success. The peak is real and the cost is not cumulative, so the limit
# is on cells running at once rather than on how many may be run.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir kexact_k2

# One cell per submission, controlled by KEXACT_CELL, because the file cost has to be measured before
# it is multiplied. One sequence per fold on 2023 sequences means 2023 fold directories of about seven
# files each, which is roughly 14000 files per cell against a 100000-file quota -- an estimate that
# killed the six-cell version of this job before it ran, and an estimate is not a measurement.
cell=${KEXACT_CELL:-inj_family_r0.05_k2_s1}
[ -d "$BENCH_ROOT/data/injected/$cell" ] || { echo "no such cell: $cell" >&2; exit 1; }
before=$(getfattr --only-values -n ceph.dir.rfiles "$HOME" 2>/dev/null)
echo "running on $(hostname), cell $cell, home holds $before files"
trap 'echo "home now holds $(getfattr --only-values -n ceph.dir.rfiles "$HOME" 2>/dev/null) files, was $before"' EXIT
cells=$cell

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets "$cells" \
  --conditions epang_T8_Kexact \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "kexact_k2_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/grid_fork"
