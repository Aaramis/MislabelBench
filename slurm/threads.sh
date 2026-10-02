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
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir threads

echo "running on $(hostname)"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets2k.json" \
  --datasets gtdb_arc2k \
  --conditions upstream_raxml_T1,upstream_raxml_T8,upstream_raxml_T16,epang_T1_K25,epang_T8_K25,epang_T16_K25 \
  --sativa_taxcode BAC \
  --replicates 3 \
  --timing_trusted true \
  --outdir "$BENCH_ROOT/results/threads"
