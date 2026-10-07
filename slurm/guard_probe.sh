#!/bin/bash
#SBATCH --job-name=guardprobe
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=1:00:00
#SBATCH --output=%x-%j.log
#
# Does `error` inside a subscribe closure actually abort the run?
#
# main.nf guards both paths against join() silently dropping a cell by counting what arrives and
# calling error() if the count is wrong. join() dropping a cell is the one failure that would make a
# short grid look complete, so these two counters are the whole protection against it -- and they run
# inside `.count().subscribe { ... }`, on the dataflow thread, where a thrown exception may or may not
# reach the launcher. Reasoning about it is not enough: the guard is either live or it is decoration.
#
# Four stub runs on a copy of the project: both paths, each with the expected count untouched and then
# deliberately off by one. The untouched runs must pass, which also checks the arithmetic -- the staged
# guard counts only the fork conditions, conds.count { impl == 'sativaepang' }, and a wrong expression
# there would fail a correct run. The perturbed runs must fail. A stub run executes no tool, so this
# costs seconds and measures nothing.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
nextflow_env

WORK=$BENCH_ROOT/results/guard_probe
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$BENCH_ROOT"/{main.nf,nextflow.config,conf,modules,bin,assets} "$WORK/"
# data_ascii/ and its n100 set went with version 1, which left this script copying a directory that is
# not there: under set -e the probe died on the cp, before any run, so the two guards it exists to check
# went unverified from that commit on. The manifest is written here instead, naming the committed
# 2 023-sequence set by absolute path. Absolute because main.nf's resolvePath resolves a relative
# manifest path against projectDir, which here is $WORK, and $WORK holds only the code: the copy above
# deliberately leaves data/ out, so data/gtdb/... would be looked for where it is not.
python3 - "$BENCH_ROOT" "$WORK/datasets.json" <<'PYJ'
import json, sys
root, out = sys.argv[1], sys.argv[2]
json.dump({"source": "guard probe: the committed 2k set, by absolute path",
           "datasets": [{"name": "gtdb_arc2k", "n_seqs": 2023, "aln_len": 1478,
                         "fasta": root + "/data/gtdb/gtdb_arc2k.fasta",
                         "tax": root + "/data/gtdb/gtdb_arc2k.tax"}]},
          open(out, "w"), indent=2)
PYJ

run_one() {
    local tag="$1"
    local dir="$WORK/$tag"
    mkdir -p "$dir"
    cd "$dir"
    local st=0
    nextflow run "$WORK" -stub-run ${STAGED_ARGS:-} \
        --datasets_json "$WORK/datasets.json" \
        --datasets gtdb_arc2k \
        --conditions upstream_raxml_T1,epang_T8_K25 \
        --sativa_taxcode BOT \
        --timing_trusted false \
        --trace_tag "guard_${tag}" \
        --outdir "$dir/out" > "$WORK/$tag.log" 2>&1 || st=$?
    echo "$st"
}

bump() {  # add one to the named guard's expected count, in the copy only
    python3 - "$WORK/main.nf" "$1" <<'PYB'
import sys, pathlib
p, var = pathlib.Path(sys.argv[1]), sys.argv[2]
s = p.read_text()
line = next(l for l in s.splitlines() if l.strip().startswith("def " + var + " ="))
assert s.count(line) == 1, var + ": anchor matched " + str(s.count(line)) + " times"
p.write_text(s.replace(line, line + " + 1", 1))
PYB
}
restore() { cp "$BENCH_ROOT/main.nf" "$WORK/main.nf"; }

single_control=$(run_one single_control)
bump expected
single_perturbed=$(run_one single_perturbed)
restore

export STAGED_ARGS="--staged true --folds_per_job 7"
staged_control=$(run_one staged_control)
bump expected_staged
staged_perturbed=$(run_one staged_perturbed)
restore
unset STAGED_ARGS

echo
printf "%-10s %-14s %s\n" path untouched "off by one"
printf "%-10s %-14s %s\n" single "exit $single_control" "exit $single_perturbed"
printf "%-10s %-14s %s\n" staged "exit $staged_control" "exit $staged_perturbed"
echo
grep -hoE "(collected|staged path scored) [0-9]+ .*" "$WORK"/single_perturbed.log "$WORK"/staged_perturbed.log 2>/dev/null | head -2 || true
echo
if [ "$single_control" = "0" ] && [ "$single_perturbed" != "0" ] \
   && [ "$staged_control" = "0" ] && [ "$staged_perturbed" != "0" ]; then
    echo "VERDICT: both guards are live, and both count what they should"
else
    echo "VERDICT: a guard is not live or miscounts" >&2
    for t in single_control single_perturbed staged_control staged_perturbed; do
        echo "--- $t"; tail -12 "$WORK/$t.log" 2>/dev/null || true
    done
    exit 1
fi
