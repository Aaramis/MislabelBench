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
# The interpreter org_script.py needs. It imports biopython and scikit-optimize at module level --
# the README names biopython, numpy, pandas and matplotlib and not scikit-optimize, so the imports are
# the requirement and not the README -- and the cluster's python3 has neither.
#
# Built here rather than left as a manual step, because a prerequisite that lives in someone's shell
# history is the opposite of what this repository is for. Versions are **recorded, not pinned**: a
# version pinned from a laptop against the cluster's python minor version is a guess that fails on
# first contact, whereas what the resolver chose is a fact worth keeping. It costs nothing in
# reproducibility either, since the data this interpreter produces is pinned by sha256 downstream and
# the simulator itself is the binary inside the pinned repository, not a package from here.
# 13 000 files measured for biopython, scikit-optimize and the scipy that comes with it, against a
# 100 000-file quota on $HOME that one minimal-case arm already takes a fifth of. Cheap to check, and
# the alternative is discovering it as an OSError 122 halfway through pip.
# Built from a pinned cluster interpreter and not from the node's python3. The login node has
# 3.12 but the compute image has 3.8 without ensurepip, so `python3 -m venv` fails there with
# "ensurepip is not available" -- which is where the first run of this script died. The
# deployment's own python environments are visible from every node and carry ensurepip; the
# pin follows prelude.sh's NEXTFLOW_ENV: checked rather than trusted, alternatives listed when it
# is gone, since the deployment prunes old environments eventually.
BASE_PY=/shared/software/miniconda_deployment/envs/python-3.12/bin/python
[ -x "$BASE_PY" ] || {
    echo "no interpreter at $BASE_PY: the pinned environment is gone. Available:" >&2
    ls -d /shared/software/miniconda_deployment/envs/python-3.* 2>/dev/null >&2
    echo "pick one, update BASE_PY in slurm/fetch_grove.sh, and record the change" >&2
    exit 1
}
# An environment that cannot import what it was built for is rebuilt, not reported. The first run
# of this script left a venv made by a python without ensurepip, so it had an interpreter and no
# packages; the `-x env/bin/python` guard then skipped the build on the second run and the import
# check below failed on a directory that would never pass. One rebuild, from the pinned python.
if [ -x "$OUT/env/bin/python" ] && ! "$OUT/env/bin/python" -c "import Bio, skopt, numpy" 2>/dev/null; then
    echo "the environment at $OUT/env cannot import its packages; rebuilding it"
    rm -rf "$OUT/env"
fi
if [ ! -x "$OUT/env/bin/python" ]; then
    room_for 15000
    "$BASE_PY" -m venv "$OUT/env"
    "$OUT/env/bin/pip" install --quiet --upgrade pip
    "$OUT/env/bin/pip" install --quiet biopython scikit-optimize numpy
fi
"$OUT/env/bin/python" -c "import Bio, skopt, numpy" || {
    echo "the environment at $OUT/env cannot import Bio, skopt and numpy even after a rebuild" >&2
    exit 1
}
"$OUT/env/bin/pip" freeze > "$OUT/env-requirements.txt"
python3 - "$OUT" <<'PYE'
import json, subprocess, sys
from pathlib import Path
out = Path(sys.argv[1])
rec = json.loads((out / "provenance.json").read_text())
rec["interpreter"] = {
    "path": str(out / "env" / "bin" / "python"),
    "python": subprocess.run([str(out / "env/bin/python"), "-V"], capture_output=True,
                             text=True).stdout.strip(),
    "requirements": "env-requirements.txt",
}
(out / "provenance.json").write_text(json.dumps(rec, indent=2) + "\n")
print(rec["interpreter"]["python"], "with", len((out / "env-requirements.txt").read_text().splitlines()),
      "packages recorded in env-requirements.txt")
PYE
echo "wrote $OUT/provenance.json"
