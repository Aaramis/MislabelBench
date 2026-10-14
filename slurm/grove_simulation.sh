#!/bin/bash
#SBATCH --job-name=grovesimulation
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#
# Not --exclusive, for the reason the other untimed grids give: these cells declare
# timing_trusted false, and exclusivity would bill 510 cores against a 600-CPU quota.

#SBATCH --output=%x-%j.log
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir grove_simulation

echo "running on $(hostname)"

# The same control as slurm/simulation.sh, on the RAxMLGrove reference instead of the hand-made one:
# an empirical topology, the database's own substitution model and alpha, and the source alignment's
# own missing-data pattern. It reverses the earlier choice of a hand-made tree.
#
# Run beside the hand-made one rather than instead of it. The pair is the measurement: if the fork
# and SATIVA agree on the regular reference and part ways on the empirical one, the difference is in
# the data's realism and nowhere else, which is exactly the co-author's objection.
#
# Both tools, for the reason simulation.sh gives: the control is about the method, not the fork.
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/grove_sim/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25,upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "grove_simulation_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/grove_simulated"
