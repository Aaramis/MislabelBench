#!/bin/bash
#SBATCH --job-name=scaling
#SBATCH --ntasks-per-node=1
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=%x-N%N-%j.log
#
# Pinned to one CPU model. The partition mixes xeon-e5-2695, epyc-7662, epyc-9554 and epyc-9754
# nodes, and between the oldest and the newest there is roughly a factor of two per core, so two
# timed runs that land on different models are not comparable. 18 nodes carry this feature, which
# is enough for every node count the CPU quota allows.
#SBATCH --constraint=epyc-9754
#
# Parallel efficiency of the staged leave-one-out, which is the one number upstream SATIVA
# cannot produce at any cost: it has no way to place folds anywhere but in its own process.
#
# Submit once per node count:
#   slurm/submit.sh slurm/scaling.sh --nodes=1 --exclusive --cpus-per-task=8
#   slurm/submit.sh slurm/scaling.sh --nodes=4 --cpus-per-task=140
#
# The allocation is set by the caller, not by this script, because the two cannot be the same
# thing here. The tool always runs on SCALING_THREADS cores (8); what the caller chooses is how
# much of each node is held while it does. --exclusive is the measurement we trust, but a node has
# 254 effective cores and --exclusive bills all of them against a 600-CPU per-user quota, so it
# caps the experiment at two nodes. Reserving 140 cores per node instead fits four nodes inside
# the quota, and whether that reservation is as trustworthy as exclusivity is something to check
# at N=2, where both can be run, rather than to assume.
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
# Threads the tool uses, which is a property of the condition and not of the allocation.
THREADS="${SCALING_THREADS:-8}"
# What Slurm actually gave us per node, rather than what was asked for. Under --exclusive this
# comes back as the node's full core count, so the allocation records itself and there is no need
# to guess at a variable that may not exist.
RESERVED="${SLURM_CPUS_PER_TASK:-$THREADS}"
GOT_PER_NODE="${SLURM_JOB_CPUS_PER_NODE:-unknown}"
CPU_MODEL=$(awk -F: '/^model name/ {gsub(/^ +/, "", $2); print $2; exit}' /proc/cpuinfo)
ROOT="$HOME/bench"
# Nextflow and `singularity pull` name their cached images differently, so find it rather
# than spell it: the version is what must be pinned, not the file name.
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
[ -n "$IMG" ] || { echo "sativa-epang 0.10.2 image not in $HOME/.singularity_cache" >&2; exit 1; }
OUT="$ROOT/results/scaling/N${N}_c${SLURM_CPUS_PER_TASK:-8}_r${SCALING_REP:-1}"
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
# Same tool flags as conf/modules.config. They are not cosmetic: -m defaults to `thorough`,
# a full constrained RAxML search, so leaving it out measured a different algorithm and put
# the reference build at 249 s against the 38 s the rest of the benchmark sees.
ARGS=(-m ultrafast -C 0.4 -x BAC -p 42 -S)
se -s aln.fasta -t tax.tsv "${ARGS[@]}" -n run -o "$OUT" -T "$THREADS" -stage reference
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

se -r "$OUT/run.refjson" -C 0.4 -S -n run -o "$OUT" -T "$THREADS" -stage loo-score -taskdir "$OUT/run.l1o_tasks"
t4=$(now)

python3 - "$N" "$THREADS" "$t0" "$t1" "$t2" "$t3" "$t4" "$RESERVED" "$GOT_PER_NODE" "$CPU_MODEL" "$SLURM_JOB_NODELIST" <<'PY' > "$OUT/timing.json"
import json, sys
n, threads = int(sys.argv[1]), int(sys.argv[2])
t = [float(x) for x in sys.argv[3:8]]
print(json.dumps({
    "nodes": n, "threads_per_node": threads,
    "cores_requested_per_node": int(sys.argv[8]), "cores_allocated_per_node": sys.argv[9],
    "cpu_model": sys.argv[10], "nodelist": sys.argv[11],
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
