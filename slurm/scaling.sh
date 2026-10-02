#!/bin/bash
#SBATCH --job-name=scaling
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --exclusive
#SBATCH --output=%x-N%N-%j.log
#
# Parallel efficiency of the staged leave-one-out, which is the one number upstream SATIVA
# cannot produce at any cost: it has no way to place folds anywhere but in its own process.
#
# Submit once per node count:
#   sbatch --nodes=1 slurm/scaling.sh
#   sbatch --nodes=4 slurm/scaling.sh
#
# The split is measured, not assumed to be free: reference and loo-tasks run once and are
# timed separately, the N placement jobs are timed from the first starting to the last
# finishing, and loo-score runs once at the end. Only the placement step can be spread, so
# reporting the three phases separately is what makes the speedup readable rather than
# flattered by the serial parts.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

N="${SLURM_JOB_NUM_NODES:-1}"
THREADS="${SLURM_CPUS_PER_TASK:-8}"
ROOT="$HOME/bench"
# Nextflow and `singularity pull` name their cached images differently, so find it rather
# than spell it: the version is what must be pinned, not the file name.
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
[ -n "$IMG" ] || { echo "sativa-epang 0.10.2 image not in $HOME/.singularity_cache" >&2; exit 1; }
OUT="$ROOT/results/scaling/N${N}"
ALN="$ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$ROOT/data/gtdb/gtdb_arc2k.tax"

rm -rf "$OUT"
mkdir -p "$OUT"
cd "$OUT"
cp "$ALN" aln.fasta
cp "$TAX" tax.tsv

se() { singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" sativa-epang "$@"; }

now() { date +%s.%N; }
t0=$(now)
se -s aln.fasta -t tax.tsv -x BAC -n run -o "$OUT" -T "$THREADS" -stage reference
t1=$(now)
se -r "$OUT/run.refjson" -n run -o "$OUT" -T "$THREADS" -stage loo-tasks
t2=$(now)

# One placement task per node, each taking every Nth fold. -folds i/N needs no knowledge of
# how many folds there are, which is the point of the stride form for a fan-out.
for i in $(seq 0 $((N - 1))); do
    srun --exclusive -N1 -n1 -c "$THREADS" \
        singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" \
        sativa-epang -stage loo-place -taskdir "$OUT/run.l1o_tasks" -T "$THREADS" -folds "${i}/${N}" &
done
wait
t3=$(now)

se -r "$OUT/run.refjson" -n run -o "$OUT" -T "$THREADS" -stage loo-score -taskdir "$OUT/run.l1o_tasks"
t4=$(now)

python3 - "$N" "$THREADS" "$t0" "$t1" "$t2" "$t3" "$t4" <<'PY' > "$OUT/timing.json"
import json, sys
n, threads = int(sys.argv[1]), int(sys.argv[2])
t = [float(x) for x in sys.argv[3:8]]
print(json.dumps({
    "nodes": n, "threads_per_node": threads,
    "reference_sec": round(t[1] - t[0], 2),
    "loo_tasks_sec": round(t[2] - t[1], 2),
    "loo_place_sec": round(t[3] - t[2], 2),
    "loo_score_sec": round(t[4] - t[3], 2),
    "total_sec": round(t[4] - t[0], 2),
}, indent=2))
PY

echo "--- N=$N ---"
cat "$OUT/timing.json"
grep -vc '^;' "$OUT/run.mis" | xargs -I{} echo "flags: {}"
