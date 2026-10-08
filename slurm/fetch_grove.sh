#!/bin/bash
#SBATCH --job-name=fetchgrove
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=2:00:00
#SBATCH --output=%x-%j.log
#
# RAxMLGrove: empirical trees and model parameter estimates, to replace the simulated reference's
# hand-picked tree.
#
# Why this arrives at all. Protocol.md 2.1's simulated reference is the control that closes the one
# hole injection leaves: there, every label is correct by construction, so a flag on an untouched
# sequence is a false positive in the strict sense. A co-author's comment on that paragraph asked how
# the tree and the parameters are chosen, and the honest answer was "by hand": a balanced 3,2,2,2,2,3
# branching, branch lengths fixed per rank, Jukes-Cantor, no gaps. Zero flags on a reference that
# regular is weak evidence that zero flags would appear on a realistic one.
#
# What this buys that irregularity drawn by us would not: a citable provenance. "Topologies and model
# parameters drawn from RAxMLGrove" closes the question; "branch lengths drawn from a distribution we
# chose" invites it again one level down.
#
# It reverses a decision this repository records. bin/simulate_reference.py argues for forty lines of
# Jukes-Cantor rather than a pinned container, on the grounds that what matters is a model a reader can
# check. That argument is about a reader; the objection is a reviewer's. Decisions.md carries the
# reversal and the reason.
#
# Two sources, both pinned. The scripts are a git repository, so the commit is the pin; the database is
# a file, so the sha256 is. Both go into the provenance record, with the size and the date, the way
# every other fetch script here records what it took.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"

DB_URL="https://cme.h-its.org/exelixis/material/raxmlgrove/latest_all.db"
SCRIPTS_URL="https://github.com/angtft/RAxMLGroveScripts.git"
OUT="$BENCH_ROOT/data/grove"
mkdir -p "$OUT"
cd "$OUT"

if [ ! -d scripts ]; then
    git clone --quiet "$SCRIPTS_URL" scripts
fi
COMMIT=$(git -C scripts rev-parse HEAD)
echo "RAxMLGroveScripts at $COMMIT"

# --fail so a 404 is an error rather than an HTML file saved under a .db name, and -C - so a partial
# download resumes instead of starting over on a 140 MB file.
if [ ! -s latest_all.db ]; then
    curl -fsSL -C - -o latest_all.db "$DB_URL"
fi
DB_SHA=$(sha256sum latest_all.db | cut -d' ' -f1)
DB_SIZE=$(stat -c %s latest_all.db)
echo "latest_all.db $DB_SIZE bytes, sha256 $DB_SHA"

# What the database actually holds, so the query that picks a tree is written against measured
# numbers rather than guessed ones. The columns come from RAxMLGrove's own schema.
python3 - "$OUT" "$COMMIT" "$DB_SHA" "$DB_SIZE" "$DB_URL" <<'PYJ'
import json, sqlite3, sys, datetime
out, commit, sha, size, url = sys.argv[1:6]
con = sqlite3.connect(f"{out}/latest_all.db")
cur = con.cursor()
tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'")]
rec = {"source": url, "sha256": sha, "bytes": int(size), "scripts_commit": commit,
       "downloaded": datetime.date.today().isoformat(), "tables": tables}
if "TREE" in tables:
    cols = [r[1] for r in cur.execute("pragma table_info(TREE)")]
    rec["tree_columns"] = cols
    rec["n_trees"] = cur.execute("select count(*) from TREE").fetchone()[0]
    if "NUM_TAXA" in cols and "DATA_TYPE" in cols:
        rec["dna_trees_by_size"] = {
            band: cur.execute(
                "select count(*) from TREE where DATA_TYPE='DNA' and NUM_TAXA >= ? and NUM_TAXA < ?",
                (lo, hi)).fetchone()[0]
            for band, (lo, hi) in {"200-500": (200, 500), "500-1000": (500, 1000),
                                   "1000-2000": (1000, 2000), "2000-10000": (2000, 10000)}.items()}
print(json.dumps(rec, indent=2))
open(f"{out}/provenance.json", "w").write(json.dumps(rec, indent=2) + "\n")
PYJ
echo "wrote $OUT/provenance.json"
