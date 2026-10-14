#!/bin/bash
#SBATCH --job-name=mincase
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
# 32G, not 8. 8G was written without consulting a figure this repository already holds: slurm/timing/scaling.sh
# records the fork's measured process-tree peak at 9.3 GB on 2 023 sequences. The full-reference arm
# duly died at 8.36 GB with 1 805 oom_kill events, and the symptom was the one that file also
# documents -- an empty placement file and a JSONDecodeError four stages later. The headroom above 9.3
# is for the arm whose peak nobody has measured, the fork driving RAxML.
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=%x-%j.log
#
# A case small enough to send to someone: one sequence, one wrong label, one engine catching it
# and the other missing it.
#
# The grid already shows 44 such sequences at k=2, but each sits in a 2023-sequence alignment with
# 102 other injected labels, so nobody can read it and the divergence cannot be attributed to the
# one sequence. This cuts the clade out around one of them, puts exactly one wrong label in it, and
# runs both tools. The case is found by shrinking: --per-family caps every family, and the smallest
# cap at which the fork still flags and upstream still misses is the answer.
#
# Three arms, not two. upstream_raxml and fork_epang are the published comparison, but they differ
# in two things at once -- the placement engine and the code that scores the placements -- so a
# divergence between them says nothing about which. fork_raxml is the same codebase with the other
# engine, so the two differences are separated: if fork_raxml agrees with upstream the cause is the
# engine, and if it agrees with fork_epang the cause is the scoring. The arm is skipped, loudly,
# if the fork does not honour SATIVA_L1O_ENGINE=raxml.
#
#   CASE_SPECS="0,10 0,999999" slurm/submit.sh slurm/detection/minimal_case.sh
#   CASE_PAIRS=results/kexact_fork_only.tsv CASE_SPECS=0,10 slurm/submit.sh slurm/detection/minimal_case.sh
#
# CASE_PAIRS sweeps candidates instead of sizes. One sequence reproducing nothing is not evidence
# that none would, and bin/analysis/kexact_decomposition.py --pairs-out writes the whole list of sequences
# the fork catches and upstream misses, so the search runs over all of them.
#
# No timing is taken here, so nothing requires exclusivity or a pinned CPU model. Which also
# means this job has no reason to queue behind timed ones: when the default partition is full
# of jobs holding whole pinned nodes, move it rather than wait --
#   slurm/submit.sh slurm/detection/minimal_case.sh --partition=long
# or, for a job already queued, scontrol update jobid=N Partition=long. Done once: three timed
# tasks held the fast partition's epyc-9754 nodes for an hour and a half and this job sat
# behind them, while long had 1 412 idle cores and no constraint to satisfy.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
require_singularity

ROOT="$BENCH_ROOT"
SEQ="${CASE_SEQUENCE:-GB_GCA_003352285.1_QQVN01000005.1}"
WRONG="${CASE_WRONG:-d__Archaea;p__Thermoproteota;c__Nitrososphaeria;o__Nitrososphaerales;f__UBA57;g__UBA57;s__UBA57 sp002495905}"
RANK="${CASE_KEEP_RANK:-order}"
# The cell the sequence came from. With it the case keeps the other sequences that carry the same
# wrong label, which is what makes the case the same problem as the run: on the full reference with
# one wrong label upstream flags this sequence at 1.000, and in its own cell, where 102 labels are
# wrong, it misses it. So the company is the cause and a case without it reproduces nothing.
TRUTH="${CASE_TRUTH:-}"
# One spec per case, 'per_family,outgroup' or 'per_family,outgroup,wrong labels'. The third field is
# how many of the cell's wrong labels the case carries, which is the axis the mechanism asks about:
# one is found by both tools and the cell's hundred by one of them. Smallest first, so a sweep that
# runs out of wall clock has done the cheap cases rather than half of the expensive one.
SPECS="${CASE_SPECS:-0,10 0,200 0,1000 0,999999}"
DATASET="${CASE_DATASET:-gtdb_arc2k}"
THREADS="${CASE_THREADS:-8}"
# CASE_TAG is required, not defaulted to the dataset. The default put one sweep under
# results/minimal_case/gtdb_arc2k, a name that says nothing about what was varied and that the next
# sweep on the same dataset would have collided with. It also got the same sweep committed twice,
# once under the default tag by repatriation and once under a hand-chosen name, and the repository
# then held two copies of four identical rows. The script already refuses to overwrite a tag that
# holds results, so naming the experiment is the one thing left to insist on.
OUT="$ROOT/results/minimal_case/${CASE_TAG:?CASE_TAG is required: name the sweep, e.g. CASE_TAG=ramp_n40}"

