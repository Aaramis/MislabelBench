#!/bin/bash
#SBATCH --job-name=aldiscore
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=%x-%j.log
#
# Alignment difficulty before and after the foreign donors, with AlDiScore (Stamatakis lab, bioRxiv
# 10.64898/2026.05.29.727837; github.com/MaBody/aldiscore): a reference-free difficulty from 0 to 1
# predicted from the unaligned sequences. The protocol asks for the alignment difficulty "before and
# after" for error kind 6, and the cmalign bit-score gap stood in for it until this ran.
#
# Scored: the archaeal 7 051 and its 2 023 subset, the bacterial clade and its subset, and the nine
# foreign cells (the 2 023 plus their donors). Every input is given unaligned: the gap columns of an
# aligned file are stripped here, since the predictor takes raw sequences. One JSON line per set in
# results/aldiscore/scores.jsonl, read by bin/analysis/aldiscore_summary.py.
#
# Not on PyPI; installed from a clone at a pinned commit into a venv made by the deployment's own
# python 3.12, the way slurm/data/fetch_grove.sh does, with the same reasons (the compute image's python
# has no ensurepip). parasail and lightgbm come as x86-64 wheels. No timing is read off this job.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
echo "running on $(hostname)"

REPO_URL=https://github.com/MaBody/aldiscore
COMMIT=cc2de71f7ca1096a9cf3ef1ea3b83622e9a27a51
BASE_PY="${BASE_PY:-/shared/software/miniconda_deployment/envs/python-3.12/bin/python}"
OUT="$BENCH_ROOT/results/aldiscore"
TOOL="$BENCH_ROOT/data/aldiscore"
mkdir -p "$OUT" "$TOOL"

[ -x "$BASE_PY" ] || { echo "no $BASE_PY; the deployment moved" >&2; exit 1; }
if [ ! -d "$TOOL/src/.git" ]; then
    room_for 5000
    git clone --quiet "$REPO_URL" "$TOOL/src"
fi
git -C "$TOOL/src" checkout --quiet "$COMMIT"
if ! "$TOOL/env/bin/python" -c "import aldiscore" 2>/dev/null; then
    rm -rf "$TOOL/env"
    room_for 20000
    "$BASE_PY" -m venv "$TOOL/env"
    "$TOOL/env/bin/pip" install --quiet --upgrade pip
    "$TOOL/env/bin/pip" install --quiet "$TOOL/src"
fi
"$TOOL/env/bin/pip" freeze > "$OUT/env-requirements.txt"
"$TOOL/env/bin/python" --version > "$OUT/provenance.txt"
echo "aldiscore $COMMIT" >> "$OUT/provenance.txt"

# name<TAB>fasta, aligned or not; gaps are stripped into a scratch copy either way. The 2 000-sequence
# sets first: the before-and-after is the subset against the foreign cells built on it, and the first
# submission spent ninety minutes on the 7 051 without a line of output, the two large sets being
# the ones whose pairwise features scale worst. They come last, so a time limit costs only them.
# It did: the 7 051 ran out of 32 GB after three and a half hours and the clade was never reached;
# the two are listed for the record, and scoring them needs more memory and a longer limit.
sets="$OUT/sets.tsv"
{
    printf 'gtdb_arc2k\t%s\n' "$BENCH_ROOT/data/gtdb/gtdb_arc2k.fasta"
    for d in "$BENCH_ROOT"/data/foreign/fgn_*; do
        printf '%s\t%s\n' "$(basename "$d")" "$d/$(basename "$d").fasta"
    done
    printf 'gtdb_bac2k\t%s\n' "$BENCH_ROOT/data/gtdb/gtdb_bac2k.fasta"
    printf 'gtdb_arc1200\t%s\n' "$BENCH_ROOT/data/gtdb/gtdb_arc1200.fasta"
    printf 'gtdb_bac_lachnospirales\t%s\n' "$BENCH_ROOT/data/gtdb/gtdb_bac_lachnospirales.aligned.fasta"
} > "$sets"

: > "$OUT/scores.jsonl"
while IFS=$'\t' read -r name fasta; do
    [ -f "$fasta" ] || { echo "missing $fasta" >&2; exit 1; }
    raw="$OUT/tmp_${name}.fasta"
    "$TOOL/env/bin/python" - "$fasta" "$raw" <<'PY'
import sys
src, dst = sys.argv[1:3]
with open(src) as f, open(dst, "w") as g:
    for line in f:
        g.write(line if line.startswith(">") else line.replace("-", "").replace(".", "").upper())
PY
    n=$(grep -c '>' "$raw")
    echo "== $name: $n sequences"
    text=$("$TOOL/env/bin/aldiscore" predict "$raw" --in-type DNA 2>&1 | tee "$OUT/${name}.out")
    "$TOOL/env/bin/python" - "$name" "$n" "$OUT/${name}.out" >> "$OUT/scores.jsonl" <<'PY'
import json, re, sys
name, n, out = sys.argv[1], int(sys.argv[2]), open(sys.argv[3]).read()
nums = re.findall(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", out)
print(json.dumps({"set": name, "n_sequences": n, "stdout": out.strip(), "numbers_in_output": nums}))
PY
    rm -f "$raw"
done < "$sets"
echo "scored $(wc -l < "$OUT/scores.jsonl") sets"
