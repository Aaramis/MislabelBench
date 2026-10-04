#!/bin/bash
#SBATCH --job-name=m1check
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=2:00:00
#SBATCH --exclusive
#SBATCH --constraint=epyc-9754
#SBATCH --output=%x-%j.log
#
# M1's success criterion, which was never actually met: "the new harness landing on the v1 figure
# for upstream at 1 thread (~109 s) within run-to-run variation", and the plan adds "if it
# disagrees, stop and find out why before going further".
#
# The one run that exists, results/nf, says 142.8 s -- 31% above v1's 109.0 s and far outside v1's
# own 108.8 to 111.6 spread. It landed on cpu-node-109, an epyc-9554, and recorded no cpu_model,
# while v1 measured on a 32-core workstation with 502 GB. So the two numbers were never from the
# same machine and the criterion as written could not be met by anything.
#
# This measures it where every other timed figure in this benchmark is measured: one epyc-9754 held
# exclusively, the model pinned. Three replicates, because v1's figure is a range over replicates
# and a single run cannot be compared with one.
#
# What it settles is narrow and worth settling: whether the gap is the harness or the hardware. The
# detection results do not depend on it -- they are counts, not seconds -- but M1 is the step that
# was supposed to license everything after it.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
nextflow_env
nf_launch_dir m1_check

nextflow run "$BENCH_ROOT" -profile singularity \
  --datasets_json "$BENCH_ROOT/data_ascii/datasets.json" \
  --datasets n800 \
  --conditions upstream_raxml_T1 \
  --replicates 3 \
  --sativa_taxcode BOT \
  --timing_trusted true \
  --trace_tag "m1_check_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/m1_check"

export PATH="$BENCH_ROOT/bin:$PATH"
echo
echo "=== v1 reported 109.0 s, range 108.8 to 111.6, on a 32-core workstation"
echo "=== the single M1 run recorded 142.8 s on cpu-node-109, an epyc-9554"
echo "=== this run, on an exclusive epyc-9754:"
python3 - "$BENCH_ROOT/results/m1_check" <<'PY'
import glob, json, statistics as st, sys
v = []
for f in sorted(glob.glob(f"{sys.argv[1]}/runs/*/run.json")):
    d = json.load(open(f))
    v.append(d["wall_sec"])
    print(f"  {d['run_name']:34} {d['wall_sec']:7.1f} s  {d.get('cpu_model', 'model not recorded')}")
if v:
    print(f"  median {st.median(v):.1f} s over {len(v)} replicates, spread {max(v) - min(v):.1f}")
PY
