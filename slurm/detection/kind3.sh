#!/bin/bash
#SBATCH --job-name=kind3
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#
# Not --exclusive. These cells declare timing_trusted false, so exclusivity buys them nothing,
# and on this cluster it costs everything: a node has 254 effective cores and --exclusive bills
# all of them against a 600-CPU per-user quota.

#SBATCH --output=%x-%j.log
set -euo pipefail

# Slurm copies the batch script to /var/spool, so $0 does not point at the repo.
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
require_singularity

nextflow_env
nf_launch_dir kind3

echo "running on $(hostname)"

# Error kind 3: whole taxa relabelled, so nothing correctly labelled remains to confirm them.
# Both tools, because the question is whether the clade is detectable at all once leave-one-out's
# usual handle is gone, and upstream is the reference for that. Nine cells, three distances by
# three seeds, six clades each spread over the compactness range -- see bin/inject_clade.py for
# what separation means and why it is the variable.
#
# Not a timed comparison, so timing_trusted is false and several cells run at once.
nextflow run "$BENCH_ROOT" -profile singularity -resume \
  --datasets_json "$BENCH_ROOT/data/clade/datasets.json" \
  --datasets all \
  --conditions epang_T8_K25,upstream_raxml_T8 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "kind3_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/clade"
