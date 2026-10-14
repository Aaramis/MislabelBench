#!/bin/bash
#SBATCH --job-name=memstep
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=4:00:00
#SBATCH --output=%x-%j.log
#
# Where does the fork's memory per sequence step up?
#
# results/resource_usage.txt gives 4.59, 4.47 and 4.61 MB per sequence at 402, 801 and 2 023
# sequences and 5.14 and 5.13 at 4 001 and 7 051: two flat regimes with a 12 % gap and no overlap,
# measured over 3, 3, 8, 3 and 15 runs of epang_T8_K25. The step is therefore between 2 023 and
# 4 001, and none of the tool's four size thresholds is -- epac/config.py sets CAT_LOWER_THRES 100,
# CAT_GAMMA_THRES 500, EPA_HEUR_THRES 1000 and GAMMA_UPPER_THRES 10000 -- so it is not a configured
# switch. README tells a reader to extrapolate from the large-reference 5.13 and says the cause is
# unknown, which is worth narrowing rather than leaving.
#
# One point halves the interval. 3 000 sequences: 4.6 puts the step above 3 000, 5.14 below it.
#
# The subset is built here rather than committed, from the committed source and the seed convention
# every other subset uses, so the measurement needs nothing this repository does not already hold.
# bin/subset_taxa.py takes whole species groups, which bin/verify_manifests.py now checks, and the
# record it writes carries the source's digest. If the answer is worth keeping, the subset is
# regenerated on any machine from the same two arguments.
#
# Untimed on purpose: --timing_trusted false. The peak comes from the Nextflow trace's peak_rss,
# which is recorded whatever the timing flag says, and this job has no claim on seconds.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
nextflow_env
export PATH="$BENCH_ROOT/bin:$PATH"

# MEMSTEP_DATASET names a size the repository already holds, from data/gtdb/datasets_sizes.json, and
# skips the subset build. That is how the same script answers the second question: the peak at 2 023
# sequences is 1.11 MB/seq at one thread and 4.61 at eight, so it is dominated by the four placements
# the tool runs concurrently rather than by the reference. If the rise in MB/seq with size is a
# property of that concurrency it should vanish at one thread, and if it is a per-placement structure
# it should not. Two runs of epang_T1_K25, at the smallest and largest committed sizes, separate them.
CONDITION="${MEMSTEP_CONDITION:-epang_T8_K25}"
cd "$BENCH_ROOT"
if [ -n "${MEMSTEP_DATASET:-}" ]; then
    NAME="$MEMSTEP_DATASET"
    MANIFEST="$BENCH_ROOT/data/gtdb/datasets_sizes.json"
    n=$(python3 -c "
import json, sys
m = json.load(open('$MANIFEST'))
for d in m['datasets']:
    if d['name'] == '$NAME':
        print(d['n_seqs']); break
else:
    sys.exit('$NAME is not in $MANIFEST')")
    echo "dataset $NAME from the committed manifest: $n sequences"
else

TARGET="${MEMSTEP_TARGET:-3000}"
NAME="gtdb_arc${TARGET}"

if [ ! -s "data/gtdb/$NAME.tax" ]; then
    subset_taxa.py data/gtdb/gtdb_arc1200.aligned.fasta data/gtdb/gtdb_arc1200.tax \
        --target "$TARGET" --seed 42 --prefix "data/gtdb/$NAME"
fi
n=$(grep -c '^>' "data/gtdb/$NAME.fasta")
width=$(python3 -c "
import sys
seq = []
for l in open('data/gtdb/$NAME.fasta'):
    if l.startswith('>'):
        if seq: break
    else: seq.append(l.strip())
print(len(''.join(seq)))")
echo "subset $NAME: $n sequences, $width columns"

MANIFEST="$BENCH_ROOT/data/gtdb/datasets_${NAME}.json"
python3 - "$NAME" "$n" "$width" > "$MANIFEST" <<'PYJ'
import json, sys
name, n, width = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
json.dump({"source": f"{name}, a size point between the benchmark's 2 023 and 4 001",
           "datasets": [{"name": name, "n_seqs": n, "aln_len": width,
                         "fasta": f"data/gtdb/{name}.fasta", "tax": f"data/gtdb/{name}.tax"}]},
          sys.stdout, indent=2)
PYJ
fi

nf_launch_dir "memstep_${NAME}_${CONDITION}"
nextflow run "$BENCH_ROOT" -profile singularity \
  --datasets_json "$MANIFEST" \
  --datasets "$NAME" \
  --conditions "$CONDITION" \
  --sativa_taxcode BAC \
  --timing_trusted false \
  --trace_tag "memstep_${NAME}_${CONDITION}_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/memstep_${NAME}_${CONDITION}"

# The answer, from the trace rather than from run.json: run.json's max_rss_mb is the largest single
# child and the law is stated on the process tree. resource_usage.py explains the 3.7x between them.
python3 - "$BENCH_ROOT/results/memstep_${NAME}_${CONDITION}/pipeline_info" "$n" <<'PYJ'
import csv, glob, os, re, sys
UNITS = {"B": 1/1048576, "KB": 1/1024, "MB": 1, "GB": 1024, "TB": 1048576}
info, n = sys.argv[1], int(sys.argv[2])
for p in sorted(glob.glob(os.path.join(info, "trace-*.txt"))):
    for r in csv.DictReader(open(p), delimiter="\t"):
        if r["status"] == "COMPLETED" and r["name"].startswith("SATIVAEPANG "):
            m = re.match(r"([\d.]+)\s*(B|KB|MB|GB|TB)", r.get("peak_rss") or "")
            if m:
                mb = float(m.group(1)) * UNITS[m.group(2)]
                print(f"process-tree peak {mb:.0f} MB over {n} sequences "
                      f"-> {mb / n:.2f} MB/seq")
                print("4.6 puts the step above this size, 5.14 below it.")
PYJ
