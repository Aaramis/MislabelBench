#!/bin/bash
#SBATCH --job-name=stagedchk
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=4:00:00
#SBATCH --output=%x-%j.log
#
# Does the four-stage path produce the same .mis as the single-process one?
#
# That is the question to answer before any timed distributed run, because the staged path exists to
# measure distribution and a measurement of a different computation is worth nothing. Untimed on
# purpose: --timing_trusted false, so the shards may share a node and the only thing compared is the
# output. bin/analyses.sh reads the .mis, so byte equality is the whole test.
#
# 2023 sequences rather than 7051: the point is equality, and the smaller set gives it in minutes.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir staged_check

nextflow run "$BENCH_ROOT" -profile singularity \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets2k.json" \
  --datasets gtdb_arc2k \
  --conditions epang_T8_K25 \
  --staged true \
  --folds_per_job "${FOLDS_PER_JOB:-7}" \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "staged_check_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/staged_check"

# The comparison, here rather than by hand, so that a run either demonstrates equality or fails.
single=$BENCH_ROOT/results/baseline2k/runs/gtdb_arc2k__epang_T8_K25__rep1/gtdb_arc2k__epang_T8_K25__rep1.mis
staged=$(ls "$BENCH_ROOT"/results/staged_check/runs/*/*.mis 2>/dev/null | head -1)
[ -s "$single" ] || { echo "no single-process .mis at $single" >&2; exit 1; }
[ -n "$staged" ] && [ -s "$staged" ] || { echo "the staged path produced no .mis" >&2; exit 1; }
echo "single-process: $(grep -vc '^;' "$single") flags, $(md5sum "$single" | cut -d' ' -f1)"
echo "staged:         $(grep -vc '^;' "$staged") flags, $(md5sum "$staged" | cut -d' ' -f1)"
if cmp -s "$single" "$staged"; then
    echo "VERDICT: byte identical"
else
    echo "VERDICT: they differ" >&2
    diff <(grep -v '^;' "$single" | cut -f1 | sort) \
         <(grep -v '^;' "$staged" | cut -f1 | sort) | head -20
    exit 1
fi
