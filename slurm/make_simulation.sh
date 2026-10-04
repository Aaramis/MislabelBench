#!/bin/bash
# Protocol.md 2.1's control: a reference where every label is certain, un-injected and injected.
#
# Two things it gives that the injected grid cannot.
#
# The first is in 2.1: "Simulation shows that the method works where the answer is certain."
#
# The second is in 2.4, which says of real data that "a sequence we did not inject is not known to
# be correctly labelled ... so a flag on such a sequence cannot be called a false positive", and is
# why the whole benchmark reports collateral flags against a measured baseline instead. Here it can:
# the taxonomy is the tree, so a flag on an untouched sequence is a false positive outright, and the
# un-injected cell below measures that rate directly.
#
# Small on purpose -- 2.1 calls it a control and not a second set of results. One simulated
# reference and six injected cells against the grid's 180.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$HOME/bench}"
OUT="$BENCH_ROOT/data/simulated"
mkdir -p "$OUT"

# The reference itself. Deterministic from the seed, so this is idempotent like the other make_ scripts.
if [ ! -s "$OUT/sim/sim.tax" ]; then
    mkdir -p "$OUT/sim"
    # Six per species, not three. inject_mislabels.py needs k+1 members in a donor group so that
    # one stays correctly labelled, so three per species silently yields zero injections at k=3 --
    # which is what the first run of this script produced, the warning sitting unread in warn.txt.
    # Six supports k up to 5, which is the grid's range bar k=10.
    python3 "$BENCH_ROOT/bin/simulate_reference.py" --seed 1 --per-species 6 \
        --prefix "$OUT/sim/sim" > "$OUT/sim/sim.txt"
fi
ALN="$OUT/sim/sim.fasta"
TAX="$OUT/sim/sim.tax"

# Injected cells. Distances only to genus: deeper than that and the simulated tree has no
# divergence left to tell the recipient from the donor, which is a property of the model and not a
# finding, so the cells that would measure it are not made.
for dist in species genus family; do
  for k in 1 2 3 5; do
    name="sim_${dist}_k${k}_s1"
    d="$OUT/$name"
    [ -s "$d/$name.tax" ] && continue
    mkdir -p "$d"
    python3 "$BENCH_ROOT/bin/inject_mislabels.py" "$TAX" \
      --distance "$dist" --rate 0.05 --k "$k" --seed 1 \
      --prefix "$d/$name" >/dev/null 2>"$d/warn.txt" || { echo "FAILED $name" >&2; continue; }
    ln -sf "$ALN" "$d/$name.fasta"
  done
done

python3 - "$OUT" "$ALN" "$BENCH_ROOT" <<'PY'
import json, sys
from pathlib import Path
out, aln, root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
text = aln.read_text()
n = sum(1 for l in text.splitlines() if l.startswith(">"))
width = len(text.split("\n", 1)[1].split("\n")[0])
cells = [{"name": "sim", "n_seqs": n, "aln_len": width,
          "fasta": str(aln.relative_to(root)), "tax": str((out / "sim/sim.tax").relative_to(root))}]
for d in sorted(out.glob("sim_*")):
    tax = d / f"{d.name}.tax"
    if tax.exists():
        cells.append({"name": d.name, "n_seqs": n, "aln_len": width,
                      "fasta": str((d / f"{d.name}.fasta").relative_to(root)),
                      "tax": str(tax.relative_to(root))})
(out / "datasets.json").write_text(json.dumps(
    {"source": "simulated under Jukes-Cantor, labels certain by construction (Protocol 2.1)",
     "datasets": cells}, indent=2))
print(f"{len(cells)} cells: one un-injected reference and {len(cells)-1} injected, "
      f"{n} sequences of {width} columns")
PY
