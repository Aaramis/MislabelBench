#!/bin/bash
#SBATCH --job-name=stagedtimed
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=12:00:00
#SBATCH --output=%x-%j.log
#
# The distributed leave-one-out, timed, through the harness. The number to compare against is
# slurm/timing/scaling.sh on the same dataset: placement 195.59 +/- 0.67 s at one shard and 123.93 at two,
# 1.58x of an ideal 2.00. That version drives the tool with srun from inside one allocation and
# shares a task directory on ceph; this one gives every stage its own Slurm job and stages 12 MB per
# fold, so the two are not the same experiment and the difference is the point.
#
# One CPU and 4 GB: this job is only the Nextflow driver. It submits the stages and polls, and
# sbatch does work from inside a job here -- checked, a job on cpu-node-97 submitted another.
#
# FOLDS_PER_JOB sets the shard count on 25 folds: 25 gives one shard, 13 gives two, 7 gives four,
# which are the three node counts scaling.sh measured. Below four the tool loses its own internal
# concurrency and a fold costs 22 s instead of 8; see docs/distribution.md.
#
# STAGED_REP numbers a replicate of the same round. The stages no longer hold a node to themselves --
# an exclusive job is charged all 510 CPUs of an epyc-9754 against a QOS cap of 600, so two shards
# could never be scheduled, let alone four -- so what bounds the interference is the spread over
# replicates rather than an argument that nothing else was running. Round and replicate both go in
# the output directory, so no two runs can overwrite each other's trace:
#
#   for r in 1 2 3; do for f in 25 13 7; do
#     STAGED_REP=$r FOLDS_PER_JOB=$f slurm/submit.sh slurm/timing/staged_timed.sh -p fast
#   done; done
#
# Submit them chained on --dependency=afterany, not all at once. Without exclusivity our own rounds
# are each other's interference, and two rounds of this on one node is the one disturbance we can
# still rule out.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
nextflow_env

# bin on PATH, as bin/analyses.sh does. Without it the summary at the end exits 127 -- which it
# did, in all three runs, after the pipeline itself had succeeded.
export PATH="$BENCH_ROOT/bin:$PATH"

FPJ="${FOLDS_PER_JOB:-7}"
REP="${STAGED_REP:-}"
TAG="f${FPJ}${REP:+_r$REP}"
nf_launch_dir "staged_timed_${TAG}"

nextflow run "$BENCH_ROOT" -profile ifb \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets.json" \
  --datasets gtdb_arc1200 \
  --conditions epang_T8_K25 \
  --staged true \
  --folds_per_job "$FPJ" \
  --sativa_taxcode BAC \
  --timing_trusted true \
  --trace_tag "staged_timed_${TAG}_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/staged_timed_${TAG}"

# The measurement reads itself: if the shards ran concurrently the span is about the stage sum, and
# if something serialised them it is about the sum with the shards added instead of maximised.
staged_scaling.py --staged-dir "$BENCH_ROOT/results/staged_timed_${TAG}/staged" \
    --trace-dir "$BENCH_ROOT/results/staged_timed_${TAG}/pipeline_info"
