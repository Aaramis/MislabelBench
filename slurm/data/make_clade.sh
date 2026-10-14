#!/bin/bash
# Build the error kind 3 cells: whole taxa relabelled, so nothing correct is left to confirm them.
#
# The protocol keeps kind 3 as a case to characterise rather than a grid to score. It is only worth
# the compute if the cells vary compactness and not just distance. So this is nine cells, not 180: three distances spanning the range the
# protocol names -- species is "a wrong label inside the correct genus", the hard case, and phylum
# the easy end -- by three seeds, six clades each spread over the separation range.
#
# Pure python and seconds to run, like make_grid.sh. No cluster needed.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
OUT="$BENCH_ROOT/data/clade"
mkdir -p "$OUT"
ALN="$BENCH_ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$BENCH_ROOT/data/gtdb/gtdb_arc2k.tax"
[ -s "$ALN" ] && [ -s "$TAX" ] || { echo "missing $ALN or $TAX" >&2; exit 1; }

# See make_grid.sh for why the cell alignments are relative links and not absolute ones.
ALN_REL=$(python3 -c 'import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' \
          "$ALN" "$OUT/any_cell")

# Idempotent, for the reason make_grid.sh gives: a cell is a function of its name.
for dist in species family phylum; do
  for seed in 1 2 3; do
    name="k3_${dist}_s${seed}"
    d="$OUT/$name"
    if [ ! -s "$d/$name.tax" ]; then
      mkdir -p "$d"
      python3 "$BENCH_ROOT/bin/inject_clade.py" "$TAX" --alignment "$ALN" \
        --distance "$dist" --n-clades 6 --seed "$seed" --prefix "$d/$name" \
        >"$d/clades.txt" 2>"$d/warn.txt" || { echo "FAILED $name" >&2; continue; }
    fi
    # See make_grid.sh: relative, and refreshed even for a cell that already exists. These nine
    # cells are committed, so without the refresh a clone keeps the links the author's machine wrote.
    ln -sfn "$ALN_REL" "$d/$name.fasta"
  done
done

# The manifest, relative to BENCH_ROOT for the reason make_grid.sh spells out.
python3 - "$OUT" "$ALN" "$BENCH_ROOT" <<'PY'
import json, sys
from pathlib import Path
out, aln, root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
n = sum(1 for l in aln.read_text().splitlines() if l.startswith(">"))
width = len(aln.read_text().split("\n>")[0].split("\n", 1)[1].replace("\n", ""))
cells = []
for d in sorted(out.glob("k3_*")):
    tax = d / f"{d.name}.tax"
    if tax.exists():
        cells.append({"name": d.name, "n_seqs": n, "aln_len": width,
                      "fasta": str((d / f"{d.name}.fasta").relative_to(root)),
                      "tax": str(tax.relative_to(root))})
(out / "datasets.json").write_text(json.dumps(
    {"source": "gtdb_arc2k, whole-clade relabelling (error kind 3)", "datasets": cells}, indent=2))
print(f"{len(cells)} kind 3 cells, {n} sequences of {width} columns")
PY
