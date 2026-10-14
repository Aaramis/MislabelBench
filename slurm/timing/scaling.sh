#!/bin/bash
#SBATCH --job-name=scaling
#SBATCH --ntasks-per-node=1
# 64G, not 32. The first round ran on 2023 sequences, where the fork's process-tree peak is 9.3 GB
# and 32G was ample. On gtdb_arc1200, 7051 sequences, the measured peak is 36 GB and every N=2 job
# was OOM-killed inside three minutes: six oom_kill events on one node, seven on the other. The
# tree peak is 4.76 MB per sequence at eight threads and it does not fall with the fold count,
# because what holds the memory is the reference tree and the alignment, not the folds.
#SBATCH --mem=64G
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
# The dataset matters as much as the node count. SCALING_DATASET defaults to gtdb_arc1200, 7051
# sequences, because the first round ran on 2023 where placement is under half a minute and the
# measurement was dominated by container startup; see the note beside DATASET below.
#
# Submit once per node count:
#   slurm/submit.sh slurm/timing/scaling.sh --nodes=1 --exclusive --cpus-per-task=8
#   slurm/submit.sh slurm/timing/scaling.sh --nodes=4 --cpus-per-task=140
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
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
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
ROOT="$BENCH_ROOT"
# Nextflow and `singularity pull` name their cached images differently, so find it rather
# than spell it: the version is what must be pinned, not the file name.
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
[ -n "$IMG" ] || { echo "sativa-epang 0.10.2 image not in $HOME/.singularity_cache" >&2; exit 1; }
# SCALING_TAG separates runs that differ in something the path does not already carry, which so far
# means the CPU model. The allocation-mode comparison has to happen within one model, and on this
# cluster it can only happen on the smaller one: an epyc-9754 node is dual socket with SMT, so Slurm
# counts 512 CPUs and --exclusive bills all of them against a 600 quota, while an epyc-9554 counts
# 256 and leaves room for other work to run alongside.
# The dataset is a parameter because the first round of this experiment used gtdb_arc2k, where the
# placement step is 16 to 26 seconds and the serial parts are 38.5% of the total. At that size there
# is almost nothing to divide: the Amdahl ceiling is 2.60x, N=1 to N=2 came out at 1.47x, and N=4
# regressed to 27.9 s with a spread of 7.8 against 17.4 at N=2 -- 28% of the mean, which is four
# singularity containers starting rather than a property of the distribution. gtdb_arc1200 is the
# answer and not a bigger allocation: the fork's whole run there is 262 s against 38.5 at 2023, so
# placement has something to spread.
DATASET="${SCALING_DATASET:-gtdb_arc1200}"
OUT="$ROOT/results/scaling/${DATASET}_N${N}_c${SLURM_CPUS_PER_TASK:-8}_r${SCALING_REP:-1}${SCALING_TAG:+_$SCALING_TAG}"
ALN="$ROOT/data/gtdb/${DATASET}.aligned.fasta"
TAX="$ROOT/data/gtdb/${DATASET}.tax"
[ -s "$ALN" ] || ALN="$ROOT/data/gtdb/${DATASET}.fasta"
[ -s "$ALN" ] && [ -s "$TAX" ] || { echo "no such dataset: $DATASET" >&2; exit 1; }

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
# Each shard says which node it ran on and how long it took, into its own file. Without that a
# straggler is invisible: at N=4 three shards finish in 56 to 62 s, exactly what six folds predict,
# and one takes 124 to 258 s, in all three replicates. Which node that is decides whether the cause
# is the allocation sharing a node with another tenant or something about the shard itself, and the
# combined log cannot say because the four shards interleave.
pids=()
for i in $(seq 0 $((N - 1))); do
    (
        s0=$(now)
        srun --exclusive -N1 -n1 -c "$THREADS" \
            singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" \
            sativa-epang -stage loo-place -taskdir "$OUT/run.l1o_tasks" -T "$THREADS" \
            -folds "${i}/${N}" > "$OUT/place_shard${i}.log" 2>&1
        st=$?
        node=$(srun --exclusive -N1 -n1 -c1 hostname 2>/dev/null || echo unknown)
        python3 -c "
import json, sys
json.dump({'shard': int(sys.argv[1]), 'node': sys.argv[2], 'sec': round(float(sys.argv[3]), 2),
           'status': int(sys.argv[4])}, open(sys.argv[5], 'w'))
" "$i" "$node" "$(echo "$(now) - $s0" | bc)" "$st" "$OUT/shard${i}.json"
        exit $st
    ) &
    pids+=($!)
done
# Every placement task is waited on by pid and its status checked. A bare `wait` returns the status
# of the last job only and set -e does not fire for a background one, so a task killed by the OOM
# reaper left its folds unplaced, the tool wrote empty placement files, logged "EPA-ng FAIL fold 5:"
# with no message, carried on, and the run died two minutes later in the scoring stage on
# "JSONDecodeError: Expecting value: line 1 column 1". The cause was four stages and two minutes
# away from the symptom.
failed=0
for i in "${!pids[@]}"; do
    # st captured in the || branch, not inside an `if ! wait`: there $? is the status of the
    # negation and always 0, which was checked and did report "failed with status 0".
    st=0
    wait "${pids[$i]}" || st=$?
    [ "$st" = "0" ] || { echo "placement task $i failed with status $st" >&2; failed=1; }
done
[ "$failed" = "0" ] || { echo "a placement task failed; the timings below would be meaningless" >&2; exit 1; }

# And a check that does not depend on the tool, because the tool does not fail when folds fail. An
# OOM-killed run logged "[epang-l1o] EPA-ng FAIL fold 18:" with nothing after the colon, then
# "placed 7/12 folds", and carried on; the only symptom was the scoring stage crashing on an empty
# jplace. Every fold must have a placement and no placement may be empty.
n_folds=$(python3 -c "import json; print(json.load(open('$OUT/run.l1o_tasks/manifest.json'))['n_folds'])")
n_placed=$(ls "$OUT"/run.l1o_tasks/fold_*/epa_result.jplace 2>/dev/null | wc -l | tr -d ' ')
n_empty=$(find "$OUT/run.l1o_tasks" -name epa_result.jplace -size 0 | wc -l | tr -d ' ')
[ "$n_placed" = "$n_folds" ] || { echo "only $n_placed of $n_folds folds were placed" >&2; exit 1; }
[ "$n_empty" = "0" ] || { echo "$n_empty placements are empty files" >&2; exit 1; }
echo "all $n_folds folds placed, none empty"
t3=$(now)

se -r "$OUT/run.refjson" -C 0.4 -S -n run -o "$OUT" -T "$THREADS" -stage loo-score -taskdir "$OUT/run.l1o_tasks"
t4=$(now)

N_SEQS=$(grep -c '^>' "$ALN")
python3 - "$N" "$THREADS" "$t0" "$t1" "$t2" "$t3" "$t4" "$RESERVED" "$GOT_PER_NODE" "$CPU_MODEL" "$SLURM_JOB_NODELIST" "$DATASET" "$N_SEQS" <<'PY' > "$OUT/timing.json"
import json, sys
n, threads = int(sys.argv[1]), int(sys.argv[2])
t = [float(x) for x in sys.argv[3:8]]
print(json.dumps({
    # Which set this was run on. Without it the first round on 2023 sequences and any later round
    # on 7051 group together by node count and the summary averages two different experiments.
    "dataset": sys.argv[12], "n_seqs": int(sys.argv[13]),
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
