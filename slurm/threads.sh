#!/bin/bash
#SBATCH --job-name=threads
#SBATCH --cpus-per-task=140
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# Pinned to one CPU model, because the partition mixes four generations and between the oldest and
# the newest there is roughly a factor of two per core.
#SBATCH --constraint=epyc-9754
#
# The thread axis the protocol promises, at 1, 8 and 16, both tools, three replicates, on the
# 2000-sequence subset. One size, because the question is how each tool uses the threads it is given
# and that does not need the whole gradient repeated.
#
# 140 cores are reserved rather than the node held exclusively: exclusivity bills all 510 of an
# epyc-9754 against a 600-CPU quota, and reserving most of a node was measured to time the same and
# more reproducibly than holding it.
#
# What this is expected to show, so that a null result is readable: upstream uses 7.97 of 8 threads,
# so 16 should help it; the fork uses 4.4 of 8 at this size, so 16 should not. If both improve, the
# fork's thread utilisation is not the ceiling it looks like.
# THREADS_DATASET and THREADS_CONDITIONS narrow the axis to another size or to one thread count.
# A co-author's comment is that "a large speed gain" runs together three quantities --
# the sequential gain from the placement engine, the time to completion, and the accumulated CPU time --
# and the sequential one is the only axis this script measures. It had one size, 2 023 sequences, so the
# sequential ratio had no size dependence at all: 9.2x in wall clock and 18.4x in core-seconds, at one
# point. The thread axis proper stays at 2 023, which is what the comment above is about; these two
# variables exist to put the T1 pair at the other sizes the gradient already holds.
#
#   THREADS_DATASET=gtdb_arc400 THREADS_CONDITIONS=upstream_raxml_T1,epang_T1_K25 \
#       slurm/submit.sh slurm/threads.sh
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env

DS="${THREADS_DATASET:-gtdb_arc2k}"
CONDS="${THREADS_CONDITIONS:-upstream_raxml_T1,upstream_raxml_T8,upstream_raxml_T16,epang_T1_K25,epang_T8_K25,epang_T16_K25}"
# datasets2k.json holds only gtdb_arc2k; the gradient's other sizes are in datasets_sizes.json.
MANIFEST="$BENCH_ROOT/data/gtdb/datasets2k.json"
[ "$DS" = "gtdb_arc2k" ] || MANIFEST="$BENCH_ROOT/data/gtdb/datasets_sizes.json"

nf_launch_dir "threads_${DS}"

echo "running on $(hostname): $DS, $CONDS"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$MANIFEST" \
  --datasets "$DS" \
  --conditions "$CONDS" \
  --sativa_taxcode BAC \
  --replicates 3 \
  --timing_trusted true \
  --trace_tag "threads_${DS}_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/threads"
