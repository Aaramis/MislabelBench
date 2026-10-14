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
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
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
#
# Against a digest and not against the file. The single-process .mis lives under results/baseline2k/
# in the repository and never reaches the cluster: bin/restore_cluster.sh says "results/ travels the
# other way" and leaves results/ empty by construction, so this compared against a file that is here
# only on a cluster still holding the run from the day it was produced there. It stopped working when
# the cluster was rebuilt, and said "no single-process .mis at ...", which reads as a missing input
# rather than as a check that cannot run where it runs. assets/staged_check_reference.sha256 travels
# with the code, and bin/verify_manifests.py holds it to the committed file.
single=$BENCH_ROOT/results/baseline2k/runs/gtdb_arc2k__epang_T8_K25__rep1/gtdb_arc2k__epang_T8_K25__rep1.mis
expected=$(grep -v '^#' "$BENCH_ROOT/assets/staged_check_reference.sha256" | awk 'NF{print $1; exit}')
staged=$(ls "$BENCH_ROOT"/results/staged_check/runs/*/*.mis 2>/dev/null | head -1)
[ -n "$expected" ] || { echo "no digest in assets/staged_check_reference.sha256" >&2; exit 1; }
[ -n "$staged" ] && [ -s "$staged" ] || { echo "the staged path produced no .mis" >&2; exit 1; }
got=$(sha256sum "$staged" | cut -d' ' -f1)
echo "expected: $expected"
echo "staged:   $got  ($(grep -vc '^;' "$staged") flags)"
if [ -s "$single" ]; then
    echo "the committed file is here too: $(sha256sum "$single" | cut -d' ' -f1)"
fi
if [ "$got" = "$expected" ]; then
    echo "VERDICT: byte identical"
else
    echo "VERDICT: they differ" >&2
    diff <(grep -v '^;' "$single" | cut -f1 | sort) \
         <(grep -v '^;' "$staged" | cut -f1 | sort) | head -20
    exit 1
fi
