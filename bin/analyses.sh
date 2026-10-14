#!/usr/bin/env bash
# Regenerate every analysis result in results/ from the run directories.
#
# The scripts in bin/ were in the repo from the start; the commands that produced each result were
# not, so a reader could see what computed a number but not with which arguments. This closes that:
# one command rebuilds every committed result, and a change to any script shows up as a diff.
#
#   bin/analyses.sh                      from a clone, or
#   BENCH_ROOT=/path/to/bench bin/analyses.sh
#
# It reads only run directories and writes only into results/. It does not run the pipeline, which is
# what slurm/*/*.sh is for.
#
# Every committed file under results/ is rebuilt by this script. That was not true twice over until
# recently: the k-axis and fold-sweep summaries were never rebuilt, and three files from version 1 on
# the ITS sets sat outside its scope with no run tree to rebuild them from. Version 1 has been removed,
# so the exception is gone with it and the claim in the line above is now exact.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
[ -d "$BENCH_ROOT" ] || { echo "BENCH_ROOT does not name a directory: '$BENCH_ROOT'" >&2; exit 1; }
cd "$BENCH_ROOT"
export PATH="$BENCH_ROOT/bin:$(printf '%s:' "$BENCH_ROOT"/bin/*/)$PATH"

TAX=data/gtdb/gtdb_arc2k.tax
ALN=data/gtdb/gtdb_arc2k.fasta
INJ=data/injected
RUNS=results/grid_fork/runs
BASE_FORK=results/baseline2k/runs/gtdb_arc2k__epang_T8_K25__rep1/gtdb_arc2k__epang_T8_K25__rep1.mis

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

step "grid summaries and the surviving-label law, for K = 25 and K = 5"
for cond in epang_T8_K25 epang_T8_K5; do
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
        --pairs-out results/kexact_one_sided.tsv
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
else
    echo "   skipped: no upstream cells yet"
fi

step "the two columns, and where the stem calls sit"
column_comparison.py --injected-dir "$INJ" --runs-dir "$RUNS" --condition epang_T8_K25__rep1 \
    --out results/column_comparison.json >/dev/null
threshold_holdout.py --injected-dir "$INJ" --runs-dir "$RUNS" --condition epang_T8_K25__rep1 \
    --baseline-mis "$BASE_FORK" --out results/threshold_holdout.json >/dev/null
stem_flags.py > results/stem_flags.txt

step "whether the collateral flags are local"
# --condition is required: without it the glob matches every condition in the runs directory at once.
collateral_locality.py --base-tax "$TAX" --baseline "$BASE_FORK" --injected-dir "$INJ" \
    --runs-dir "$RUNS" --condition epang_T8_K25__rep1 > results/collateral_locality.txt

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

# Error kind 3, which is characterised rather than scored: whole taxa relabelled,
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

# The simulated control, on a RAxMLGrove tree. The un-injected cell is the one number the injected
# grid cannot give: on simulated data a flag on an untouched sequence is a false positive outright,
# because the taxonomy is the tree.
control_analyses() {
    local data="$1" res="$2" base="$3" label="$4" cond n total b
    step "${label}: recall where every label is certain, and a strict false-positive rate"
    for cond in epang_T8_K25 upstream_raxml_T8; do
        b="$res/runs/${base}__${cond}__rep1/${base}__${cond}__rep1.mis"
        if [ -s "$b" ]; then
            # `grep -vc` exits 1 when it counts nothing, which is the expected answer here and not a
            # failure: zero flags on the un-injected reference is the result this control exists for.
            n=$(grep -vc '^;' "$b" || true)
            total=$(grep -c '^>' "$data/$base/$base.fasta")
            echo "  ${cond}: ${n} flags on ${total} certainly-correct sequences"
            aggregate_grid.py --injected-dir "$data" --runs-dir "$res/runs" \
                --condition "${cond}__rep1" --baseline-mis "$b" \
                --thresholds 0.0,0.5,0.511,0.7,0.9,0.95,0.99 \
                --out "results/${label}_summary_${cond}.json"
        else
            echo "  ${cond}: no un-injected run yet, skipped"
        fi
    done

    step "${label}: the detection law and the paired comparison, on whichever arms have run"
    for cond in epang_T8_K25 upstream_raxml_T8; do
        if [ -s "$res/runs/${base}__${cond}__rep1/${base}__${cond}__rep1.mis" ]; then
            detection_law.py --base-tax "$data/$base/$base.tax" --injected-dir "$data" \
                --runs-dir "$res/runs" --condition "${cond}__rep1" \
                --out "results/detection_law_${label}_${cond}.json" >/dev/null
        fi
    done
    if [ -s "$res/runs/${base}__upstream_raxml_T8__rep1/${base}__upstream_raxml_T8__rep1.mis" ]; then
        paired_conditions.py --injected-dir "$data" --runs-dir "$res/runs" \
            --a upstream_raxml_T8__rep1 --b epang_T8_K25__rep1 \
            --out "results/paired_${label}_upstream_vs_epang_T8_K25.json" >/dev/null
    fi
}

