#!/bin/bash
#SBATCH --job-name=base2k
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --exclusive
#SBATCH --output=%x-%j.log
#
# Both tools on the un-injected 2 000-sequence subset. This is the baseline every injection cell
# is read against, and the timed comparison at that size, so it takes the node to itself and
# timing_trusted is true.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_serialise
cd "$HOME/bench"

echo "running on $(hostname)"

nextflow run . -profile singularity -resume \
  --datasets_json data/gtdb/datasets2k.json \
  --datasets gtdb_arc2k \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted true \
  --outdir "$HOME/bench/results/baseline2k"
