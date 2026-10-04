#!/bin/bash
#SBATCH --job-name=sizes
#SBATCH --cpus-per-task=140
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# Pinned to one CPU model. The partition mixes xeon-e5-2695, epyc-7662, epyc-9554 and epyc-9754
# nodes, and between the oldest and the newest there is roughly a factor of two per core, so two
# timed runs that land on different models are not comparable. 18 nodes carry this feature.
#SBATCH --constraint=epyc-9754
#
# The size gradient the protocol promises, which until now had two points out of five. Both tools at
# 402, 801, 2023, 4001 and 7051 sequences, three replicates, timed.
#
# 140 cores of 254 are reserved rather than the node held exclusively, because --exclusive bills all
# 254 against a 600-CPU per-user quota and would make this the only job we can run. That check has
# since landed: D39 found reserving most of a node times the same as holding it and more
# reproducibly, which is what threads.sh already states. Every timing here still carries the model
# and the allocation it ran under, so it can be rechecked rather than re-run.
#
# Every subset is drawn by whole taxa from the alignment, not from the ragged release file, and their
# judgeability at species runs 73.8 to 76.2 % against 72.7 % for the source, so the sizes are
# comparable in difficulty and not just in count.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir sizes

echo "running on $(hostname)"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets_sizes.json" \
  --datasets all \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --replicates 3 \
  --timing_trusted true \
  --trace_tag "sizes_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/sizes"
