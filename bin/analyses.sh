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
#
# Every committed file under results/ is rebuilt by this script. That was not true twice over until
# recently: the k-axis and fold-sweep summaries were never rebuilt, and three files from version 1 on
# the ITS sets sat outside its scope with no run tree to rebuild them from. Version 1 has been removed,
# so the exception is gone with it and the claim in the line above is now exact.
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

# Stamped before the first step so the last one can check that every table under results/ is newer
# than it. Not in results/, which is what is being checked, and not committed.
REBUILD_MARKER="${TMPDIR:-/tmp}/analyses_started.$$"
: > "$REBUILD_MARKER"
trap 'rm -f "$REBUILD_MARKER"' EXIT

# A gate, not a report: a run that did not finish cleanly must not reach any table below.
step "every run finished cleanly"
verify_runs.py

# And a run must say truthfully whether its seconds are usable. 737 of 949 records once said they
# were when their job had said otherwise, and nothing noticed because the only consumer also
# happened to skip anything not named gtdb*.
step "every run's timing flag agrees with the job that produced it"
verify_timing_flags.py

# And every condition of a cell read the same database, which the comparison between the two tools
# rests on and which nothing recorded until the tool modules started writing the sha256 of what
# they read. Records written before that field existed are named rather than passed over.
step "every condition of a cell read the same database"
verify_inputs.py

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
    # The comparator's own detection law. It was built by hand once and left out of this script, so
    # it kept saying what a 105-cell grid said after the grid had reached 180.
    detection_law.py --base-tax "$TAX" --injected-dir "$INJ" --runs-dir "$RUNS" \
        --condition upstream_raxml_T8__rep1 \
        --out results/detection_law_upstream_raxml_T8.json >/dev/null
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
# Reads the case directories, not the verdicts tables those runs wrote, so the campaign's claims rest
# on a second reading of the same evidence.
step "the minimal-case campaign, recounted from the arms' own output"
if ls results/minimal_case/*/*/case.json >/dev/null 2>&1; then
    minimal_case_summary.py --out results/minimal_case_summary.tsv
else
    echo "    no minimal-case sweep yet"
fi

