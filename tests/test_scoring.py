#!/usr/bin/env python3
"""Tests for the scripts that turn runs into numbers.

Written against the defects this benchmark actually hit, not against a coverage target. Every case
below failed, or would have failed silently, at some point:

  a .mis with eight columns instead of nine, because the comparator has no exclusion column
  a name that does not join, which reported a rate of zero rather than an error
  a glob matching every condition at once, which mixed four of them into one table
  a lineage that trims to nothing, which crashed the tool two steps later

Plain unittest, no new dependency: the repo's analysis layer is standard library only and a test
suite is not a reason to change that.

  python3 -m unittest discover -s tests -v
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
TRUE = "d__A;p__B;c__C;o__O;f__F;g__G;s__S1"
WRONG = "d__A;p__B;c__C;o__O;f__Z;g__Z;s__Z1"


def mis_row(name, conf, excl, declared=WRONG, proposed=TRUE, level="Family"):
    fields = [name, level, declared.split(";")[4], proposed.split(";")[4], f"{conf:.3f}",
              declared, proposed, "0.9;0.9;0.9"]
    if excl is not None:
        fields.append(f"{excl:.3f}")
    return "\t".join(fields)


def run(script, *args):
    r = subprocess.run([sys.executable, str(BIN / script), *map(str, args)],
                       capture_output=True, text=True)
    return r


class ScoreInjection(unittest.TestCase):
    """score_injection.py produces every recall number the paper reports."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.truth = self.tmp / "t.truth.json"
        self.truth.write_text(json.dumps({
            "distance": "family", "rate": 0.01, "k": 2, "seed": 1, "n_total": 10,
            "injected": {n: {"true": TRUE, "wrong": WRONG} for n in ("i1", "i2", "i3", "i4")},
        }))

    def write_mis(self, rows):
        p = self.tmp / "run.mis"
        p.write_text(HEADER + "\n" + "\n".join(rows) + "\n")
        return p

    def score(self, mis, *extra):
        out = self.tmp / "score.json"
        r = run("score_injection.py", "--truth", self.truth, "--mis", mis, "--out", out, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(out.read_text())

    def at(self, d, threshold, metric="by_confidence"):
        return next(r for r in d[metric] if r["threshold"] == threshold)

    def test_recall_counts_only_injected_sequences(self):
        d = self.score(self.write_mis([mis_row("i1", 0.9, 1.0), mis_row("i2", 0.9, 1.0),
                                       mis_row("other", 0.9, 1.0)]))
        self.assertEqual(self.at(d, 0.0)["recall"], 0.5, "two of four injected are flagged")
        self.assertEqual(self.at(d, 0.0)["flags_on_non_injected"], 1)

    def test_threshold_excludes_rows_below_it(self):
        d = self.score(self.write_mis([mis_row("i1", 0.95, 1.0), mis_row("i2", 0.50, 1.0)]))
        self.assertEqual(self.at(d, 0.0)["recall"], 0.5)
        self.assertEqual(self.at(d, 0.9)["recall"], 0.25, "the 0.50 row drops out")

    def test_eight_column_mis_has_no_exclusion_curve(self):
        """The comparator emits eight columns. Reading a ninth that is not there must not invent one
        or drop the row: it was a None that had to flow through every threshold."""
        d = self.score(self.write_mis([mis_row("i1", 0.9, None), mis_row("i2", 0.9, None)]))
        self.assertFalse(d["has_exclusion_column"])
        self.assertIsNone(d["by_exclusion"])
        self.assertEqual(self.at(d, 0.0)["recall"], 0.5, "recall still works without the column")

    def test_no_flags_at_all_is_zero_not_absent(self):
        d = self.score(self.write_mis([]))
        self.assertEqual(self.at(d, 0.0)["recall"], 0.0)
        self.assertEqual(self.at(d, 0.0)["flags_on_non_injected"], 0)

    def test_names_that_do_not_join_give_zero_recall_and_say_so_in_the_counts(self):
        """The silent-zero class. A name mismatch cannot be distinguished from genuine non-detection
        by recall alone, so the test pins what the other fields show: flags exist, none are injected."""
        d = self.score(self.write_mis([mis_row("r_i1", 0.9, 1.0), mis_row("r_i2", 0.9, 1.0)]))
        self.assertEqual(self.at(d, 0.0)["recall"], 0.0)
        self.assertEqual(self.at(d, 0.0)["flags_on_non_injected"], 2,
                         "two flags that joined to nothing, which is the signature to look for")


class VerifyInjection(unittest.TestCase):
    """verify_injection.py must fail on a tampered cell, or it is not a check."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "base.tax"
        self.base.write_text("".join(f"s{i}\t{TRUE}\n" for i in range(6)))
        self.cell = self.tmp / "inj" / "c1"
        self.cell.mkdir(parents=True)

    def write_cell(self, tax_lines, injected):
        (self.cell / "c1.tax").write_text("".join(tax_lines))
        (self.cell / "c1.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.1, "k": 1, "seed": 1,
            "injected": injected}))

    def verify(self):
        return run("verify_injection.py", "--base", self.base,
                   "--injected-dir", self.tmp / "inj")

    def test_a_sound_cell_passes(self):
        lines = [f"s{i}\t{WRONG if i == 0 else TRUE}\n" for i in range(6)]
        self.write_cell(lines, {"s0": {"true": TRUE, "wrong": WRONG}})
        r = self.verify()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 cells checked, 1 sound", r.stdout)

    def test_an_undeclared_change_is_caught(self):
        lines = [f"s{i}\t{WRONG if i in (0, 1) else TRUE}\n" for i in range(6)]
        self.write_cell(lines, {"s0": {"true": TRUE, "wrong": WRONG}})
        self.assertNotEqual(self.verify().returncode, 0,
                            "s1 was changed without being declared")

    def test_a_missing_sequence_is_caught(self):
        lines = [f"s{i}\t{WRONG if i == 0 else TRUE}\n" for i in range(5)]
        self.write_cell(lines, {"s0": {"true": TRUE, "wrong": WRONG}})
        self.assertNotEqual(self.verify().returncode, 0, "the cell has five entries, the base six")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ColumnComparison(unittest.TestCase):
    """column_comparison.py divided by the number of flags at the stem confidence without
    checking there were any. On this grid 31.5 % of flags sit there, so it never bit; on a
    dataset where the stem split never fires it would have raised ZeroDivisionError."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        cell = self.tmp / "inj" / "c1"
        cell.mkdir(parents=True)
        (cell / "c1.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.1, "k": 1, "seed": 1,
            "injected": {"i1": {"true": TRUE, "wrong": WRONG}}}))
        self.runs = self.tmp / "runs"
        d = self.runs / "c1__cond"
        d.mkdir(parents=True)
        self.mis = d / "c1__cond.mis"

    def run_it(self):
        return run("column_comparison.py", "--injected-dir", self.tmp / "inj",
                   "--runs-dir", self.runs, "--condition", "cond")

    def test_no_flag_at_the_stem_confidence_reports_none(self):
        self.mis.write_text(HEADER + "\n" + mis_row("i1", 0.900, 1.0) + "\n")
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("none", r.stdout)

    def test_a_flag_at_the_stem_confidence_is_still_reported(self):
        self.mis.write_text(HEADER + "\n" + mis_row("i1", 0.510, 1.0) + "\n")
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("100.0%", r.stdout)


