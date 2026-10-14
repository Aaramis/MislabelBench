#!/bin/bash
#SBATCH --job-name=placementsup
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=06:00:00
#SBATCH --output=%x-%j.log
#
# The upstream half of slurm/placements.sh again, for one file the first run did not keep.
#
# Upstream's leave-one-out jplace (RAxML -f O) carries edge numbers and no tree; the tree they refer
# to, with its {n} labels, lives in the run's .refjson, which the SATIVA process did not declare as an
# output and cleanup = true then deleted with the work directory. The 2023 placements came home
# unreadable. modules/local/sativa/main.nf now emits the refjson beside the jplace and KEEPPLACEMENTS
# copies it; this reruns the one upstream cell, into the same results tree. The fork's half is not
# rerun: its folds carry ref.nwk already. SATIVA seeds RAxML with a fixed -p, so the .mis this
# produces is expected to equal the committed one byte for byte, which is checked on repatriation.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env
echo "running on $(hostname)"
room_for 2000
nf_launch_dir placements_kexact

nextflow run "$BENCH_ROOT" -profile ifb \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets inj_family_r0.05_k2_s1 \
  --conditions upstream_raxml_T8 \
  --keep_placements true \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "placements_kexact_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/placements_kexact"

echo "kept for upstream:"
ls "$BENCH_ROOT"/results/placements_kexact/placements/inj_family_r0.05_k2_s1__upstream_raxml_T8__rep1/upstream/