# Absent until slurm/detection/grove_simulation.sh has run, which the guards above report rather than fail on.
control_analyses data/grove_sim results/grove_simulated grove grove_simulated
# And the promise the control rests on, re-checked on the committed files rather than trusted from
# the day they were generated: every label is a clade of the tree the sequences evolved along.
if [ -s data/grove_sim/grove/grove.tax ]; then
    verify_grove_taxonomy.py --tree data/grove_sim/raw/*/tree_best.newick \
        --tax data/grove_sim/grove/grove.tax
fi

# Does fold co-removal explain the fork's advantage on the k axis? The question is the fork's own
# mechanism, so it belongs beside the decomposition rather than in a script nothing ran: this one had
# no caller, wrote no record, and its docstring still quoted the partial grid's numbers.
step "the k-axis gap against the co-removal model it was supposed to have"
fold_mechanism.py --upstream results/grid_summary_upstream_raxml_T8.json \
    --fork results/grid_summary_epang_T8_K25.json \
    --fork-k5 results/grid_summary_epang_T8_K5.json \
    --out results/fold_mechanism.json

# The non-regression control, and the only reason an agreement measure is kept at all.
step "agreement between the two tools on the un-injected sets"
for pair in baseline2k:gtdb_arc2k baseline:gtdb_arc1200; do
    d=${pair%%:*}; ds=${pair##*:}
    up=results/$d/runs/${ds}__upstream_raxml_T8__rep1/${ds}__upstream_raxml_T8__rep1.mis
    fk=results/$d/runs/${ds}__epang_T8_K25__rep1/${ds}__epang_T8_K25__rep1.mis
    [ -f "$up" ] && [ -f "$fk" ] && agreement.py --a "$up" --b "$fk" \
        --out "results/agreement_${ds}.json" || echo "   skipped $ds"
done

step "timing: the staged scaling, and how many cores each tool actually uses"
resource_usage.py > results/resource_usage.txt
# One file per fold count and replicate: the spread over replicates is what bounds the interference
# between shards, and it cannot be read off a single run. The main figure reads these.
for d in results/staged_timed_f*_r*; do
    [ -d "$d/staged" ] || continue
    # The trace dir is the round's own where it has one and results/pipeline_info otherwise, since
    # bin/ops/repatriate.sh flattens the traces of every round into that one directory. --round names
    # the round so the span and the node record come from its trace and not from a sibling's.
    info="$d/pipeline_info"
    [ -d "$info" ] || info=results/pipeline_info
    staged_scaling.py --staged-dir "$d/staged" --trace-dir "$info" \
        --round "$(basename "$d")" \
        > "results/staged_scaling_${d#results/staged_timed_}.txt"
done

# The same nine rounds as one table. The per-round files above leave the medians to the reader, and
# this repository's own rule is medians over replicates and never a single run, so the scaling claim
# gets a producer of its own rather than being assembled by eye from nine files.
staged_rounds.py --out results/staged_rounds.txt > /dev/null
# The same four-shard round with every shard pinned to a different machine (slurm/timing/staged_nodes.sh),
# once it has run: the other half of "across jobs" against "across machines".
if ls -d results/staged_nodes_n4_r* >/dev/null 2>&1; then
    staged_rounds.py --prefix staged_nodes --tags n4 --base staged_timed_f25 --replicates r1,r2,r3,r4 --out results/staged_nodes.txt > /dev/null
fi

# Error kind 7, chimeras: detection along the two axes the protocol names, and whether the proposal
# sides with the unlabelled parent. Skipped when the runs are not here, as for the ragged cells.
if [ -d results/chimera/runs ]; then
    step "error kind 7: chimeras, by parent distance and breakpoint, both tools"
    for cond in epang_T8_K25 upstream_raxml_T8; do
        chimera_detection.py --chimera-dir data/chimera --runs-dir results/chimera/runs \
            --condition "${cond}__rep1" --out "results/chimera_detection_${cond}.json"
    done
fi

# The bacterial replication: the same questions on an order chosen by the evaluability criteria
# (data/gtdb/bacterial_clade_selection.json), both tools. Agreement on the un-injected clade, the
# grid summaries and the surviving-label law on the fifteen family-distance cells. The subset baseline (results/baseline_bac2k) gives the added-vs-baseline column when it has
# run; without it the summaries carry none, as the archaeal grid's did before baseline2k.
if [ -d results/grid_bac/runs ]; then
    step "bacterial clade: agreement, grid summaries, detection law"
    bup=results/baseline_bac/runs/gtdb_bac_lachnospirales__upstream_raxml_T8__rep1/gtdb_bac_lachnospirales__upstream_raxml_T8__rep1.mis
    bfk=results/baseline_bac/runs/gtdb_bac_lachnospirales__epang_T8_K25__rep1/gtdb_bac_lachnospirales__epang_T8_K25__rep1.mis
    [ -f "$bup" ] && [ -f "$bfk" ] && agreement.py --a "$bup" --b "$bfk" \
        --out results/agreement_gtdb_bac_lachnospirales.json || echo "   skipped the clade agreement"
    sup=results/baseline_bac2k/runs/gtdb_bac2k__upstream_raxml_T8__rep1/gtdb_bac2k__upstream_raxml_T8__rep1.mis
    sfk=results/baseline_bac2k/runs/gtdb_bac2k__epang_T8_K25__rep1/gtdb_bac2k__epang_T8_K25__rep1.mis
    [ -f "$sup" ] && [ -f "$sfk" ] && agreement.py --a "$sup" --b "$sfk" \
        --out results/agreement_gtdb_bac2k.json || echo "   skipped the subset agreement"
    for cond in epang_T8_K25 upstream_raxml_T8; do
        base=results/baseline_bac2k/runs/gtdb_bac2k__${cond}__rep1/gtdb_bac2k__${cond}__rep1.mis
        aggregate_grid.py --injected-dir data/injected_bac --runs-dir results/grid_bac/runs \
            --condition "${cond}__rep1" $([ -f "$base" ] && echo --baseline-mis "$base") \
            --out "results/grid_summary_bac_${cond}.json"
        detection_law.py --base-tax data/gtdb/gtdb_bac2k.tax --injected-dir data/injected_bac \
            --runs-dir results/grid_bac/runs --condition "${cond}__rep1" \
            --out "results/detection_law_bac_${cond}.json" >/dev/null
    done
    paired_conditions.py --injected-dir data/injected_bac --runs-dir results/grid_bac/runs \
        --a upstream_raxml_T8__rep1 --b epang_T8_K25__rep1 \
        --out results/paired_bac_upstream_vs_epang_T8_K25.json
fi

# The memory law's width term, measured: the fork on the same 2 023 sequences at five alignment
# widths (slurm/timing/width.sh), peak RSS against sequences x columns.
if ls results/width/runs/*/run.json >/dev/null 2>&1; then
    step "peak memory against alignment width, the law's coefficient per sequence and per column"
    memory_width.py --out results/memory_width.json > /dev/null
