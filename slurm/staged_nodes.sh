#!/bin/bash
#SBATCH --job-name=stagednodes
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=12:00:00
#SBATCH --output=%x-%j.log
#
# The four-shard round with every shard on a different machine.
#
# Nine rounds of slurm/staged_timed.sh put all their shards on cpu-node-121, so the 3.65x they
# measured is distribution across Slurm jobs sharing one node's memory bandwidth, and the protocol
# now says "jobs" for that reason. This is the other measurement: params.shard_nodes pins shard i
# to the i-th of four epyc-9754 nodes with --nodelist, chosen here from sinfo at submission so the
# list is what the cluster had free and not a guess written months earlier. The nodes go in the log
# and, through slurm/shard_nodes.sh afterwards, in the trace table that bin/staged_rounds.py reads.
#
# Three replicates, chained with --dependency=afterany like the one-node set:
#
#   prev=; for r in 1 2 3; do
#     out=$(STAGED_REP=$r slurm/submit.sh slurm/staged_nodes.sh ${prev:+--dependency=afterany:$prev})
#     prev=${out##* }
#   done
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
nextflow_env
export PATH="$BENCH_ROOT/bin:$PATH"

REP="${STAGED_REP:-}"
TAG="n4${REP:+_r$REP}"

# Four distinct epyc-9754 nodes, idle or mixed first so the pins do not queue behind full nodes, and
# from the partition this job runs in: the shards are submitted to the same partition, and a
# --nodelist naming a node of another one is refused by sbatch as "Requested node configuration is
# not available", which is how the first three rounds died nine minutes in. Chosen inside the job
# rather than at submission: a node free when the chain was submitted is not necessarily free when
# replicate three starts, and a pin to a full node waits for it.
PART="${SLURM_JOB_PARTITION:-fast}"
NODES="${SHARD_NODES:-$(sinfo -N -h -p "$PART" -t idle,mix -o '%N %f' | awk '$2 ~ /epyc-9754/ {print $1}' \
        | sort -u | head -4 | paste -sd, -)}"
n=$(echo "$NODES" | tr ',' '\n' | grep -c .)
[ "$n" = 4 ] || { echo "need four idle or mixed epyc-9754 nodes in partition $PART, found $n: '$NODES'" >&2; exit 1; }
# Checked again at this moment, because the first round pinned a shard to cpu-node-121 between
# sinfo listing it mixed and Slurm draining it, and the shard then sat on ReqNodeNotAvail for an
# hour while the rest of the round waited. A node that is no longer idle or mixed fails the job
# here, in one line, and the next replicate picks afresh.
for node in $(echo "$NODES" | tr ',' ' '); do
    state=$(sinfo -N -h -n "$node" -o '%T' | head -1)
    case "$state" in idle|mixed|mix) ;; *) echo "$node is $state, not idle or mixed; refusing the pin" >&2; exit 1;; esac
done
echo "shards pinned to: $NODES"
nf_launch_dir "staged_nodes_${TAG}"

nextflow run "$BENCH_ROOT" -profile ifb \
  --datasets_json "$BENCH_ROOT/data/gtdb/datasets.json" \
  --datasets gtdb_arc1200 \
  --conditions epang_T8_K25 \
  --staged true \
  --folds_per_job 7 \
  --shard_nodes "$NODES" \
  --sativa_taxcode BAC \
  --timing_trusted true \
  --trace_tag "staged_nodes_${TAG}_${SLURM_JOB_ID:-local}" \
  --outdir "$BENCH_ROOT/results/staged_nodes_${TAG}"

# Which node each shard really ran on, from sacct, so the pin is checked and not trusted.
bash "$BENCH_ROOT/slurm/shard_nodes.sh" "$BENCH_ROOT/results/staged_nodes_${TAG}"
staged_scaling.py --staged-dir "$BENCH_ROOT/results/staged_nodes_${TAG}/staged" \
    --trace-dir "$BENCH_ROOT/results/staged_nodes_${TAG}/pipeline_info"
