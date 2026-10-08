#!/usr/bin/env python3
"""bin/detection_law.py, which carries the paper's mechanistic claim and almost nothing pinned it.

The claim is that recall on a shared mislabel is governed by what the removed sequence is placed
against: of the relatives that survive its removal, k-1 carry the wrong label and the rest carry the
right one, and that ratio predicts detection. If it does, the limit belongs to leave-one-out and not
to this implementation, which is why K=5 and K=25 find the same sequences.

A mutation sweep over the script killed **1 of 13** mutants against the existing suite, which only
checked that it runs. The survivors were not cosmetic: `k - 1` became `k + 1`, `group_size - k` became
`group_size + k`, and the clamp `min(..., bins - 1)` became `max(...)`. Each one re-bins every injected
sequence in the published table, and the table would still have looked like a law.

The fixture here is small enough that every number below is arithmetic a reader can redo: one donor
group of six, one of three, one of a single sequence.

    python3 tests/mutation_sweep.py bin/detection_law.py tests.test_detection_law
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

BIG = "d__A;p__B;c__C;o__O;f__F;g__G;s__BIG"        # six members
MID = "d__A;p__B;c__C;o__O;f__F;g__G;s__MID"        # three
LONE = "d__A;p__B;c__C;o__O;f__F;g__G;s__LONE"      # one
WRONG = "d__A;p__B;c__C;o__O;f__F;g__G;s__ELSE"
COND = "cond__rep1"


class DetectionLaw(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "base.tax"
        rows = ([(f"big{i}", BIG) for i in range(6)]
                + [(f"mid{i}", MID) for i in range(3)]
                + [("lone0", LONE)])
        self.base.write_text("".join(f"{n}\t{l}\n" for n, l in rows))
        self.inj = self.tmp / "inj"
        self.runs = self.tmp / "runs"

    def cell(self, name, k, donor, members, flagged, condition=COND):
        """One injected cell and the run that found `flagged` of its injected sequences."""
        d = self.inj / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.truth.json").write_text(json.dumps({
            "distance": "species", "rate": 0.1, "k": k, "seed": 1,
            "injected": {m: {"true": donor, "wrong": WRONG, "donor_group": donor}
                         for m in members}}))
        run = self.runs / f"{name}__{condition}"
        run.mkdir(parents=True, exist_ok=True)
        rows = [f"{m}\tSpecies\ts__BIG\ts__ELSE\t0.900\t{WRONG}\t{donor}\t0.9;0.9;0.9\t1.000"
                for m in flagged]
        (run / f"{name}__{condition}.mis").write_text(HEADER + "\n" + "\n".join(rows) + "\n")

    def law(self, *extra):
        out = self.tmp / "law.json"
        r = subprocess.run([sys.executable, str(BIN / "detection_law.py"),
                            "--base-tax", str(self.base), "--injected-dir", str(self.inj),
                            "--runs-dir", str(self.runs), "--condition", COND,
                            "--out", str(out), *extra], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(out.read_text()), r.stdout

    def ratio_row(self, doc, low):
        return next(r for r in doc["by_ratio"] if r["low"] == low)

    def test_the_ratio_is_k_minus_one_over_the_survivors(self):
        """Three cells on the group of six, hand-computed.

        k=1: no wrong relative survives, 5 right, ratio 0.0  -> the 0.0-0.2 bin
        k=2: 1 wrong, 4 right, ratio 0.2                     -> the 0.2-0.4 bin
        k=5: 4 wrong, 1 right, ratio 0.8                      -> the 0.8-1.0 bin

        `k + 1` instead of `k - 1` puts the first cell at 2/7 and the third at 6/-1; `group_size + k`
        puts them at 0/7 and 4/11. Either way the law is drawn from a different table.
        """
        self.cell("c_k1", 1, BIG, ["big0"], ["big0"])
        self.cell("c_k2", 2, BIG, ["big1", "big2"], ["big1"])
        self.cell("c_k5", 5, BIG, [f"big{i}" for i in range(5)], [])
        doc, stdout = self.law()
        self.assertEqual([r["low"] for r in doc["by_ratio"]], [0.0, 0.2, 0.8])
        # The printed bands too, which are what a reader of the log sees and which the JSON's own
        # `high` field cannot vouch for: they are computed a second time in the print.
        self.assertIn("0.0-0.2", stdout)
        self.assertIn("0.2-0.4", stdout)
        self.assertIn("0.8-1.0", stdout)
        self.assertEqual(self.ratio_row(doc, 0.0), {"low": 0.0, "high": 0.2, "detected": 1,
                                                    "injected": 1, "recall": 1.0})
        self.assertEqual(self.ratio_row(doc, 0.2), {"low": 0.2, "high": 0.4, "detected": 1,
                                                    "injected": 2, "recall": 0.5})
        self.assertEqual(self.ratio_row(doc, 0.8), {"low": 0.8, "high": 1.0, "detected": 0,
                                                    "injected": 5, "recall": 0.0})

    def test_a_ratio_of_one_lands_in_the_last_bin_and_not_past_it(self):
        """k equal to the whole group, which --allow-empty-donor permits: 5 wrong, 0 right, ratio 1.0.

        int(1.0 * 5) is 5 and there are five bins numbered 0 to 4, so the clamp is what keeps the row
        in the table at all. With `max` instead of `min` the index is 5, the row is tallied into a
        bucket no loop prints, and the two tables stop agreeing -- which the script's own last check
        reports but which nothing asserted.
        """
        self.cell("c_all", 6, BIG, [f"big{i}" for i in range(6)], ["big0", "big1"])
        doc, stdout = self.law()
        self.assertEqual(self.ratio_row(doc, 0.8), {"low": 0.8, "high": 1.0, "detected": 2,
                                                    "injected": 6, "recall": 0.3333})
        self.assertNotIn("fell outside", stdout)

    def test_a_group_of_one_has_no_surviving_relative_and_is_dropped(self):
        """wrong + right == 0: nothing to be placed against, so the sequence is not evidence either
        way. It must leave both tables rather than divide by zero or count as a miss."""
        self.cell("c_lone", 1, LONE, ["lone0"], [])
        self.cell("c_mid", 1, MID, ["mid0"], ["mid0"])
        doc, _ = self.law()
        self.assertEqual([r["k"] for r in doc["by_k"]], [1])
        self.assertEqual(doc["by_k"][0]["injected"], 1, "the lone sequence is gone")
        self.assertEqual(doc["by_k"][0]["detected"], 1)

    def test_the_k_table_counts_groups_sizes_and_the_pool_it_drew_from(self):
        """`eligible_taxa` is the count the README's table of pool shrinkage rests on: a taxon can
        host k injections only with k+1 members. Base here is 6 + 3 + 1, so k=1 has two eligible
        taxa and k=5 has one."""
        self.cell("c_k1", 1, BIG, ["big0"], ["big0"])
        self.cell("c_k1b", 1, MID, ["mid0"], [])
        self.cell("c_k5", 5, BIG, [f"big{i}" for i in range(5)], ["big0"])
        doc, _ = self.law()
        one = next(r for r in doc["by_k"] if r["k"] == 1)
        five = next(r for r in doc["by_k"] if r["k"] == 5)
        self.assertEqual(one["injected"], 2)
        self.assertEqual(one["donor_groups"], 2)
        self.assertEqual(one["distinct_donor_taxa"], 2)
        self.assertEqual(one["median_group_size"], 4.5, "six and three, per sequence")
        self.assertEqual(one["mean_share_relabelled"], 0.25, "mean of 1/6 and 1/3")
        self.assertEqual(one["eligible_taxa"], 2, "the group of one cannot host k=1")
        self.assertEqual(five["donor_groups"], 1)
        self.assertEqual(five["eligible_taxa"], 1, "only the group of six has six members")

    def test_also_present_restricts_the_cells_and_changes_the_answer(self):
        """The flag exists because comparing a curve over 180 cells with one over 99 compares the
        cell sets as much as the tools. It has to actually drop cells."""
        self.cell("c_both", 2, BIG, ["big0", "big1"], ["big0"])
        self.cell("c_both", 2, BIG, ["big0", "big1"], ["big0"], condition="other__rep1")
        self.cell("c_only", 2, MID, ["mid0", "mid1"], [])
        full, _ = self.law()
        self.assertEqual(sum(r["injected"] for r in full["by_k"]), 4)
        restricted, _ = self.law("--also-present", "other__rep1")
        self.assertEqual(sum(r["injected"] for r in restricted["by_k"]), 2)
        self.assertEqual(restricted["by_k"][0]["detected"], 1)


if __name__ == "__main__":
    unittest.main()
