#!/bin/bash
#SBATCH --job-name=regradient
#SBATCH --nodes=1
#SBATCH --exclusive
#SBATCH --constraint=epyc-9754
#SBATCH --mem=64G
#SBATCH --time=10:00:00
#SBATCH --output=%x-%j.log
#
# The size gradient re-measured end to end in ONE job on ONE exclusive node.
#
# The committed gradient already pins the CPU model and each of its points is a median over three
# to seven replicates, but its runs were separate Slurm jobs spread over days, and upstream's peak
# memory falls from 99.0 MB at 402 sequences to 56.9 at 801 and then rises monotonically. That
# inversion reproduces to 0.1 MB across replicates and survives every explanation checked against
# the records: identical alignment width, gap fraction within 0.003, duplicates and site patterns
# both monotone in n, thread occupancy 7.87 against 7.94 of 8, same CPU model. So it is either a
# real property of the tool at small sizes or something the per-job records cannot see.
#
# This removes the last variable. Both tools, all five sizes, three replicates, back to back on one
# node that nothing else is using, in one session. Whatever comes out is comparable to itself
# without any assumption about what the cluster was doing between jobs.
#
# WARNING, written after the fact: the times this produces are NOT comparable with the committed
# gradient and must not replace it. The sampler below starts a process every 0.2 s to walk /proc,
# which costs a fixed slice of one core, and the two tools absorb that differently: upstream
# saturates 7.97 of its 8 threads and has nothing spare, the fork uses 3.09 to 5.57 and absorbs it.
# Measured: upstream came out 8 to 15 % slower at every size while the fork was within 1 % at the
# three largest. Use this script for memory, which reading /proc does not disturb, and take the
# times from the pipeline's own runs. D190 in the decision log has the numbers.
#
# Memory is measured twice for every run, because the two numbers answer different questions and
# the committed records only have the first. ru_maxrss over children is the largest SINGLE child
# process, which is what run.json carries; the sampler below walks the run's own descendants every
# 0.2 s and reports both the tree total and the largest single process, so if the inversion is one
# RAxML invocation being bigger at 402 than at 801, it will say which.
set -uo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

ROOT="$BENCH_ROOT"
OUT="$ROOT/results/regradient"
REPS="${REGRADIENT_REPS:-3}"
SIZES="${REGRADIENT_SIZES:-gtdb_arc400 gtdb_arc800 gtdb_arc2k gtdb_arc4000 gtdb_arc1200}"
THREADS=8

# bin/ is not on PATH in a batch script. Nextflow puts it there for the pipeline's own processes,
# which is why nothing else here needed it, and the first run of this script lost all thirty
# measurements to "_timeit.py: command not found". Checked rather than assumed, because PATH being
# wrong is silent until the first call.
TIMEIT="$ROOT/bin/_timeit.py"
[ -x "$TIMEIT" ] || { echo "no executable $TIMEIT" >&2; exit 1; }

