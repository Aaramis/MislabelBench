#!/bin/bash
# The 2 023-sequence subset at five alignment widths, for the memory law's width term.
#
#   bash slurm/make_width.sh        # writes data/width/w<N>/ and data/width/datasets.json
#
# Columns are a prefix of the alignment, taxonomy unchanged. Deterministic, no seed.
set -euo pipefail
ROOT="${BENCH_ROOT:-$HOME/bench}"
OUT="$ROOT/data/width"
ALN="$ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$ROOT/data/gtdb/gtdb_arc2k.tax"
WIDTHS="${WIDTHS:-300 600 900 1200 1478}"
mkdir -p "$OUT"
entries=()
for w in $WIDTHS; do
    cell=$(printf 'w%04d' "$w")
    python3 "$ROOT/bin/truncate_alignment.py" --fasta "$ALN" --tax "$TAX" --columns "$w" \
        --prefix "$OUT/$cell/$cell"
    n=$(grep -c '>' "$OUT/$cell/$cell.fasta")
    entries+=("{\"name\": \"$cell\", \"n_seqs\": $n, \"aln_len\": $w, \"fasta\": \"data/width/$cell/$cell.fasta\", \"tax\": \"data/width/$cell/$cell.tax\"}")
done
{
    echo '{"source": "gtdb_arc2k, the first N columns of the alignment, taxonomy unchanged",'
    echo ' "datasets": ['
    printf '  %s' "${entries[0]}"; for e in "${entries[@]:1}"; do printf ',\n  %s' "$e"; done
    echo; echo ' ]}'
} > "$OUT/datasets.json"
python3 -c "import json; d=json.load(open('$OUT/datasets.json')); print(len(d['datasets']), 'width cells')"