class BinomialTail(unittest.TestCase):
    """bin/conflict_enrichment.py's tail, which carries the enrichment p-values.

    Checked against exact rational arithmetic rather than against another approximation, and
    including the two degenerate rates, one of which used to return 1.0 where the answer is 0.
    """

    @staticmethod
    def _tail():
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "bin" / "conflict_enrichment.py"
        spec = importlib.util.spec_from_file_location("conflict_enrichment", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.tail_ge

    @staticmethod
    def _exact(k, n, p):
        from fractions import Fraction
        from math import comb
        q = Fraction(p).limit_denominator(10 ** 6)
        return float(sum(comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(k, n + 1)))

    def test_matches_exact_arithmetic(self):
        tail = self._tail()
        for k, n, p in [(3, 10, 0.5), (8, 51, 0.037), (25, 350, 0.038), (1, 200, 0.01)]:
            self.assertAlmostEqual(tail(k, n, p), self._exact(k, n, p), places=9,
                                   msg=f"tail_ge({k}, {n}, {p})")

    def test_edges(self):
        tail = self._tail()
        self.assertEqual(tail(0, 10, 0.5), 1.0)
        self.assertEqual(tail(11, 10, 0.5), 0.0)
        self.assertEqual(tail(3, 10, 0.0), 0.0)
        self.assertEqual(tail(3, 10, 1.0), 1.0)

    def test_large_n_does_not_overflow(self):
        """n = 6531 is the unflagged group, where the comb() form overflowed on the first run."""
        self.assertLess(self._tail()(250, 6531, 0.0376), 1.0000001)