ALN="$ROOT/data/gtdb/${DATASET}.fasta"
TAX="$ROOT/data/gtdb/${DATASET}.tax"
[ -s "$ALN" ] && [ -s "$TAX" ] || { echo "no such dataset: $DATASET" >&2; exit 1; }

FORK=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
# The glob must not match the fork, whose name contains 'sativa' too.
UP=$(ls "$HOME"/.singularity_cache/*sativa*0.9.3*py312h031d066_0* 2>/dev/null | grep -v epang | head -1)
[ -n "$FORK" ] || { echo "sativa-epang 0.10.2 image not in $HOME/.singularity_cache" >&2; exit 1; }
[ -n "$UP" ] || { echo "sativa 0.9.3 image not in $HOME/.singularity_cache" >&2; exit 1; }

ARGS=(-m ultrafast -C 0.4 -x BAC -p 42 -S)

# Did this run flag the target, and with what? One line of TSV per arm, so the table at the end is
# just a cat. The .mis holds flagged rows only, so an absent row is a miss and not a missing file --
# which is why the run's exit status is checked separately before this is read.
verdict() {
    python3 - "$1" "$2" "$3" "$4" <<'PY'
import sys
arm, mis, seq, size = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
row = None
for line in open(mis):
    if line.startswith(";"):
        continue
    f = line.rstrip("\n").split("\t")
    if f and f[0] == seq:
        row = f
print("\t".join([size, arm, "FLAG" if row else "miss",
                 row[1] if row else "-", row[3] if row else "-",
                 row[4] if row else "-", row[8] if row and len(row) > 8 else "-"]))
PY
}

# One arm on 2 023 sequences writes about 20 300 files into its scratch directory, against a ceph
# quota of 100 000 on the home that `getfattr -n ceph.quota.max_files` reports and that two jobs have
# already died on. The tool's own failure mode is an OSError from inside the leave-one-out, forty
# minutes in, naming a fold it could not create. Checking first turns that into one line now.
# 25 000, because one arm writes about 20 300 files. room_for lives in prelude.sh so that the other
# job that needs it does not copy this one.
room_for 25000

mkdir -p "$OUT"
# A tag whose table already has rows is not overwritten. The table is built by appending one row per
# arm, so a second run under the same CASE_TAG would truncate the first run's results -- which is
# exactly what happens when one arm of a sweep has to be redone. A new tag costs nothing.
if [ -s "$OUT/verdicts.tsv" ] && [ "$(grep -c . "$OUT/verdicts.tsv")" -gt 1 ] && [ -z "${CASE_FORCE:-}" ]; then
    echo "$OUT/verdicts.tsv already holds results. Use a different CASE_TAG, or CASE_FORCE=1 to replace them." >&2
    exit 1
fi
printf 'sequence\tcase\tarm\tverdict\tlevel\tproposed\tconfidence\texclusion\n' > "$OUT/verdicts.tsv"

run_case() {
    local seq="$1" wrong="$2" spec="$3"
    local pf="${spec%%,*}" rest="${spec#*,}"
    local outgroup="${rest%%,*}" count=""
    [ "$rest" = "${rest#*,}" ] || count="${rest#*,}"
    local case_dir="$OUT/${seq}__pf${pf}_og${outgroup}${count:+_n$count}"
    rm -rf "$case_dir"
    # A sequence whose wrong label sits outside the kept clade is skipped and not fatal: over 64
    # candidates some are injected across a wider distance than --keep-rank spans, and the sweep is
    # worth more than its most awkward member.
    python3 "$ROOT/bin/analysis/minimal_case.py" --alignment "$ALN" --taxonomy "$TAX" \
        --sequence "$seq" --wrong-label "$wrong" --keep-rank "$RANK" \
        ${TRUTH:+--truth "$TRUTH"} ${count:+--injected-count "$count"} \
        --per-family "$pf" --outgroup "$outgroup" --out "$case_dir" || {
            printf '%s\t%s\t-\tSKIPPED(cannot build)\t-\t-\t-\t-\n' "$seq" "$spec" >> "$OUT/verdicts.tsv"
            return 0
        }

    for arm in upstream_raxml fork_epang fork_raxml; do
        d="$case_dir/$arm"
        mkdir -p "$d"
        cp "$case_dir/case.fasta" "$case_dir/case.tax" "$d/"
        img="$FORK"; cmd=sativa-epang; engine=epang
        case "$arm" in
            upstream_raxml) img="$UP"; cmd=sativa.py ;;
            fork_raxml)     engine=raxml ;;
        esac
        # Strict leave-one-out. The fork caps K at the leaf count, so a K above any case size puts
        # one sequence per fold; upstream has no fold notion and is strict by construction.
        # SINGULARITYENV_ and not a plain assignment: a variable set in front of `singularity exec`
        # reaches singularity, and whether it reaches the program inside depends on the version's
        # environment policy. The prefix is the documented way in and apptainer still honours it.
        ( cd "$d" && \
          SINGULARITYENV_SATIVA_L1O_ENGINE="$engine" \
          SINGULARITYENV_SATIVA_EPANG_FOLDS=999999 \
          SINGULARITYENV_OMP_NUM_THREADS="$THREADS" \
          SINGULARITYENV_OPENBLAS_NUM_THREADS="$THREADS" \
          SINGULARITYENV_MKL_NUM_THREADS="$THREADS" \
          singularity exec -B "$d:$d" --pwd "$d" "$img" \
            $cmd -s case.fasta -t case.tax -T "$THREADS" -n case -tmpdir "$d/tmp" \
                 "${ARGS[@]}" > stdout.log 2>&1 ) && st=0 || st=$?

        if [ "$st" != "0" ] || [ ! -f "$d/case.mis" ]; then
            # fork_raxml is allowed to be unavailable; the other two are not. Either way the
            # reason goes in the table rather than into a log nobody reads.
            printf '%s\t%s\t%s\tERROR(status %s)\t-\t-\t-\t-\n' "$seq" "$spec" "$arm" "$st" >> "$OUT/verdicts.tsv"
            tail -5 "$d/stdout.log" >&2 || true
            # Keep the scratch directory, which is where a failure is diagnosed, but not the fold
            # task tree: one failed arm on 2 023 sequences leaves 20 300 files there, and four of
            # them filled the 100 000-file quota and made each other fail. The first failure was
            # genuine and the other three were its debris. What a diagnosis needs is the tool's own
            # top-level files -- RAxML_info, the model, epang.log -- which stay.
            find "$d/tmp" -type d -name 'fold_*' -exec rm -rf {} + 2>/dev/null || true
            [ "$arm" = "fork_raxml" ] || exit 1
            continue
        fi
        printf '%s\t' "$seq" >> "$OUT/verdicts.tsv"
        verdict "$arm" "$d/case.mis" "$seq" "$spec" >> "$OUT/verdicts.tsv"
        # The tool's scratch directory, dropped once the arm has succeeded. A sweep over 64
        # candidates times three arms leaves thousands of RAxML intermediates behind otherwise,
        # against a 100 000-file quota that has already killed one job before it ran. It is kept
        # when an arm fails, which is when anyone would want to look at it.
        rm -rf "$d/tmp"
    done
}

if [ -n "${CASE_PAIRS:-}" ]; then
    [ -s "$CASE_PAIRS" ] || { echo "CASE_PAIRS names no readable file: $CASE_PAIRS" >&2; exit 1; }
    while IFS=$'\t' read -r seq wrong; do
        [ -n "${seq:-}" ] && [ -n "${wrong:-}" ] || continue
        for spec in $SPECS; do run_case "$seq" "$wrong" "$spec"; done
    done < "$CASE_PAIRS"
else
    for spec in $SPECS; do run_case "$SEQ" "$WRONG" "$spec"; done
fi

echo "=== $OUT/verdicts.tsv"
column -t -s $'\t' "$OUT/verdicts.tsv" || cat "$OUT/verdicts.tsv"

# What the job was for: a size where the fork flags and upstream misses. Saying so here means the
# log answers the question without anyone having to read the table, and a job that reproduces
# nothing says that too instead of looking like a success.
python3 - "$OUT/verdicts.tsv" <<'PY'
import collections, sys
rows = [l.rstrip("\n").split("\t") for l in open(sys.argv[1])][1:]
by = collections.defaultdict(dict)
for seq, spec, arm, verdict, *_ in rows:
    by[(seq, spec)][arm] = verdict
good = [k for k, a in by.items()
        if a.get("fork_epang") == "FLAG" and a.get("upstream_raxml") == "miss"]
print(f"divergence reproduced for case(s) {good}" if good
      else "no size reproduced the divergence")
PY
