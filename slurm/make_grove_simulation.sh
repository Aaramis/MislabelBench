#!/bin/bash
#SBATCH --job-name=grovesim
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=4:00:00
#SBATCH --output=%x-%j.log
#
# Protocol.md 2.1's control, rebuilt on a RAxMLGrove tree instead of a hand-made one.
#
# What it replaces and why is in Decisions.md: a co-author asked how the simulated reference's tree
# and parameters are chosen, and the honest answer was "by hand". Here the topology, the substitution
# model, its rates and base frequencies, the alpha of the gamma, the alignment width and the empirical
# missing-data pattern all come out of the database, and the tree is picked by bin/grove_select.py
# from stated requirements. Nothing in this file chooses a number that affects the data.
#
# The chain is: pick a tree -> let RAxMLGrove download it and simulate along it with AliSim -> give it
# a taxonomy that is a function of the tree (bin/grove_taxonomy.py) -> inject known mislabels. Every
# step checked, because the upstream script swallows its own failures: download_trees() wraps each
# file in `except Exception: pass`, so a tree that is not on GitHub, a missing presence/absence matrix
# and a simulator that never ran all look the same from outside, which is an empty or absent file and
# a zero exit status.
#
# Not measured work. Nothing here is timed and nothing here runs a benchmarked tool, so it needs an
# interpreter with biopython and scikit-optimize rather than a pinned container; the data it produces
# is pinned instead, by sha256, in the record it writes.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"

GROVE="$BENCH_ROOT/data/grove"
OUT="$BENCH_ROOT/data/grove_sim"
SEED="${GROVE_SEED:-42}"
# The rate is not ours to choose either. inject_mislabels.py keeps one correct member in every donor
# group, so a cell at k=1 needs as many non-singleton species as it wants injections, and how many of
# those a tree has is a property of the tree: the first tree this was developed against had 35 for 822
# tips and could not reach 5 %, the tree the criteria actually pick has 34 for 400 and can. So the
# ladder below is tried from the top and the first rate every cell reaches exactly is the one used.
# 5 % is first because it is the rate the real injection grid runs at, which is what makes the control
# readable against it.
RATES="${GROVE_RATES:-0.05 0.03 0.02}"

# biopython and scikit-optimize, both imported at org_script.py's module level. The README names
# biopython, numpy, pandas and matplotlib and does not mention scikit-optimize, so take the imports as
# the requirement and not the README.
GROVE_PY="${GROVE_PY:-python3}"
"$GROVE_PY" -c "import Bio, skopt" 2>/dev/null || {
    echo "$GROVE_PY cannot import Bio and skopt, which org_script.py needs at module level." >&2
    echo "Point GROVE_PY at an interpreter that can, for instance a conda environment created with" >&2
    echo "  conda create -p $GROVE/env python=3.11 biopython scikit-optimize numpy -y" >&2
    echo "and record its versions beside the data, since they are part of how it was made." >&2
    exit 1
}

[ -s "$GROVE/latest_all.db" ] || { echo "no $GROVE/latest_all.db: run slurm/fetch_grove.sh" >&2; exit 1; }
[ -d "$GROVE/scripts" ] || { echo "no $GROVE/scripts: run slurm/fetch_grove.sh" >&2; exit 1; }
PINNED=$(python3 -c "import json;print(json.load(open('$GROVE/provenance.json'))['scripts_commit'])")
HAVE=$(git -C "$GROVE/scripts" rev-parse HEAD)
[ "$PINNED" = "$HAVE" ] || { echo "scripts at $HAVE, provenance pins $PINNED" >&2; exit 1; }
# The simulator ships inside the pinned repository, so the commit pins the binary too.
IQTREE="$GROVE/scripts/tools/iqtree-2.2.0-beta-Linux/bin/iqtree2"
[ -s "$IQTREE" ] || { echo "no AliSim binary at $IQTREE" >&2; exit 1; }
# It is committed mode 644, so a fresh clone cannot run it. AliSim.execute() catches the
# PermissionError, prints it and returns 1, and the assembly step then runs on a file that was never
# written, so the failure arrives several steps away from its cause.
[ -x "$IQTREE" ] || chmod +x "$IQTREE"

mkdir -p "$OUT"

# 1. The tree. Reproducible from the seed and the criteria; see bin/grove_select.py for both.
if [ ! -s "$GROVE/tree.json" ]; then
    python3 "$BENCH_ROOT/bin/grove_select.py" --db "$GROVE/latest_all.db" --seed "$SEED" \
        --out "$GROVE/tree.json" | tee "$GROVE/tree.txt"
