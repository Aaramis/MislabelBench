#!/bin/bash
#SBATCH --job-name=baseline
#SBATCH --cpus-per-task=16
# 128G, matching sizes.sh, which runs the same 7051-sequence set. 48G was 33% headroom over a
# measured process-tree peak of 36 GB, and the peak was not known when 48 was chosen: run.json's
# max_rss_mb said 9.4 GB. The scaling job on the same dataset was OOM-killed at 32G, which is how
# close this was.
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --exclusive

#SBATCH --output=%x-%j.log
#
# Pinned to one CPU model. The partition mixes xeon-e5-2695, epyc-7662, epyc-9554 and epyc-9754
# nodes, and between the oldest and the newest there is roughly a factor of two per core, so two
# timed runs that land on different models are not comparable. 18 nodes carry this feature, which
# is enough for every node count the CPU quota allows.
#SBATCH --constraint=epyc-9754
set -euo pipefail

# Slurm copies the batch script to /var/spool, so $0 does not point at the repo.
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
require_singularity

nextflow_env
nf_launch_dir baseline

echo "running on $(hostname), singularity at $(command -v singularity)"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets.json" \
  --datasets gtdb_arc1200 \
  --timing_trusted true \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --trace_tag "baseline_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/baseline"
