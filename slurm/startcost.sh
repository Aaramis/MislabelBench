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
TASKDIR=$BENCH_ROOT/results/scaling/N4_c140_r1/run.l1o_tasks
now() { date +%s.%N; }

for n in 1 2 4; do
  t0=$(now)
  for i in $(seq 0 $((n - 1))); do
    srun --exclusive -N1 -n1 -c 8 singularity exec "$IMG" true &
  done
  wait
  t1=$(now)
  for i in $(seq 0 $((n - 1))); do
    srun --exclusive -N1 -n1 -c 8 singularity exec -B "$TASKDIR:$TASKDIR" "$IMG" \
      sh -c "cat $TASKDIR/fold_0*/ref.fasta > /dev/null 2>&1 || cat $TASKDIR/fold_0*/query.fasta > /dev/null" &
  done
  wait
  t2=$(now)
  printf "N=%d  container start only %6.2f s   start + read taskdir %6.2f s\n" \
    "$n" "$(echo "$t1 - $t0" | bc)" "$(echo "$t2 - $t1" | bc)"
done