fi
read -r TREE_ID NUM_TAXA NUM_SITES < <(python3 -c "
import json
d = json.load(open('$GROVE/tree.json'))
print(d['TREE_ID'], d['NUM_TAXA'], d['NUM_ALIGNMENT_SITES'])")
[ -n "$TREE_ID" ] || { echo "no TREE_ID in $GROVE/tree.json" >&2; exit 1; }
echo "tree $TREE_ID, $NUM_TAXA taxa, $NUM_SITES sites"
RAW="$OUT/raw/$TREE_ID"

# 2. Download and simulate.
#
# No --insert-matrix-gaps, and the reason is worth stating because the flag sounds like exactly what
# this control wants. The presence/absence matrix is indexed by partition, not by site:
# assemble_sequences() does `bit = matrix[taxon][j]` over partitions j and, when the bit is 0, fills
# that taxon's whole partition with the blank symbol. On a single-partition dataset -- which is what
# the criteria ask for, because our references are single-marker -- the only two things it can do are
# nothing at all and blanking an entire sequence. It cannot produce a within-sequence gap pattern. So
# this alignment has no gaps, exactly like the hand-made control's, and the control's claim is about
# the topology and the substitution model, not about the alignment. The alternative was to drop the
# single-partition requirement and take a concatenation's genuine per-gene missing data, which was
# rejected: it would make the simulated reference differ from the real ones in a second way in order
# to fix the first.
#
# --force-rewrite only destroys a database under `create` (org_script.py line 2566 guards it on the
# operation); under `generate` it merely reuses the tree's own directory name instead of writing
# $TREE_ID_1, _2, _3 on every rerun. Needed for idempotency, safe for the pinned database.
if [ ! -s "$RAW/assembled_sequences.fasta" ]; then
    mkdir -p "$OUT/raw"
    "$GROVE_PY" "$GROVE/scripts/org_script.py" generate \
        -n "$GROVE/latest_all.db" -q "TREE_ID = '$TREE_ID'" \
        -g alisim \
        --seed "$SEED" --force-rewrite -o "$OUT/raw" 2>&1 | tee "$OUT/generate.log"
fi

# 3. Everything the upstream script would have let pass in silence.
[ -s "$RAW/tree_best.newick" ] || { echo "no tree downloaded: $RAW/tree_best.newick" >&2; exit 1; }
[ -s "$RAW/assembled_sequences.fasta" ] || { echo "AliSim produced no alignment" >&2; exit 1; }

# 4. The taxonomy, from the tree alone.
mkdir -p "$OUT/grove"
python3 "$BENCH_ROOT/bin/grove_taxonomy.py" --tree "$RAW/tree_best.newick" \
    --prefix "$OUT/grove/grove" | tee "$OUT/grove/grove.txt"

# The alignment and the taxonomy have to name the same sequences: AliSim labels tips from the tree it
# was given, so a mismatch here means they came from different trees, which no later step would notice.
# The copy is unwrapped on the way out, both because biopython writes 60-column FASTA and the rest of
# this repository's simulated data is one line per sequence, and because the file this writes is the
# one whose sha256 goes in the manifest.
python3 - "$RAW/assembled_sequences.fasta" "$OUT/grove/grove.tax" "$OUT/grove/grove.fasta" \
         "$NUM_TAXA" "$NUM_SITES" <<'PYA'
import sys
from pathlib import Path
src, tax, dest = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
n_taxa, n_sites = int(sys.argv[4]), int(sys.argv[5])
seqs, order = {}, []
for line in src.read_text().splitlines():
    if line.startswith(">"):
        name = line[1:].split()[0]
        if name in seqs:
            sys.exit(f"duplicate sequence id in the simulated alignment: {name}")
        seqs[name] = []
        order.append(name)
    elif order:
        seqs[order[-1]].append(line.strip())
seqs = {k: "".join(v) for k, v in seqs.items()}
labelled = [l.split("\t")[0] for l in tax.read_text().splitlines()]
if set(seqs) != set(labelled):
    sys.exit(f"alignment and taxonomy name different sequences, e.g. "
             f"{sorted(set(seqs) ^ set(labelled))[:5]}")
if len(seqs) != n_taxa:
    sys.exit(f"{len(seqs)} sequences simulated, the database says the tree has {n_taxa} taxa")
widths = {len(v) for v in seqs.values()}
if len(widths) != 1:
    sys.exit(f"ragged alignment: widths {sorted(widths)[:5]}")
if widths != {n_sites}:
    sys.exit(f"{widths.pop()} columns, the database says {n_sites} sites")
empty = [k for k, v in seqs.items() if set(v) <= set("-?N")]
if empty:
    sys.exit(f"{len(empty)} gap-only sequences, e.g. {empty[:3]}")
dest.write_text("".join(f">{k}\n{seqs[k]}\n" for k in sorted(seqs)))
print(f"{len(seqs)} sequences of {n_sites} columns, named as the taxonomy names them")
PYA

ALN="$OUT/grove/grove.fasta"
# See make_grid.sh for why the cell alignments are relative links and not absolute ones.
ALN_REL=$(python3 -c 'import os,sys;print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$ALN" "$OUT/any_cell")

# 5. The injected cells. Distances only to family: the real grid goes to phylum, but the ranks here
# are height cuts on one tree, so above family the recipient and the donor are no longer distinguishable
# by anything the model put in the sequences -- a property of the control and not a result.
#
# First the rate: probe the twelve distance-by-k combinations at one seed and take the highest rate
# at which none of them falls short. A cell that still warns when the real cells are built is dropped
# and listed rather than run at a quietly different rate, which is what Protocol.md 2.4 asks for.
PROBE="$OUT/.probe"
probe_rate() {
    # Zero when every one of the twelve cells reaches rate $1 exactly, one when any falls short.
    local r="$1" dist k
    rm -rf "$PROBE"; mkdir -p "$PROBE"
    for dist in species genus family; do
      for k in 1 2 3 5; do
        if ! python3 "$BENCH_ROOT/bin/inject_mislabels.py" "$OUT/grove/grove.tax" \
             --distance "$dist" --rate "$r" --k "$k" --seed 1 --prefix "$PROBE/p" \
             >/dev/null 2>"$PROBE/warn.txt"; then
          return 1
        fi
        if grep -q "^warning:" "$PROBE/warn.txt"; then
          return 1
        fi
      done
    done
    return 0
}

RATE=""
for r in $RATES; do
    if probe_rate "$r"; then
        RATE="$r"
        break
    fi
    echo "rate $r is out of reach for at least one cell on this tree"
done
rm -rf "$PROBE"
[ -n "$RATE" ] || { echo "no rate in '$RATES' is reachable for every cell" >&2; exit 1; }
echo "injecting at $RATE"

: > "$OUT/skipped.txt"
for dist in species genus family; do
  for k in 1 2 3 5; do
    for seed in 1 2 3; do
      name="grove_${dist}_k${k}_s${seed}"
      d="$OUT/$name"
      if [ ! -s "$d/$name.tax" ]; then
        mkdir -p "$d"
        python3 "$BENCH_ROOT/bin/inject_mislabels.py" "$OUT/grove/grove.tax" \
          --distance "$dist" --rate "$RATE" --k "$k" --seed "$seed" \
          --prefix "$d/$name" >/dev/null 2>"$d/warn.txt" || { echo "FAILED $name" >&2; continue; }
        if grep -q "^warning:" "$d/warn.txt"; then
          sed "s/^/$name /" "$d/warn.txt" >> "$OUT/skipped.txt"
          rm -rf "$d"
          continue
        fi
      fi
      # See make_grid.sh: relative, and refreshed even for a cell that already exists, so that a
      # clone's links point inside the clone.
      ln -sfn "$ALN_REL" "$d/$name.fasta"
    done
  done
done
if [ -s "$OUT/skipped.txt" ]; then
    echo "cells dropped for want of donor groups:"
    cat "$OUT/skipped.txt"
fi

# 6. The manifest, in the shape main.nf reads, plus what the data was made from.
python3 - "$OUT" "$ALN" "$BENCH_ROOT" "$GROVE/tree.json" "$RAW" "$RATE" <<'PY'
import hashlib, json, sys
from pathlib import Path
out, aln, root, treejson, raw, rate = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]),
                                       Path(sys.argv[4]), Path(sys.argv[5]), float(sys.argv[6]))
