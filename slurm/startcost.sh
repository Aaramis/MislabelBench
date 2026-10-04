#!/bin/bash
#SBATCH --job-name=startcost
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=140
#SBATCH --mem=32G
#SBATCH --time=0:20:00
#SBATCH --constraint=epyc-9754
#SBATCH --output=%x-%j.log
# Why is placement on four nodes slower than on one?
#
# Two candidates: starting four singularity containers whose image sits on ceph, and four tasks
# reading an 82 MB task directory of many small files from the same ceph. This separates them: the
# same srun fan-out, once doing nothing but starting the container and exiting, once also reading the
# task directory. Whatever the first costs is not I/O on the data.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* | head -1)
# The task directory to read, and a check that it is there. This was hardcoded to
# results/scaling/N4_c140_r1, a name scaling.sh stopped producing when SCALING_DATASET put the
# dataset in the path (D82): it survives only as a leftover of the first round on one machine and
# does not exist in a clone. With no guard, a missing directory made the bind mount or the read fail
# and the bare waits below swallowed it, so the "start + read taskdir" column would have timed four
# tasks reading nothing and reported it as fast -- inverting the conclusion this script exists for.
TASKDIR="${STARTCOST_TASKDIR:-$BENCH_ROOT/results/scaling/gtdb_arc1200_N4_c140_r1/run.l1o_tasks}"
[ -d "$TASKDIR" ] && [ -n "$(ls -d "$TASKDIR"/fold_0* 2>/dev/null)" ] || {
    echo "no fold directories under $TASKDIR; set STARTCOST_TASKDIR to a scaling run's run.l1o_tasks" >&2
    exit 1
}
bytes=$(cat "$TASKDIR"/fold_0*/*.fasta 2>/dev/null | wc -c | tr -d ' ')
echo "reading $TASKDIR: $(ls -d "$TASKDIR"/fold_0* | wc -l | tr -d ' ') fold dirs, $bytes bytes of fasta"
now() { date +%s.%N; }

# Every background srun is waited on by pid and its status checked. A bare wait returns the status
# of the last job only, and set -e does not fire for a background one, which is the fault
# scaling.sh documents having been bitten by: an OOM-killed placement task went unnoticed and
# surfaced four stages later. Both loops here had it.
wait_all() {
    local st rc=0 pid
    for pid in "$@"; do
        st=0; wait "$pid" || st=$?
        [ "$st" = "0" ] || { echo "a task failed with status $st" >&2; rc=1; }
    done
    [ "$rc" = "0" ] || { echo "the timings below would be meaningless" >&2; exit 1; }
}

for n in 1 2 4; do
  t0=$(now)
  pids=()
  for i in $(seq 0 $((n - 1))); do
    srun --exclusive -N1 -n1 -c 8 singularity exec "$IMG" true &
    pids+=($!)
  done
  wait_all "${pids[@]}"
  t1=$(now)
  # Reads every fasta in the fold directories and insists it got bytes. The previous form was
  # `cat ref.fasta 2>/dev/null || cat query.fasta`, which treats a missing directory as a
  # successful fast read.
  pids=()
  for i in $(seq 0 $((n - 1))); do
    srun --exclusive -N1 -n1 -c 8 singularity exec -B "$TASKDIR:$TASKDIR" "$IMG" \
      sh -c "n=\$(cat $TASKDIR/fold_0*/*.fasta | wc -c); [ \"\$n\" -gt 0 ]" &
    pids+=($!)
  done
  wait_all "${pids[@]}"
  t2=$(now)
  printf "N=%d  container start only %6.2f s   start + read taskdir %6.2f s\n" \
    "$n" "$(echo "$t1 - $t0" | bc)" "$(echo "$t2 - $t1" | bc)"
done