fi

# Alignment difficulty per set (slurm/checks/aldiscore.sh), the foreign cells as a delta from the subset.
if [ -s results/aldiscore/scores.jsonl ]; then
    step "alignment difficulty of every set, the foreign cells against their base"
    aldiscore_summary.py --out results/aldiscore_summary.json > /dev/null
fi

# Where the injected sequences' placements landed, read off the jplace files slurm/checks/placements.sh
# keeps. The files stay out of git (about 540 MB for the Kexact cell), so this runs only where they
# are, and the committed record under results/placement_locality/ is what the paper cites. Upstream's
# leave-one-out jplace carries no tree; its .refjson does, and is passed as --tree.
if ls results/placements_*/placements/*/*/*.jplace >/dev/null 2>&1; then
    step "placement locality: the edge each injected sequence landed on, per kept cell"
    mkdir -p results/placement_locality
    for run in results/placements_*/placements/*; do
        name=$(basename "$run"); cell=${name%%__*}; tool=${name#*__}; tool=${tool%__*}
        d=$(dirname "$(dirname "$run")")
        if [ -d "$run/upstream" ]; then
            refjson=$(ls "$run"/upstream/*.refjson 2>/dev/null | head -1)
            [ -n "$refjson" ] || { echo "  $name: no refjson kept, skipped"; continue; }
            placement_locality.py --truth "data/injected/$cell/$cell.truth.json" \
                --tax "data/injected/$cell/$cell.tax" --mis "$d/runs/$name/$name.mis" \
                --jplace "$run"/upstream/*.l1out_seq.jplace --tree "$refjson" \
                --out "results/placement_locality/$name.json" > /dev/null
        else
            placement_locality.py --truth "data/injected/$cell/$cell.truth.json" \
                --tax "data/injected/$cell/$cell.tax" --mis "$d/runs/$name/$name.mis" \
                --jplace "$run"/shard*/fold_*/epa_result.jplace \
                --out "results/placement_locality/$name.json" > /dev/null
        fi
    done
