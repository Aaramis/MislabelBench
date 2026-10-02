#!/usr/bin/env python3
"""Tests that a script reads one condition and not every condition in the directory.

The runs directory holds one subdirectory per (cell, condition). While a single condition had been
run, globbing `*/*.mis` under it was correct. Once four fold orders and the comparator shared it, the
same glob silently mixed them: background_stability.py reported 772 cells where 180 existed, and the
committed table would have been replaced by an average over conditions that answer different
questions. These tests put two conditions in one directory and insist each script sees one.

The other half is the sign test in paired_conditions.py, which reads the same directory twice and is
the only statistic in the repo that compares conditions to each other.

  python3 -m unittest discover -s tests -v
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"
TRUE = "d__A;p__B;c__C;o__O;f__F;g__G;s__S1"
WRONG = "d__A;p__B;c__C;o__O;f__Z;g__Z;s__Z1"
HEADER = ";SeqID\tLevel\tOrig\tProp\tConfidence\tOrigPath\tPropPath\tPerRank\tExclusion"


def mis(names):
    rows = [HEADER]
    for n in names:
        rows.append("\t".join([n, "Family", "f__Z", "f__F", "0.900", WRONG, TRUE, "0.9", "1.000"]))
    return "\n".join(rows) + "\n"


def run(script, *args):
    return subprocess.run([sys.executable, str(BIN / script), *map(str, args)],
                          capture_output=True, text=True)


class Fixture(unittest.TestCase):
    """Two cells, two conditions, with deliberately different detections per condition."""

    # cell -> injected names;  (cell, condition) -> names flagged
    CELLS = {"c1": ["i1", "i2", "i3", "i4"], "c2": ["j1", "j2", "j3", "j4"]}
    FLAGS = {("c1", "A"): ["i1", "i2"],        ("c1", "B"): ["i1"],
             ("c2", "A"): ["j1", "j2", "j3"],  ("c2", "B"): ["j1", "j2", "j3", "j4"]}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.inj = self.tmp / "injected"
        self.runs = self.tmp / "runs"
        self.base_tax = self.tmp / "base.tax"
        names = [n for v in self.CELLS.values() for n in v] + ["x1", "x2"]
        self.base_tax.write_text("".join(f"{n}\t{TRUE}\n" for n in names))
        self.baseline = self.tmp / "baseline.mis"
        self.baseline.write_text(mis(["x1"]))

        for cell, injected in self.CELLS.items():
            d = self.inj / cell
            d.mkdir(parents=True)
            (d / f"{cell}.tax").write_text(
                "".join(f"{n}\t{WRONG if n in injected else TRUE}\n" for n in names))
            (d / f"{cell}.truth.json").write_text(json.dumps({
                "distance": "family", "rate": 0.1, "k": 2, "seed": 1,
                "injected": {n: {"true": TRUE, "wrong": WRONG} for n in injected}}))
        for (cell, cond), flagged in self.FLAGS.items():
            d = self.runs / f"{cell}__{cond}"
            d.mkdir(parents=True)
            (d / f"{cell}__{cond}.mis").write_text(mis(flagged))


class ConditionSelection(Fixture):

    def test_background_stability_counts_cells_once_per_condition(self):
        out = self.tmp / "bg.tsv"
        r = run("background_stability.py", "--baseline", self.baseline, "--runs", self.runs,
                "--injected-dir", self.inj, "--condition", "A", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 cells", r.stdout, "two cells exist per condition, not four")
        self.assertEqual(len(out.read_text().strip().splitlines()), 3, "a header and two rows")

    def test_condition_is_required_so_the_mixture_cannot_happen_by_default(self):
        r = run("background_stability.py", "--baseline", self.baseline, "--runs", self.runs,
                "--injected-dir", self.inj, "--out", self.tmp / "bg.tsv")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("condition", r.stderr.lower())

    def test_detection_law_sees_one_condition(self):
        out = self.tmp / "law.json"
        r = run("detection_law.py", "--base-tax", self.base_tax, "--injected-dir", self.inj,
                "--runs-dir", self.runs, "--condition", "A", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        total = sum(row["injected"] for row in json.loads(out.read_text())["by_k"])
        self.assertEqual(total, 8, "eight injected sequences across two cells, counted once")


class PairedComparison(Fixture):

    def test_sign_counts_follow_the_fixture(self):
        out = self.tmp / "paired.json"
        r = run("paired_conditions.py", "--injected-dir", self.inj, "--runs-dir", self.runs,
                "--a", "A", "--b", "B", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(out.read_text())["by_k"][0]
        # c1: A detects 2 of 4, B detects 1 -> B worse by 0.25.  c2: A 3 of 4, B 4 -> B better by 0.25.
        self.assertEqual(row["cells"], 2)
        self.assertEqual(row["cells_b_greater"], 1)
        self.assertAlmostEqual(row["mean_difference"], 0.0, places=6)

    def test_a_condition_that_is_not_there_fails_rather_than_returning_nothing(self):
        r = run("paired_conditions.py", "--injected-dir", self.inj, "--runs-dir", self.runs,
                "--a", "A", "--b", "missing")
        self.assertNotEqual(r.returncode, 0)

    def test_sign_test_is_two_sided_and_exact(self):
        sys.path.insert(0, str(BIN))
        from paired_conditions import sign_test
        self.assertAlmostEqual(sign_test(0, 10), 2 * 0.5 ** 10, places=12)
        self.assertEqual(sign_test(5, 10), 1.0)
        self.assertEqual(sign_test(0, 0), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
