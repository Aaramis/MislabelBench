#!/bin/bash
#SBATCH --job-name=inputschk
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=2:00:00
#SBATCH --output=%x-%j.log
#
# One cell under both tools, so that verify_inputs.py has something to compare.
#
# The comparison rests on both tools reading the identical database in every cell. That was true by
# construction -- main.nf resolves one path per cell and hands it to both branches -- and unprovable
# from the records, which carried the dataset's name and not its content. The tool modules now write
# the sha256 of what they read.
#
# Untimed on purpose: the question is whether the two digests match, not how long the runs take, so
# the conditions may share a node.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
export PATH="$BENCH_ROOT/bin:$PATH"
require_singularity
nextflow_env
nf_launch_dir inputs_check

CELL="${INPUTS_CELL:-inj_family_r0.05_k2_s1}"
nextflow run "$BENCH_ROOT" -profile singularity \
  --datasets_json "$BENCH_ROOT/data/injected/datasets.json" \
  --datasets "$CELL" \
  --conditions upstream_raxml_T8,epang_T8_K25 \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "inputs_check_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/inputs_check"

echo
echo "=== the digests each tool recorded"
python3 - "$BENCH_ROOT/results/inputs_check" <<'PY'
import glob, json, sys
rows = {}
for f in sorted(glob.glob(f"{sys.argv[1]}/runs/*/run.json")):
    d = json.load(open(f))
    rows[d["condition"]] = d.get("inputs")
    print(f"  {d['condition']:22} {d.get('inputs')}")
vals = [v for v in rows.values() if v]
if len(vals) < 2:
    sys.exit("fewer than two conditions recorded their inputs")
if all(v == vals[0] for v in vals):
    print("VERDICT: both tools read the same bytes")
else:
    sys.exit("VERDICT: the two tools read different files")
PY
# Back to the root: nf_launch_dir left us in $BENCH_ROOT/.nf/inputs_check, where the gate's
# relative glob matches nothing -- which it did, reporting zero cells and exiting 0.
cd "$BENCH_ROOT"
verify_inputs.py --glob "results/inputs_check/runs/*/run.json"
