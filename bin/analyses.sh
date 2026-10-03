#!/usr/bin/env bash
# Regenerate every analysis result in results/ from the run directories.
#
# The scripts in bin/ were in the repo from the start; the commands that produced each result were
# not, so a reader could see what computed a number but not with which arguments. This closes that:
# one command rebuilds every committed result, and a change to any script shows up as a diff.
#
#   BENCH_ROOT=/path/to/bench bin/analyses.sh
#
# It reads only run directories and writes only into results/. It does not run the pipeline, which is
# what slurm/*.sh is for.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$HOME/bench}"
[ -d "$BENCH_ROOT" ] || { echo "BENCH_ROOT does not name a directory: '$BENCH_ROOT'" >&2; exit 1; }
cd "$BENCH_ROOT"
export PATH="$BENCH_ROOT/bin:$PATH"

TAX=data/gtdb/gtdb_arc2k.tax
ALN=data/gtdb/gtdb_arc2k.fasta
INJ=data/injected
RUNS=results/grid_fork/runs
BASE_FORK=results/baseline2k/runs/gtdb_arc2k__epang_T8_K25__rep1/gtdb_arc2k__epang_T8_K25__rep1.mis

# Conditions whose grid has been run. Each needs its own summary and its own recall-by-ratio table,
# because the whole point of having four of them is comparing them.
FOLD_CONDITIONS="epang_T8_K25 epang_T8_K25_tree epang_T8_K5 epang_T8_K5_tree"

step() { printf '\n== %s\n' "$*"; }

# A gate, not a report: a run that did not finish cleanly must not reach any table below.
step "every run finished cleanly"
verify_runs.py

# And a run must say truthfully whether its seconds are usable. 737 of 949 records once said they
# were when their job had said otherwise, and nothing noticed because the only consumer also
# happened to skip anything not named gtdb*.
step "every run's timing flag agrees with the job that produced it"
verify_timing_flags.py

step "grid summaries and the surviving-label law, per fold condition"
for cond in $FOLD_CONDITIONS; do
    aggregate_grid.py --injected-dir "$INJ" --runs-dir "$RUNS" --condition "${cond}__rep1" \
        --baseline-mis "$BASE_FORK" --out "results/grid_summary_${cond}.json"
    detection_law.py --base-tax "$TAX" --injected-dir "$INJ" --runs-dir "$RUNS" \
        --condition "${cond}__rep1" --out "results/detection_law_${cond}.json" >/dev/null
done

