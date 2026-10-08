#!/usr/bin/env python3
"""Pick one RAxMLGrove tree for the simulated control, from stated requirements.

The point of moving off a hand-made tree is that the choice stops being ours. So the criteria here are
the control's own requirements rather than preferences, each one with the reason it exists, and the
script reports how many trees satisfy them so a reader can see how much freedom the pick had.

  DNA, one partition          the control simulates one marker, as the benchmark's references are
  NUM_TAXA 700 to 1000        the hand-made control had 864 sequences; keeping the size comparable is
                              what lets the two be read against each other
  sites 1200 to 1800          the archaeal alignment is 1478 columns wide, and per-sequence cost
                              depends on alignment width, so a tree whose MSA is 6000 sites would
                              change the timing for a reason unrelated to the tree
  a model with a rate         GTR and GTRGAMMA carry the parameters a simulator needs; GTRCAT and
                              GTRCATI are RAxML's rate-category approximations and do not
  TREE_HEIGHT present         needed by the rank cuts, which are quantiles of node height

Of the candidates the pick is by seed over the TREE_ID ordering, so it is reproducible and so a second
tree can be drawn without reopening the criteria. The join is PARTITION.PARENT_ID = TREE.TREE_ID, which
is not obvious from the column names and cost one wrong query to find.
"""

import argparse
import json
import random
import sqlite3
from pathlib import Path

CRITERIA = """p.DATA_TYPE = 'DNA'
          and t.OVERALL_NUM_PARTITIONS = 1
          and t.NUM_TAXA between 700 and 1000
          and p.NUM_ALIGNMENT_SITES between 1200 and 1800
          and p.MODEL in ('GTR', 'GTRGAMMA')
          and t.TREE_HEIGHT is not null"""

FIELDS = ["t.TREE_ID", "t.NUM_TAXA", "t.TREE_HEIGHT", "t.TREE_DIAMETER", "t.BRANCH_LENGTH_MEAN",
          "t.BRANCH_LENGTH_VARIANCE", "t.MISSING_DATA_RATE", "p.MODEL", "p.ALPHA",
          "p.NUM_ALIGNMENT_SITES", "p.GAPS", "p.RATE_AC", "p.RATE_AG", "p.RATE_AT", "p.RATE_CG",
          "p.RATE_CT", "p.RATE_GT", "p.FREQ_A", "p.FREQ_C", "p.FREQ_G", "p.FREQ_T"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/grove/latest_all.db")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", help="write the chosen tree's record here")
    args = p.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()
    sql = (f"select {', '.join(FIELDS)} from TREE t join PARTITION p on p.PARENT_ID = t.TREE_ID "
           f"where {CRITERIA} order by t.TREE_ID")
    rows = cur.execute(sql).fetchall()
    if not rows:
        raise SystemExit("no tree satisfies the criteria; they are stated in this file's docstring")

    names = [f.split(".", 1)[1] for f in FIELDS]
    # The seed picks among the candidates rather than shuffling them, so the same seed gives the same
    # tree whatever order sqlite returns, and ordering by TREE_ID makes that order fixed anyway.
    chosen = dict(zip(names, rows[random.Random(args.seed).randrange(len(rows))]))
    chosen["n_candidates"] = len(rows)
    chosen["seed"] = args.seed
    chosen["criteria"] = " ".join(CRITERIA.split())

    print(f"{len(rows)} tree(s) satisfy the criteria; seed {args.seed} picks TREE_ID "
          f"{chosen['TREE_ID']}")
    for k in ("NUM_TAXA", "NUM_ALIGNMENT_SITES", "MODEL", "ALPHA", "TREE_HEIGHT",
              "BRANCH_LENGTH_MEAN", "BRANCH_LENGTH_VARIANCE", "GAPS", "MISSING_DATA_RATE"):
        print(f"  {k:26} {chosen[k]}")
    if args.out:
        Path(args.out).write_text(json.dumps(chosen, indent=2) + "\n")


if __name__ == "__main__":
    main()