fi
# From the committed records, so it also runs where the jplace files are absent.
pair=results/placement_locality/inj_family_r0.05_k2_s1
if [ -f "${pair}__upstream_raxml_T8__rep1.json" ] && [ -f "${pair}__epang_T8_Kexact__rep1.json" ]; then
    step "the engine tie: upstream and the fork on the same cell"
    placement_comparison.py --upstream "${pair}__upstream_raxml_T8__rep1.json" \
        --fork "${pair}__epang_T8_Kexact__rep1.json" --out results/placement_comparison.tsv > /dev/null
fi

# What an incomplete lineage costs detection. The ragged cells are the grid's own at family distance
# and the top rate, with a quarter of the untouched lineages cut to genus and a quarter to family, so
# the injected truth is unchanged and recall is comparable cell for cell. Skipped rather than failed
# when the runs are not here, since the cells are a late addition and a clone may predate them.
if [ -d results/ragged/runs ]; then
    step "what an incomplete lineage costs detection, for both tools"
    ragged_cost.py --out results/ragged_cost.json
fi

# What the archaeal reference can be judged on at all, which verify_manifests checks against
# assets/datasets.yml and data/gtdb/dataset_table.json.
step "judgeability of the archaeal reference"
dataset_shape.py --convention gtdb --fasta data/gtdb/gtdb_arc1200.aligned.fasta \
    --tax data/gtdb/gtdb_arc1200.tax --out results/shape_gtdb_arc1200.json

