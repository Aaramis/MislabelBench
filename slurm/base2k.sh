#!/bin/bash
#SBATCH --job-name=base2k
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --exclusive
#SBATCH --output=%x-%j.log
#
# Pinned to one CPU model. The partition mixes xeon-e5-2695, epyc-7662, epyc-9554 and epyc-9754
# nodes, and between the oldest and the newest there is roughly a factor of two per core, so two
# timed runs that land on different models are not comparable. 18 nodes carry this feature, which
# is enough for every node count the CPU quota allows.
#SBATCH --constraint=epyc-9754
#
# Both tools on the un-injected 2 000-sequence subset. This is the baseline every injection cell
# is read against, and the timed comparison at that size, so it takes the node to itself and
# timing_trusted is true.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir base2k

echo "running on $(hostname)"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets2k.json" \
  --datasets gtdb_arc2k \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted true \
  --trace_tag "base2k_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/baseline2k"
