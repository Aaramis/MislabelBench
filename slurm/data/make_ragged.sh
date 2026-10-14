#!/bin/bash
# Cells of the injection grid with a quarter of the OTHER lineages truncated.
#
# A one-off check established that the tool accepts lineages of unequal depth: 402
# sequences with a quarter cut to genus and a quarter to family ran through and flagged 11. That is a
# robustness measurement -- nothing was mislabelled in it, so 11 is a count and not a recall -- and
# it leaves the question a user actually has: does an incomplete lineage hide a real mislabel?
#
# The dataset here answers the half of that question which is well posed. A sequence whose label we
# faked keeps its full lineage; a quarter of the rest is cut to genus and a quarter to family. So the
# injected truth is untouched, recall means exactly what it means in the grid, and the comparison is
# the same cell with and without the truncation. The other half -- truncating the faked sequences
# themselves -- is not built here: if a lineage stops at family and the error is at species, the rank
# of the error is no longer declared and "was it detected" has no agreed answer. That is a convention
# to settle, not an experiment to run.
#
# The truncation rule is that check's, deliberately: the two then say something about the same
# shape of input.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SRC="$BENCH_ROOT/data/injected"
OUT="$BENCH_ROOT/data/ragged"
# Family distance at the top rate, every k the grid uses, three seeds. Family because it is the
# distance the minimal-case work sits on, and every k because the one difference between the tools
# lives on that axis and this asks whether truncation moves it.
CELLS="${RAGGED_CELLS:-}"
if [ -z "$CELLS" ]; then
    for k in 1 2 3 5 10; do
        for s in 1 2 3; do CELLS="$CELLS inj_family_r0.05_k${k}_s${s}"; done
    done
fi

rm -rf "$OUT"
mkdir -p "$OUT"
for cell in $CELLS; do
    src="$SRC/$cell"
    [ -s "$src/$cell.tax" ] || { echo "no such cell: $cell" >&2; exit 1; }
    d="$OUT/rag_$cell"
    mkdir -p "$d"
    ln -sfn "../../gtdb/gtdb_arc2k.fasta" "$d/rag_$cell.fasta"
    cp "$src/$cell.truth.json" "$d/rag_$cell.truth.json"
    python3 - "$src/$cell.tax" "$src/$cell.truth.json" "$d/rag_$cell.tax" <<'PY'
import json, sys
from pathlib import Path
tax, truth, out = (Path(p) for p in sys.argv[1:4])
spoiled = set(json.loads(truth.read_text())["injected"])
rows = [l.split("\t", 1) for l in tax.read_text().splitlines() if l.strip()]
cut = {"genus": 0, "family": 0, "whole": 0}
with out.open("w") as fh:
    # i % 4 over the untouched rows only, so the share truncated does not depend on where the
    # injected sequences happen to fall in the file.
    i = 0
    for name, lin in rows:
        if name in spoiled:
            cut["whole"] += 1
        else:
            r = lin.split(";")
            if i % 4 == 1:
                r, _ = r[:6], cut.__setitem__("genus", cut["genus"] + 1)
            elif i % 4 == 2:
                r, _ = r[:5], cut.__setitem__("family", cut["family"] + 1)
            else:
                cut["whole"] += 1
            lin = ";".join(r)
            i += 1
        fh.write(f"{name}\t{lin}\n")
print(f"  {out.parent.name}: {cut['whole']} whole, {cut['genus']} cut to genus, "
      f"{cut['family']} cut to family")
PY
done

python3 - "$OUT" "$BENCH_ROOT" <<'PY'
import json, sys
from pathlib import Path
out, root = Path(sys.argv[1]), Path(sys.argv[2])
sets = []
for d in sorted(out.iterdir()):
    if not d.is_dir():
        continue
    fa, tax = d / f"{d.name}.fasta", d / f"{d.name}.tax"
    n = sum(1 for l in fa.open() if l.startswith(">"))
    w = len("".join(fa.read_text().split(">")[1].split("\n")[1:]))
    sets.append({"name": d.name, "n_seqs": n, "aln_len": w,
                 "fasta": str(fa.relative_to(root)), "tax": str(tax.relative_to(root))})
json.dump({"source": "injected cells with a quarter of the untouched lineages truncated",
           "datasets": sets}, open(out / "datasets.json", "w"), indent=2)
print(f"{len(sets)} ragged datasets, {sets[0]['n_seqs']} sequences each")
PY
