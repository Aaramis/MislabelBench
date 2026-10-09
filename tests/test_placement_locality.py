#!/usr/bin/env python3
"""bin/placement_locality.py on a six-leaf tree and a jplace written by hand.

The claim it exists to check -- that a removed sequence's placement lands among its k-1 co-carriers
-- has to be readable off an edge number, so the fixture pins the parser (edge labels on a Newick),
the best-edge choice by like_weight_ratio through the file's own `fields` order, and the two cases:
a placement whose edge sits inside the co-carriers' clade, and one that does not.

    python3 -m unittest tests.test_placement_locality
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"
HEADER = (";SeqID\tMislabeledLevel\tOriginalLabel\tProposedLabel\tConfidence"
          "\tOriginalTaxonomyPath\tProposedTaxonomyPath\tPerRankConfidence\tOriginalLabelExclusion")
TRUE = "d__A;p__P;c__C;o__O;f__F1;g__G1;s__S1"
WRONG = "d__A;p__P;c__C;o__O;f__F2;g__G2;s__S2"
# Six leaves: i1, i2, i3 are one species (S1), two of them injected with F2's lineage; c1, c2 are
# F2's own; o1 is another family. Edge numbers in braces, as a jplace tree carries them.
TREE = "(((i1:0.1{0},i2:0.1{1}):0.2{2},i3:0.3{3}):0.4{4},(c1:0.1{5},c2:0.1{6}):0.5{7},o1:0.9{8}):0{9};"
TAX = {"i1": WRONG, "i2": WRONG, "i3": TRUE, "c1": WRONG, "c2": WRONG,
       "o1": "d__A;p__P;c__C;o__O;f__F3;g__G3;s__S3"}


def jplace(path, placements, tree=TREE):
    doc = {"version": 3, "metadata": {}}
    if tree is not None:
        doc["tree"] = tree
    Path(path).write_text(json.dumps({**doc,
        "fields": ["like_weight_ratio", "edge_num", "distal_length", "pendant_length", "likelihood"],
        "placements": [{"p": [[lwr, edge, 0.01, 0.02, -100.0] for edge, lwr in rows], "n": [name]}
                       for name, rows in placements.items()]}))


class PlacementLocality(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "truth.json").write_text(json.dumps({
            "distance": "family", "k": 2, "seed": 1,
            "injected": {"i1": {"true": TRUE, "wrong": WRONG, "donor_group": TRUE},
                         "i2": {"true": TRUE, "wrong": WRONG, "donor_group": TRUE}}}))
        (self.tmp / "cell.tax").write_text("".join(f"{n}\t{l}\n" for n, l in TAX.items()))
        (self.tmp / "run.mis").write_text(
            HEADER + "\n" + f"i2\tFamily\tf__F2\tf__F1\t0.900\t{WRONG}\t{TRUE}\t0.9\t1.000\n")

    def run_it(self, placements):
        jplace(self.tmp / "p.jplace", placements)
        out = self.tmp / "loc.json"
        r = subprocess.run([sys.executable, str(BIN / "placement_locality.py"),
                            "--truth", str(self.tmp / "truth.json"), "--tax", str(self.tmp / "cell.tax"),
                            "--mis", str(self.tmp / "run.mis"), "--jplace", str(self.tmp / "p.jplace"),
                            "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(out.read_text())

    def test_the_best_edge_is_read_by_the_fields_order_and_lands_among_the_co_carrier(self):
        """i1 held out: most weight on edge 1, the branch above i2, its only co-carrier. With the
        fields order putting like_weight_ratio first, a parser that assumed edge_num first would
        read 0.7 as an edge number."""
        d = self.run_it({"i1": [(1, 0.7), (3, 0.3)]})
        row = next(x for x in d["rows"] if x["sequence"] == "i1")
        self.assertEqual(row["edge"], 1)
        self.assertEqual(row["lwr"], 0.7)
        self.assertEqual(row["leaves_below"], 1)
        self.assertTrue(row["among_co_carriers"])
        self.assertFalse(row["flagged"], "i1 is not in the .mis")
        self.assertEqual(d["summary"]["missed"]["among_co_carriers"], 1)

    def test_a_placement_outside_the_co_carriers_is_not_among_them(self):
        """i2 held out and placed on edge 7, the branch above F2's own members: that is where its
        wrong label says it belongs, and it is not among its co-carrier i1."""
        d = self.run_it({"i2": [(7, 0.9), (1, 0.1)]})
        row = next(x for x in d["rows"] if x["sequence"] == "i2")
        self.assertEqual(row["edge"], 7)
        self.assertFalse(row["among_co_carriers"])
        self.assertEqual(row["below_agree_with_wrong_to_rank"], 6, "c1 and c2 carry WRONG whole")
        self.assertEqual(row["below_agree_with_true_to_rank"], 3, "they agree with the truth to order")
        self.assertTrue(row["flagged"])
        self.assertEqual(d["summary"]["flagged"]["among_co_carriers"], 0)

    def test_an_edge_above_the_co_carrier_and_a_true_relative_still_counts(self):
        """Edge 2 spans i1 and i2: for i1 held out, below it is i2 only -- a co-carrier -- so among.
        Edge 4 spans i1, i2, i3: i3 is a true relative sharing the lineage below the family rank, so
        still among, which is the mechanism exactly: the placement sits with the group."""
        d = self.run_it({"i1": [(4, 1.0)]})
        row = d["rows"][0]
        self.assertEqual(sorted([row["co_carriers_below"], row["leaves_below"]]), [1, 2])
        self.assertTrue(row["among_co_carriers"])

    def test_sativa_r_prefix_on_tree_leaves_and_placed_names_is_stripped(self):
        # The real files carry r_ before every name, tree and placements alike; the first run on a
        # cell said "no injected sequence was placed" and read the tree's clades as unknown taxa.
        jplace(self.tmp / "p.jplace", {"r_i2": [(0, 1.0)]}, tree=TREE.replace("(", "(r_").replace(",", ",r_"))
        out = self.tmp / "loc.json"
        r = subprocess.run([sys.executable, str(BIN / "placement_locality.py"),
                            "--truth", str(self.tmp / "truth.json"), "--tax", str(self.tmp / "cell.tax"),
                            "--mis", str(self.tmp / "run.mis"), "--jplace", str(self.tmp / "p.jplace"),
                            "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(out.read_text())["rows"][0]
        self.assertEqual(row["sequence"], "i2")
        self.assertTrue(row["among_co_carriers"])

    def test_a_jplace_without_a_tree_needs_one_and_reads_it_from_a_refjson(self):
        # Upstream's leave-one-out jplace has no tree; its .refjson carries the labelled one.
        jplace(self.tmp / "p.jplace", {"i2": [(5, 1.0)]}, tree=None)
        (self.tmp / "run.refjson").write_text(json.dumps({"tree": TREE, "sequences": []}))
        cmd = [sys.executable, str(BIN / "placement_locality.py"),
               "--truth", str(self.tmp / "truth.json"), "--tax", str(self.tmp / "cell.tax"),
               "--mis", str(self.tmp / "run.mis"), "--jplace", str(self.tmp / "p.jplace"),
               "--out", str(self.tmp / "loc.json")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--tree", r.stderr)
        r = subprocess.run(cmd + ["--tree", str(self.tmp / "run.refjson")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads((self.tmp / "loc.json").read_text())["rows"][0]
        self.assertEqual(row["edge"], 5)
        self.assertFalse(row["among_co_carriers"])

    def test_a_leave_one_out_placement_on_the_sequence_own_edge_reads_the_clade_it_hung_from(self):
        # Edge 1 is i2's own pendant edge in the full tree: below it, nothing but i2. The clade it
        # hung from is (i1, i2), so the placement is among the co-carrier.
        out = self.run_it({"i2": [(1, 1.0)]})
        self.assertEqual(out["rows"][0]["leaves_below"], 1)
        self.assertTrue(out["rows"][0]["among_co_carriers"])

    def test_no_injected_sequence_placed_is_an_error(self):
        jplace(self.tmp / "p.jplace", {"o1": [(8, 1.0)]})
        r = subprocess.run([sys.executable, str(BIN / "placement_locality.py"),
                            "--truth", str(self.tmp / "truth.json"), "--tax", str(self.tmp / "cell.tax"),
                            "--mis", str(self.tmp / "run.mis"), "--jplace", str(self.tmp / "p.jplace")],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no injected sequence", r.stderr)


class PlacementComparison(unittest.TestCase):
    """bin/placement_comparison.py joins two locality records on the sequence and keeps the
    sequences one engine flagged and the other did not."""

    def test_deviating_rows_and_the_same_edge_count(self):
        tmp = Path(tempfile.mkdtemp())
        up = {"rows": [{"sequence": "i1", "flagged": False, "edge": 1, "lwr": 0.7,
                        "below_agree_with_wrong_to_rank": 6, "below_agree_with_true_to_rank": 3,
                        "among_co_carriers": True},
                       {"sequence": "i2", "flagged": True, "edge": 7, "lwr": 0.9,
                        "below_agree_with_wrong_to_rank": 6, "below_agree_with_true_to_rank": 3,
                        "among_co_carriers": False}]}
        fk = {"rows": [{"sequence": "i1", "flagged": True, "edge": 1, "lwr": 0.55,
                        "below_agree_with_wrong_to_rank": 6, "below_agree_with_true_to_rank": 3,
                        "among_co_carriers": True},
                       {"sequence": "i2", "flagged": True, "edge": 7, "lwr": 0.9,
                        "below_agree_with_wrong_to_rank": 6, "below_agree_with_true_to_rank": 3,
                        "among_co_carriers": False}]}
        (tmp / "up.json").write_text(json.dumps(up))
        (tmp / "fk.json").write_text(json.dumps(fk))
        r = subprocess.run([sys.executable, str(BIN / "placement_comparison.py"),
                            "--upstream", str(tmp / "up.json"), "--fork", str(tmp / "fk.json"),
                            "--out", str(tmp / "cmp.tsv")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 flagged by one only; of those, 1 sit on the same edge", r.stdout)
        rows = [l.split("\t") for l in (tmp / "cmp.tsv").read_text().splitlines()]
        self.assertEqual(rows[0][0], "sequence")
        i1 = next(x for x in rows[1:] if x[0] == "i1")
        self.assertEqual((i1[1], i1[2], i1[5]), ("False", "True", "True"), "same edge, one flag")


if __name__ == "__main__":
    unittest.main()
