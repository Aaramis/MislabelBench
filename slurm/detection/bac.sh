#!/bin/bash
#SBATCH --job-name=bacterial
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --constraint=epyc-9754
#SBATCH --output=%x-%j.log
#
# The bacterial replication, both tools: the baseline on the whole clade, timed and pinned to the CPU
# model as baseline.sh is, then the fifteen-cell k axis on the clade's subset, untimed. 128G for the
# reason baseline.sh gives: the fork's process tree peaks near 36 GB on 7 051 sequences.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env
echo "running on $(hostname)"

BAC=$(python3 -c "import json;print(json.load(open('$BENCH_ROOT/data/gtdb/datasets_bac.json'))['datasets'][0]['name'])")

nf_launch_dir baseline_bac
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets_bac.json" \
  --datasets "$BAC" \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted true \
  --trace_tag "baseline_bac_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/baseline_bac"

nf_launch_dir grid_bac
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected_bac/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25,upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "grid_bac_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/grid_bac"