# The paper's central number, recomputed from the two primary files by a second implementation that
# shares nothing with score_injection.py or aggregate_grid.py. Both of those are tested, but against
# fixtures written by the same hand, so a misreading of the .mis would sit in the code, the fixture and
# the paper at once.
step "every published recall and collateral count, recomputed by a second route"
verify_recall_independently.py --injected-dir "$INJ" --runs-dir "$RUNS" \
    --summary epang_T8_K25__rep1=results/grid_summary_epang_T8_K25.json \
    --summary epang_T8_K5__rep1=results/grid_summary_epang_T8_K5.json \
    --summary upstream_raxml_T8__rep1=results/grid_summary_upstream_raxml_T8.json
# The same check over the other injection experiments, which have the same record shape. Error
# kind 6's cells carry no k, which crashed this gate until it matched cells on the fields they have.
# The Grove control is guarded, unlike the others, because its runs may not exist yet and an absent
# summary is not a disagreement.
if [ -s results/grove_simulated_summary_epang_T8_K25.json ]; then
    verify_recall_independently.py --injected-dir data/grove_sim --runs-dir results/grove_simulated/runs \
        --summary epang_T8_K25__rep1=results/grove_simulated_summary_epang_T8_K25.json \
        --summary upstream_raxml_T8__rep1=results/grove_simulated_summary_upstream_raxml_T8.json
fi
verify_recall_independently.py --injected-dir data/foreign --runs-dir results/foreign/runs \
    --summary epang_T8_K25__rep1=results/foreign_summary_epang_T8_K25.json \
    --summary upstream_raxml_T8__rep1=results/foreign_summary_upstream_raxml_T8.json

# Seconds from two machines cannot be compared, which is the rule this repository states for itself and
# enforces at submission with --constraint. Nothing checked it afterwards against what the runs recorded.
step "every published timing is a median over one CPU model"
verify_timed_one_model.py

step "truth checks, which must pass rather than be read"
verify_manifests.py
verify_doc_paths.py
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
# Two calls over one directory, because the thread axis and the sequential comparison share it and do
# not cover the same sizes: T8 and T16 are measured at 2 023 sequences only, while the T1 pair was
# extended to 402 and 801 for the engine-only ratio. The enumeration is per condition, so the two sets
# do not see each other's cells.
verify_grid_complete.py --datasets-json data/gtdb/datasets2k.json --runs-dir results/threads/runs \
    --conditions epang_T8_K25,epang_T16_K25,upstream_raxml_T8,upstream_raxml_T16 \
    --replicates 3
verify_grid_complete.py --datasets-json data/gtdb/datasets_sizes.json --runs-dir results/threads/runs \
    --datasets gtdb_arc400,gtdb_arc800,gtdb_arc2k \
    --conditions epang_T1_K25,upstream_raxml_T1 --replicates 3

# Last, because it reads the records the steps above write rather than the run directories: the
# figure can only be as current as the tables, and building it from them is what keeps the two from
# drifting. Every number drawn is also written to results/figure3_values.tsv, so a change upstream
# shows up as a diff in a table and not only as a change of ink.
step "the Application Note's figure and the supplement's figures"
main_figure.py "$BENCH_ROOT"
# The UpSet panel as tables, then the paired tests; the supplement's figures read both.
upset_tables.py "$BENCH_ROOT" > results/upset_tables.txt
paired_stats.py "$BENCH_ROOT"
supplement_figures.py "$BENCH_ROOT"
# Measured rather than looked at: a label running out of its box, or two labels a point apart.
# Advisory: the figure is checked by eye, and this reports label overlaps of a few points that do not
# change what a reader sees.
verify_figure_layout.py results/figure3.svg || echo "  (layout notes above; not a failure)"

# The traces are provenance, not measurement, so nothing reads them. Without this gate the document
# enumerating them drifts unnoticed.
step "every Nextflow trace is named in the document that enumerates them"
verify_trace_table.py

step "every path and link in the documentation resolves"
verify_doc_paths.py "$BENCH_ROOT"

step "every table under results/ was rebuilt by this run"
verify_rebuild_coverage.py --marker "$REBUILD_MARKER"

echo
echo "done; results/ rebuilt from $BENCH_ROOT"