step "the engine against the fold scheme, on the cells with a Kexact run"
if ls "$RUNS"/*__epang_T8_Kexact__rep1 >/dev/null 2>&1; then
    kexact_decomposition.py --injected-dir "$INJ" --runs-dir "$RUNS" \
        --out results/kexact_decomposition.json \
        --pairs-out results/kexact_fork_only.tsv
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

# The two side grids, which are not separate results. kaxis ran species distance at every k and rate
# 0.05, ksweep ran species and genus at k=10, and the 180-cell grid now covers every one of those
# cells with the same seeds and the same injected inputs. Rebuilding their four summary records was
# worse than not rebuilding them: it produced four committed files carrying the grid's own numbers,
# which a reader could take for independent measurements of the same quantity. They were removed.
#
# What their 42 run directories are good for is the opposite claim. Each was produced by a different
# Slurm job at a different time from the grid's counterpart, so comparing the two is the largest
# reproducibility check here by a wide margin -- 42 cells against the determinism script's one cell
# produced three times.
step "the 42 cells that were run twice must have produced the same answer twice"
verify_duplicate_runs.py

# Error kind 3, which Protocol.md 2.2 asks to characterise rather than score: whole taxa relabelled,
# so nothing correct is left to confirm them, and detection reported against how well the clade can
# be told apart from the taxon it was given. Guarded, because the runs arrive from the cluster.
# Guarded per condition and not per experiment. The first version checked that the fork arm
# existed and then looped over both, so the whole analysis failed the moment one arm had been
# repatriated and the other was still running on the cluster -- which is the normal state while a
# comparator catches up, upstream taking sixteen times as long per cell.
step "error kind 3: does detection track how compact the relabelled clade is?"
for cond in epang_T8_K25 upstream_raxml_T8; do
    if ls results/clade/runs/*__${cond}__rep1 >/dev/null 2>&1; then
        clade_detection.py --clade-dir data/clade --runs-dir results/clade/runs \
            --condition "${cond}__rep1" --out "results/clade_detection_${cond}.json"
    else
        echo "  ${cond}: no runs yet, skipped"
    fi
done

# Protocol.md 2.1's control. The un-injected cell is the one number the injected grid cannot give:
# on simulated data a flag on an untouched sequence is a false positive outright, because the
# taxonomy is the tree.
step "simulation: recall where every label is certain, and a strict false-positive rate"
for cond in epang_T8_K25 upstream_raxml_T8; do
    base=results/simulated/runs/sim__${cond}__rep1/sim__${cond}__rep1.mis
    if [ -s "$base" ]; then
        # `grep -vc` exits 1 when it counts nothing, which is the expected answer here and not a
        # failure: zero flags on the un-injected reference is the result this control exists for.
        n=$(grep -vc '^;' "$base" || true)
        total=$(grep -c '^>' data/simulated/sim/sim.fasta)
        echo "  ${cond}: ${n} flags on ${total} certainly-correct sequences"
        aggregate_grid.py --injected-dir data/simulated --runs-dir results/simulated/runs \
            --condition "${cond}__rep1" --baseline-mis "$base" \
            --out "results/simulated_summary_${cond}.json"
    else
        echo "  ${cond}: no un-injected run yet, skipped"
    fi
done

# Three committed records of this experiment were produced by hand and rebuilt by nothing, which is the
# defect finding 73 found in the k-axis summaries and declared fixed. It was not: the law and the paired
# test for the simulated set were outside every loop here, because those loops read the archaeal grid.
# It mattered the moment upstream's arm finished -- it went from 12 cells on one seed to 36 on three, and
# both records still described the twelve.
step "the simulation's detection law and the paired comparison, on whichever arms have run"
for cond in epang_T8_K25 upstream_raxml_T8; do
    if [ -s "results/simulated/runs/sim__${cond}__rep1/sim__${cond}__rep1.mis" ]; then
        detection_law.py --base-tax data/simulated/sim/sim.tax --injected-dir data/simulated \
            --runs-dir results/simulated/runs --condition "${cond}__rep1" \
            --out "results/detection_law_simulated_${cond}.json" >/dev/null
    fi
done
if [ -s results/simulated/runs/sim__upstream_raxml_T8__rep1/sim__upstream_raxml_T8__rep1.mis ]; then
    paired_conditions.py --injected-dir data/simulated --runs-dir results/simulated/runs \
        --a upstream_raxml_T8__rep1 --b epang_T8_K25__rep1 \
        --out results/paired_simulated_upstream_vs_epang_T8_K25.json >/dev/null
fi

# Does fold co-removal explain the fork's advantage on the k axis? The question is the fork's own
# mechanism, so it belongs beside the decomposition rather than in a script nothing ran: this one had
# no caller, wrote no record, and its docstring still quoted the partial grid's numbers.
step "the k-axis gap against the co-removal model it was supposed to have"
fold_mechanism.py --upstream results/grid_summary_upstream_raxml_T8.json \
    --fork results/grid_summary_epang_T8_K25.json \
    --fork-k5 results/grid_summary_epang_T8_K5.json \
    --out results/fold_mechanism.json

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
# The staged table DISTRIBUTION.md quotes was printed by a job script and committed nowhere: the
# per-shard timings are in results/, so the numbers were recoverable, but the table that carries the
# distribution claim had no record and nothing rebuilt it. One file per fold count, since the three
# rounds differ in the only variable they vary.
# One file per round, and per replicate where there is one: the rounds are no longer exclusive, so
# the spread over replicates is what bounds the interference and it cannot be read off a single run.
for d in results/staged_timed_f*; do
    [ -d "$d/staged" ] || continue
    # The trace dir is the round's own where it has one and results/pipeline_info otherwise, since
    # bin/repatriate.sh flattens the traces of every round into that one directory. --round names
    # the round so the span and the node record come from its trace and not from a sibling's.
    info="$d/pipeline_info"
    [ -d "$info" ] || info=results/pipeline_info
    staged_scaling.py --staged-dir "$d/staged" --trace-dir "$info" \
        --round "$(basename "$d")" \
        > "results/staged_scaling_${d#results/staged_timed_}.txt"
done

# What an incomplete lineage costs detection. The ragged cells are the grid's own at family distance
# and the top rate, with a quarter of the untouched lineages cut to genus and a quarter to family, so
# the injected truth is unchanged and recall is comparable cell for cell. Skipped rather than failed
# when the runs are not here, since the cells are a late addition and a clone may predate them.
if [ -d results/ragged/runs ]; then
    step "what an incomplete lineage costs detection, for both tools"
    ragged_cost.py --out results/ragged_cost.json > results/ragged_cost.txt
    cat results/ragged_cost.txt
fi

# What each reference can be judged on at all, which is a ceiling on any recall figure and a
# property of the database rather than of either tool. One rule for every dataset, so that the
# protocol's table is computed one way: the UNITE rows were published at 85.7 % and 8.5 % when
# they were not.
step "judgeability of every reference, by one rule"
dataset_shape.py --convention gtdb --fasta "$ALN" --tax "$TAX" \
    --out results/shape_gtdb_arc2k.json
dataset_shape.py --convention gtdb --fasta data/gtdb/gtdb_arc1200.aligned.fasta \
    --tax data/gtdb/gtdb_arc1200.tax --out results/shape_gtdb_arc1200.json
if [ -s data/unite/unite_reps.tax ]; then
    dataset_shape.py --convention unite --fasta data/unite/unite_reps.fasta \
        --tax data/unite/unite_reps.tax --out results/shape_unite_reps.json
else
    echo "    UNITE not fetched here; slurm/fetch_unite.sh gets it"
fi

# The paper's central number, recomputed from the two primary files by a second implementation that
# shares nothing with score_injection.py or aggregate_grid.py. Both of those are tested, but against
# fixtures written by the same hand, so a misreading of the .mis would sit in the code, the fixture and
# the paper at once. Finding 98 is the precedent: rereading a correct script could not find an error
# that recomputing from the format found at once.
step "every published recall and collateral count, recomputed by a second route"
verify_recall_independently.py --injected-dir "$INJ" --runs-dir "$RUNS" \
    --summary epang_T8_K25__rep1=results/grid_summary_epang_T8_K25.json \
    --summary epang_T8_K25_tree__rep1=results/grid_summary_epang_T8_K25_tree.json \
    --summary epang_T8_K5__rep1=results/grid_summary_epang_T8_K5.json \
    --summary epang_T8_K5_tree__rep1=results/grid_summary_epang_T8_K5_tree.json \
    --summary upstream_raxml_T8__rep1=results/grid_summary_upstream_raxml_T8.json
# The same check over the other two injection experiments, which have the same record shape. Error
# kind 6's cells carry no k, which crashed this gate until it matched cells on the fields they have.
verify_recall_independently.py --injected-dir data/simulated --runs-dir results/simulated/runs \
    --summary epang_T8_K25__rep1=results/simulated_summary_epang_T8_K25.json \
    --summary upstream_raxml_T8__rep1=results/simulated_summary_upstream_raxml_T8.json
verify_recall_independently.py --injected-dir data/foreign --runs-dir results/foreign/runs \
    --summary epang_T8_K25__rep1=results/foreign_summary_epang_T8_K25.json \
    --summary upstream_raxml_T8__rep1=results/foreign_summary_upstream_raxml_T8.json

# Seconds from two machines cannot be compared, which is the rule this repository states for itself and
# enforces at submission with --constraint. Nothing checked it afterwards against what the runs recorded.
step "every published timing is a median over one CPU model"
verify_timed_one_model.py

step "truth checks, which must pass rather than be read"
verify_manifests.py
# What is not committed must come back from the kept inputs alone, which was the one claim in
# data/README.md run by hand rather than by this script -- and run from a fresh clone, where two of
# the four experiments cannot be regenerated at all because their cells are committed.
verify_regeneration.py
# The condition names are the benchmark's independent variable for four of its conditions, and
# run.json records what was declared rather than what ran. This compares both against the tool's own
# line, which is the only evidence of the fold count the harness did not write itself.
verify_fold_counts.py
# And the other half of what that one states: the count is checked against the tool's own line, the
# order against nothing. This checks the output instead, in both directions.
verify_conditions_differ.py
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

# Last, because it reads the records the steps above write rather than the run directories: the
# figure can only be as current as the tables, and building it from them is what keeps the two from
# drifting. Every number it draws is also written to results/figure1_values.tsv, so a change
# upstream shows up as a diff in a table and not only as a change of ink.
step "the Application Note's figure"
make_figure.py --root "$BENCH_ROOT" --out results/figure1.svg --values results/figure1_values.tsv
# And the figure the manuscript actually carries, with its values table and its draft caption.
paper_figure.py "$BENCH_ROOT"
# Measured rather than looked at. Four passes of looking left "Reference tree" running out of both
# sides of its box and two labels 0.7 points apart in the runtime panel.
verify_figure_layout.py results/candidates/figure3.svg results/candidates/figure1_[1-6].svg

# Run here rather than by hand, which is how it was run until now. A gate whose running depends on
# someone remembering it is one nobody notices has stopped.
# The traces are provenance rather than measurement, so nothing reads them -- which is exactly why the
# document enumerating them drifted to 13 files of 41 without anyone noticing.
step "every Nextflow trace is named in the document that enumerates them"
verify_trace_table.py

step "every file of the repository is named somewhere in REVIEW.md"
review_coverage.py
# And that the report's own cross-references resolve. Only REVIEW.md here: the decision log lives
# outside this repository, so a clone must pass without it. Run it on both by hand with --decisions.
verify_report_references.py

# The claim this script opens with, checked rather than restated. It has been false three times.
step "every table under results/ was rebuilt by this run"
verify_rebuild_coverage.py --marker "$REBUILD_MARKER"

echo
echo "done; results/ rebuilt from $BENCH_ROOT"