FORK=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
UP=$(ls "$HOME"/.singularity_cache/*sativa*0.9.3*py312h031d066_0* 2>/dev/null | grep -v epang | head -1)
[ -n "$FORK" ] && [ -n "$UP" ] || { echo "missing a container image" >&2; exit 1; }

rm -rf "$OUT"; mkdir -p "$OUT"
failed=0
echo "node $(hostname), $(nproc) cpus, model: $(awk -F: '/^model name/{gsub(/^ +/,"",$2);print $2;exit}' /proc/cpuinfo)"
printf 'dataset\tn_seqs\ttool\trep\twall_s\tru_maxrss_mb\ttree_peak_mb\tlargest_child_mb\tlargest_child\n' \
    > "$OUT/gradient.tsv"

# Every descendant of $1, sampled until it exits. Writes "rss_kb comm" lines.
sample_tree() {
    local root=$1 out=$2
    while kill -0 "$root" 2>/dev/null; do
        # The whole subtree, found by walking ppid links rather than by matching command names:
        # a name filter is how the first attempt at this captured every process on the node.
        python3 - "$root" <<'PY'
import os, sys
root = int(sys.argv[1])
kids = {}
for pid in filter(str.isdigit, os.listdir("/proc")):
    try:
        with open(f"/proc/{pid}/stat") as fh:
            f = fh.read().rsplit(") ", 1)[1].split()
        kids.setdefault(int(f[1]), []).append(int(pid))
    except OSError:
        pass
seen, stack, total = [], [root], 0
while stack:
    p = stack.pop()
    stack += kids.get(p, [])
    try:
        rss = int(open(f"/proc/{p}/statm").read().split()[1]) * os.sysconf("SC_PAGE_SIZE") // 1024
        comm = open(f"/proc/{p}/comm").read().strip()
    except OSError:
        continue
    total += rss
    seen.append((rss, comm))
if seen:
    print(f"TREE {total}")
    for rss, comm in seen:
        print(f"PROC {rss} {comm}")
PY
        sleep 0.2
    done > "$out" 2>/dev/null
}

for ds in $SIZES; do
    aln="$ROOT/data/gtdb/$ds.aligned.fasta"; [ -s "$aln" ] || aln="$ROOT/data/gtdb/$ds.fasta"
    tax="$ROOT/data/gtdb/$ds.tax"
    [ -s "$aln" ] && [ -s "$tax" ] || { echo "no such dataset: $ds" >&2; exit 1; }
    n=$(grep -c '^>' "$aln")
    for tool in fork upstream; do
        img="$FORK"; cmd=sativa-epang; extra=(-S)
        [ "$tool" = upstream ] && { img="$UP"; cmd=sativa.py; }
        for rep in $(seq 1 "$REPS"); do
            d="$OUT/${ds}__${tool}__rep${rep}"; mkdir -p "$d"
            cp "$aln" "$d/aln.fasta"; cp "$tax" "$d/tax.tsv"
            ( cd "$d" && \
              SINGULARITYENV_SATIVA_L1O_ENGINE=epang SINGULARITYENV_SATIVA_EPANG_FOLDS=25 \
              SINGULARITYENV_OMP_NUM_THREADS=$THREADS \
              SINGULARITYENV_OPENBLAS_NUM_THREADS=$THREADS SINGULARITYENV_MKL_NUM_THREADS=$THREADS \
              "$TIMEIT" --cwd "$d" --stdout "$d/stdout.log" -- \
                singularity exec -B "$d:$d" --pwd "$d" "$img" \
                  $cmd -s aln.fasta -t tax.tsv -T $THREADS -n run -tmpdir "$d/tmp" \
                       -m ultrafast -C 0.4 -x BAC -p 42 "${extra[@]}" > "$d/timing.json" ) &
            runner=$!
            sample_tree $runner "$d/samples.txt"
            wait $runner; st=$?
            tree=$(awk '$1=="TREE" && $2>m {m=$2} END {printf "%.1f", m/1024}' "$d/samples.txt")
            read -r child comm <<<"$(awk '$1=="PROC" && $2>m {m=$2; c=$3} END {printf "%.1f %s", m/1024, c}' "$d/samples.txt")"
            wall=$(python3 -c "import json;print(json.load(open('$d/timing.json'))['wall_sec'])" 2>/dev/null || echo NA)
            rss=$(python3 -c "import json;print(json.load(open('$d/timing.json'))['max_rss_mb'])" 2>/dev/null || echo NA)
            printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
                "$ds" "$n" "$tool" "$rep" "$wall" "$rss" "$tree" "$child" "$comm" >> "$OUT/gradient.tsv"
            echo "$ds $tool rep$rep: wall ${wall}s  ru_maxrss ${rss}MB  tree ${tree}MB  largest ${child}MB ($comm)  status $st"
            [ "$st" = "0" ] && [ "$wall" != "NA" ] || { failed=$((failed + 1)); tail -3 "$d/stdout.log" >&2 2>/dev/null; }
            # The scratch tree is the bulk of the files; the .mis and the logs are what is kept.
            rm -rf "$d/tmp" "$d/aln.fasta" "$d/samples.txt"
        done
    done
done
echo; column -t -s $'\t' "$OUT/gradient.tsv" || cat "$OUT/gradient.tsv"

# A table of NA is not a measurement. The first run of this script printed thirty of them and said
# ALLDONE, which is the fifth time in this repository that a summary line has reported success after
# the work failed; the rule each time was the same, that the failure path has to be exercised before
# the summary is written.
if [ "$failed" != "0" ]; then
    echo "$failed of the runs failed; the table above is not a measurement" >&2
    exit 1
fi
echo ALLDONE