lines = aln.read_text().splitlines()
n = sum(1 for l in lines if l.startswith(">"))
width = len(lines[1])
cells = [{"name": "grove", "n_seqs": n, "aln_len": width,
          "fasta": str(aln.relative_to(root)),
          "tax": str((out / "grove/grove.tax").relative_to(root))}]
for d in sorted(out.glob("grove_*")):
    tax = d / f"{d.name}.tax"
    if tax.exists():
        cells.append({"name": d.name, "n_seqs": n, "aln_len": width,
                      "fasta": str((d / f"{d.name}.fasta").relative_to(root)),
                      "tax": str(tax.relative_to(root))})
(out / "datasets.json").write_text(json.dumps(
    {"source": "RAxMLGrove tree, AliSim along it, taxonomy from the tree (Protocol 2.1)",
     "tree": json.loads(treejson.read_text()),
     "taxonomy": json.loads((out / "grove/grove.grove_tax.json").read_text()),
     "requested_rate": rate,
     "alignment_sha256": hashlib.sha256(aln.read_bytes()).hexdigest(),
     "newick_sha256": hashlib.sha256((raw / "tree_best.newick").read_bytes()).hexdigest(),
     "datasets": cells}, indent=2) + "\n")
print(f"{len(cells)} cells: one un-injected reference and {len(cells)-1} injected, "
      f"{n} sequences of {width} columns")
PY