step "the comparator on the same grid, when it has run"
if ls "$RUNS"/*__upstream_raxml_T8__rep1 >/dev/null 2>&1; then
    base_up=results/baseline2k/runs/gtdb_arc2k__upstream_raxml_T8__rep1/gtdb_arc2k__upstream_raxml_T8__rep1.mis
    aggregate_grid.py --injected-dir "$INJ" --runs-dir "$RUNS" --condition upstream_raxml_T8__rep1 \
        --baseline-mis "$base_up" --out results/grid_summary_upstream_raxml_T8.json
else
    echo "   skipped: no upstream cells yet"
fi

step "paired comparisons, which is how two conditions may be compared at all"
paired_conditions.py --injected-dir "$INJ" --runs-dir "$RUNS" \
    --a epang_T8_K25__rep1 --b epang_T8_K5__rep1 \
    --out results/paired_epang_T8_K25_vs_epang_T8_K5.json
paired_conditions.py --injected-dir "$INJ" --runs-dir "$RUNS" \
    --a epang_T8_K25__rep1 --b epang_T8_K25_tree__rep1 \
    --out results/paired_epang_T8_K25_vs_epang_T8_K25_tree.json
paired_conditions.py --injected-dir "$INJ" --runs-dir "$RUNS" \
    --a epang_T8_K5__rep1 --b epang_T8_K5_tree__rep1 \
    --out results/paired_epang_T8_K5_vs_epang_T8_K5_tree.json

# Strict leave-one-out through EPA-ng, which is the one condition that tells the engine apart from
# the fold scheme. Runs on whichever cells have it; it is expensive, so that is one or two.
step "the engine against the fold scheme, on the cells with a Kexact run"
if ls "$RUNS"/*__epang_T8_Kexact__rep1 >/dev/null 2>&1; then
    kexact_decomposition.py --injected-dir "$INJ" --runs-dir "$RUNS" \
        --out results/kexact_decomposition.json
else
    echo "    no Kexact run yet"
fi

# Where the two tools disagree, injected truth says which one is right. On un-injected data this is not
# answerable; here it is arithmetic.
step "when the tools disagree on an injected cell, who is right?"
if ls "$RUNS"/*__upstream_raxml_T8__rep1 >/dev/null 2>&1; then
    disagreement_truth.py --injected-dir "$INJ" --runs-dir "$RUNS" \
        --condition-a upstream_raxml_T8__rep1 --condition-b epang_T8_K25__rep1 \
        --out results/disagreement_truth.json
    paired_conditions.py --injected-dir "$INJ" --runs-dir "$RUNS" \
        --a upstream_raxml_T8__rep1 --b epang_T8_K25__rep1 \
        --out results/paired_upstream_vs_epang_T8_K25.json
else
    echo "   skipped: no upstream cells yet"
fi

step "the two columns, and where the stem calls sit"
column_comparison.py --injected-dir "$INJ" --runs-dir "$RUNS" --condition epang_T8_K25__rep1 \
    --out results/column_comparison.json >/dev/null
threshold_holdout.py --injected-dir "$INJ" --runs-dir "$RUNS" --condition epang_T8_K25__rep1 \
    --baseline-mis "$BASE_FORK" --out results/threshold_holdout.json >/dev/null
stem_flags.py > results/stem_flags.txt

step "the background, and whether the collateral flags are local"
# Both take --condition. Without it their globs match every condition in the runs directory at
# once, which was harmless while only one had been run and mixes four fold conditions and the
# comparator now: the first rebuild after the K=5 grid landed reported 772 cells instead of 180.
background_stability.py --baseline "$BASE_FORK" --runs "$RUNS" --injected-dir "$INJ" \
    --condition epang_T8_K25__rep1 --out results/background_stability.tsv
collateral_locality.py --base-tax "$TAX" --baseline "$BASE_FORK" --injected-dir "$INJ" \
    --runs-dir "$RUNS" --condition epang_T8_K25__rep1 > results/collateral_locality.txt

step "identical sequences under conflicting labels, in the reference itself"
duplicate_conflicts.py --alignment data/gtdb/gtdb_arc1200.aligned.fasta \
    --taxonomy data/gtdb/gtdb_arc1200.tax --unaligned data/gtdb/gtdb_arc1200.fasta \
    --out results/duplicate_conflicts.json
duplicate_conflicts.py --alignment "$ALN" --taxonomy "$TAX" \
    --unaligned data/gtdb/gtdb_arc1200.fasta --baseline-mis "$BASE_FORK" \
    --out results/duplicate_conflicts_2k.json

step "what a cluster-level check would catch that leave-one-out misses"
cluster_conflict.py --alignment "$ALN" --base-tax "$TAX" --injected-dir "$INJ" \
    --out results/cluster_conflict.json >/dev/null

step "error kind 6: is the detection phylogenetic, or is it the alignment score?"
for cond in epang_T8_K25 upstream_raxml_T8; do
    foreign_score_vs_flag.py --donor-scores data/bacteria/donor_pool.cmalign.txt \
        --base-scores data/gtdb/gtdb_arc1200.cmalign.txt --foreign-dir data/foreign \
        --runs-dir results/foreign/runs --condition "${cond}__rep1" \
        --out "results/foreign_score_vs_flag_${cond}.json"
done

step "error kind 6, both tools"
for cond in epang_T8_K25 upstream_raxml_T8; do
    base=results/baseline2k/runs/gtdb_arc2k__${cond}__rep1/gtdb_arc2k__${cond}__rep1.mis
    aggregate_grid.py --injected-dir data/foreign --runs-dir results/foreign/runs \
        --condition "${cond}__rep1" --baseline-mis "$base" \
        --out "results/foreign_summary_${cond}.json"
done

# Whether the 0.510 artefact is upstream's, as the protocol claims, and how concentrated the column is.
step "the shape of the Confidence column, both tools"
for pair in baseline2k:gtdb_arc2k baseline:gtdb_arc1200; do
    d=${pair%%:*}; ds=${pair##*:}
    up=results/$d/runs/${ds}__upstream_raxml_T8__rep1/${ds}__upstream_raxml_T8__rep1.mis
    fk=results/$d/runs/${ds}__epang_T8_K25__rep1/${ds}__epang_T8_K25__rep1.mis
    [ -f "$up" ] && [ -f "$fk" ] && confidence_shape.py --mis "upstream=$up" --mis "fork=$fk" \
        --out "results/confidence_shape_${ds}.json" || echo "   skipped $ds"
done

# The non-regression control, and the only reason an agreement measure is kept at all.
step "agreement between the two tools on the un-injected sets"
for pair in baseline2k:gtdb_arc2k baseline:gtdb_arc1200; do
    d=${pair%%:*}; ds=${pair##*:}
    up=results/$d/runs/${ds}__upstream_raxml_T8__rep1/${ds}__upstream_raxml_T8__rep1.mis
    fk=results/$d/runs/${ds}__epang_T8_K25__rep1/${ds}__epang_T8_K25__rep1.mis
    [ -f "$up" ] && [ -f "$fk" ] && agreement.py --a "$up" --b "$fk" \
        --out "results/agreement_${ds}.json" || echo "   skipped $ds"
done

# The only truth un-injected data offers, used to ask whether each tool's unique calls find anything.
step "are the tools' unique flags enriched in the reference's own label conflicts?"
up7=results/baseline/runs/gtdb_arc1200__upstream_raxml_T8__rep1/gtdb_arc1200__upstream_raxml_T8__rep1.mis
fk7=results/baseline/runs/gtdb_arc1200__epang_T8_K25__rep1/gtdb_arc1200__epang_T8_K25__rep1.mis
if [ -f "$up7" ] && [ -f "$fk7" ]; then
    conflict_enrichment.py --alignment data/gtdb/gtdb_arc1200.aligned.fasta \
        --taxonomy data/gtdb/gtdb_arc1200.tax --mis-a "$up7" --mis-b "$fk7" \
        --out results/conflict_enrichment.json
else
    echo "   skipped: the full-set baseline is not both there"
fi

step "timing: the staged scaling, and how many cores each tool actually uses"
scaling_summary.py > results/scaling_summary.txt
resource_usage.py > results/resource_usage.txt

step "truth checks, which must pass rather than be read"
verify_manifests.py
verify_injection.py --base "$TAX" --injected-dir "$INJ"
verify_foreign.py

# Every cell the grids should hold, enumerated from the same manifests and condition lists the jobs
# were given. A join that dropped a cell would otherwise show up only as a smaller denominator.
step "every grid is complete"
verify_grid_complete.py --datasets-json "$INJ/datasets.json" --runs-dir "$RUNS" \
    --conditions "$(echo $FOLD_CONDITIONS | tr ' ' ','),upstream_raxml_T8"
verify_grid_complete.py --datasets-json data/foreign/datasets.json \
    --runs-dir results/foreign/runs --conditions epang_T8_K25,upstream_raxml_T8
verify_grid_complete.py --datasets-json data/gtdb/datasets_sizes.json \
    --runs-dir results/sizes/runs --conditions epang_T8_K25,upstream_raxml_T8 --replicates 3
verify_grid_complete.py --datasets-json data/gtdb/datasets2k.json --runs-dir results/threads/runs \
    --conditions epang_T1_K25,epang_T8_K25,epang_T16_K25,upstream_raxml_T1,upstream_raxml_T8,upstream_raxml_T16 \
    --replicates 3

echo
echo "done; results/ rebuilt from $BENCH_ROOT"
