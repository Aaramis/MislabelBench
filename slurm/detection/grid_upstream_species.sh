#!/bin/bash
#SBATCH --job-name=grid-up-sp
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.log
#
# The comparator on the species cells only, run beside the main upstream grid rather than after it.
#
# That grid works in directory order, so species comes last of the six distances -- and species is the
# one that matters most to check: it is the hardest distance, 0.746 against 1.000 at phylum, and the
# caveat on the detection comparison is precisely that species and phylum are missing. Waiting for the
# main job would settle it five hours later than this does.
#
# The cost is that the main grid will recompute these 30 cells when it reaches them. Output is
# deterministic, so it overwrites with identical content; the waste is compute, and the quota is
# otherwise idle at 32 of 600 CPUs.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir grid_up_species

cells=$(ls "$BENCH_ROOT/data/injected" | grep '^inj_species_' | paste -sd, -)
echo "running on $(hostname), $(echo "$cells" | tr ',' '\n' | wc -l) species cells"

nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets "$cells" \
  --conditions upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "grid_up_species_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/grid_fork"
