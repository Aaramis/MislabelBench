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
    # The label columns hold the family, which is rank 4 -- except for a proposal that stops above
    # family, where the deepest rank it has is the one the tool would have named.
    def label(path):
        parts = path.split(";")
        return parts[4] if len(parts) > 4 else parts[-1]

    fields = [name, level, label(declared), label(proposed), f"{conf:.3f}",
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

    def test_added_vs_baseline_subtracts_the_baseline_and_not_the_other_way(self):
        """`added_vs_baseline` is published, and until this test nothing exercised the flag at all.

        A mutation sweep flipped `len(others - baseline)` to `len(others + baseline)`, which is a
        TypeError on two sets, and the suite passed: no test had ever passed --baseline-mis. The
        numbers here are chosen so the two directions differ -- one collateral flag is in the
        baseline and one is not, so the answer is 1 and never 2 or 3.
        """
        base = self.tmp / "base.mis"
        base.write_text(HEADER + "\n" + mis_row("old", 0.9, 1.0) + "\n")
        d = self.score(self.write_mis([mis_row("i1", 0.9, 1.0), mis_row("old", 0.9, 1.0),
                                       mis_row("new", 0.9, 1.0)]), "--baseline-mis", base)
        row = self.at(d, 0.0)
        self.assertEqual(row["flags_on_non_injected"], 2, "old and new")
        self.assertEqual(row["added_vs_baseline"], 1, "new only")
        self.assertEqual(d["baseline_flags"], 1)

    def test_an_empty_baseline_is_an_answer_and_not_a_missing_one(self):
        """A database the tool flags nothing in is a real baseline, and the field used to report
        null for it while `baseline_flags: 0` sat two lines above. Recovered 144 null values in the
        simulated summaries when it was fixed, so it is pinned here."""
        base = self.tmp / "empty.mis"
        base.write_text(HEADER + "\n")
        d = self.score(self.write_mis([mis_row("a", 0.9, 1.0), mis_row("b", 0.9, 1.0)]),
                       "--baseline-mis", base)
        self.assertEqual(d["baseline_flags"], 0)
        self.assertEqual(self.at(d, 0.0)["added_vs_baseline"], 2)

    def test_without_a_baseline_the_field_is_absent_rather_than_zero(self):
        d = self.score(self.write_mis([mis_row("a", 0.9, 1.0)]))
        self.assertIsNone(self.at(d, 0.0)["added_vs_baseline"])
        self.assertIsNone(d["baseline_flags"])

    def test_a_proposal_that_is_a_prefix_lands_at_the_shorter_depth(self):
        """mismatch_rank's fallback, for a proposed path that agrees everywhere it exists.

        It is reached whenever the tool proposes a lineage shorter than the declared one, and it
        feeds recall_at_injected_rank. `min` to `max` survived the sweep because nothing came down
        this branch. The proposal here agrees on all four ranks it has, so the shorter length is 4,
        which is exactly the family index this cell injected at: `min` counts the row at rank and
        `max` would return 7 and not count it. One sequence of four, so 0.25 either way for recall
        and 0.25 against 0.0 for the rank metric.
        """
        short = "d__A;p__B;c__C;o__O"
        d = self.score(self.write_mis([mis_row("i1", 0.9, 1.0, declared=WRONG, proposed=short)]))
        self.assertEqual(self.at(d, 0.0)["recall"], 0.25)
        self.assertEqual(self.at(d, 0.0)["recall_at_injected_rank"], 0.25)

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

    def test_the_sound_count_is_the_cells_minus_the_problems(self):
        """Two cells, one tampered: the line has to read 2 checked and 1 sound.

        The existing cases all have either no problem or one cell, where `checked - len(problems)`
        and `checked + len(problems)` agree. This is the gate's own summary, read by whoever runs
        bin/analyses.sh, and a gate that miscounts what it passed is worse than no gate.
        """
        lines = [f"s{i}\t{WRONG if i == 0 else TRUE}\n" for i in range(6)]
        self.write_cell(lines, {"s0": {"true": TRUE, "wrong": WRONG}})
        bad = self.tmp / "inj" / "c2"
        bad.mkdir(parents=True)
        (bad / "c2.tax").write_text("".join(
            f"s{i}\t{WRONG if i in (0, 1) else TRUE}\n" for i in range(6)))
        (bad / "c2.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.1, "k": 1, "seed": 1,
            "injected": {"s0": {"true": TRUE, "wrong": WRONG}}}))
        r = self.verify()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("2 cells checked, 1 sound", r.stdout)
        self.assertIn("1 cells failed", r.stderr)

    def test_a_missing_sequence_is_caught(self):
        lines = [f"s{i}\t{WRONG if i == 0 else TRUE}\n" for i in range(5)]
        self.write_cell(lines, {"s0": {"true": TRUE, "wrong": WRONG}})
        self.assertNotEqual(self.verify().returncode, 0, "the cell has five entries, the base six")


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


class ColumnComparisonCurves(unittest.TestCase):
    """The two curves and the stem table, on seven flags whose every number is countable by hand.

    The class above checks that the script survives a grid with no stem flag, which was a real
    ZeroDivisionError. It does not touch the curves, the floors, the matched-budget row or the
    exclusion thresholds -- so a mutation sweep killed 7 of 15, and among the survivors were the
    `>= 0.99` that produces the share README quotes, the `min` that picks the matched budget, and the
    `max` that reads the best point off it. Those are the script's output.

    The fixture is built so that the two columns disagree: the confidence column can be pushed to
    zero calls on untouched sequences, the exclusion column bottoms out at two, which is the
    saturation the whole comparison exists to show.
    """

    #       name  injected  confidence  exclusion
    ROWS = [("i1", True, 0.510, 0.990),
            ("i2", True, 0.900, 0.500),
            ("i3", True, 0.800, 0.600),
            ("u1", False, 0.510, 0.980),
            ("u2", False, 0.700, 1.000),
            ("u3", False, 0.600, 0.990),
            ("u4", False, 0.510, 1.000)]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        cell = self.tmp / "inj" / "c1"
        cell.mkdir(parents=True)
        (cell / "c1.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.1, "k": 1, "seed": 1,
            "injected": {n: {"true": TRUE, "wrong": WRONG}
                         for n, inj, _, _ in self.ROWS if inj}}))
        runs = self.tmp / "runs"
        d = runs / "c1__cond"
        d.mkdir(parents=True)
        (d / "c1__cond.mis").write_text(
            HEADER + "\n" + "\n".join(mis_row(n, c, e) for n, _, c, e in self.ROWS) + "\n")
        self.out = self.tmp / "cols.json"
        self.r = run("column_comparison.py", "--injected-dir", self.tmp / "inj",
                     "--runs-dir", runs, "--condition", "cond", "--out", self.out)
        self.assertEqual(self.r.returncode, 0, self.r.stderr)
        self.doc = json.loads(self.out.read_text())

    def test_the_curves_are_cumulative_from_the_threshold_up(self):
        self.assertEqual(self.doc["n_flags"], 7)
        self.assertEqual(self.doc["n_injected_flags"], 3)
        self.assertEqual(
            [(p["threshold"], p["injected_kept"], p["untouched_kept"])
             for p in self.doc["curves"]["confidence"]],
            [(0.510, 3, 4), (0.600, 2, 2), (0.700, 2, 1), (0.800, 2, 0), (0.900, 1, 0)])
        self.assertEqual(
            [(p["threshold"], p["injected_kept"], p["untouched_kept"])
             for p in self.doc["curves"]["exclusion"]],
            [(0.500, 3, 4), (0.600, 2, 4), (0.980, 1, 4), (0.990, 1, 3), (1.000, 0, 2)])

    def test_the_floor_is_the_lowest_reachable_call_count_per_column(self):
        self.assertEqual(self.doc["untouched_floor"], {"confidence": 0, "exclusion": 2})

    def test_the_matched_budget_is_the_higher_floor_and_takes_the_best_point_in_it(self):
        """The budget has to be the larger of the two floors, or the saturated column cannot reach
        it at all, and within the budget the informative point is the one keeping the most injected
        flags. Here the budget is 2: confidence keeps 2 injected flags there and exclusion keeps 0.
        """
        line = next(l for l in self.r.stdout.splitlines() if l.strip().startswith("budget"))
        self.assertIn("budget      2", line)
        self.assertRegex(line, r"confidence\s+2\b")
        self.assertRegex(line, r"exclusion\s+0\b")

    def test_the_exclusion_threshold_counts_the_boundary_itself(self):
        """0.99 exactly is in, and two of the fixture's rows sit on it. README quotes this share as
        the reason the exclusion floor is where it is, so off by one row is off in print."""
        self.assertEqual(self.doc["flags_exclusion_ge_099"], 4, "0.990, 0.990, 1.000, 1.000")
        self.assertEqual(self.doc["stem_flags"], 3, "three flags at confidence 0.510")
        self.assertEqual(self.doc["stem_exclusion_ge_099"], 2, "0.990 and 1.000 among those three")
        self.assertEqual(self.doc["stem_injected"], 1)


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


class ColumnComparisonFloor(unittest.TestCase):
    """untouched_floor is the minimum over the curve, not the value at any particular threshold.

    The paper's one sentence about the exclusion column is read off this field, and it was published
    once as "at a 0.99 threshold" when the floor is reached at 1.0 -- on the real grid, exclusion
    keeps 97.5 % of the collateral flags at its floor and 99.1 % at 0.99. The fixture below makes the
    two answers different on purpose: one collateral flag sits at exactly 0.99 and is kept there and
    dropped at 1.0, so a reading that confused the two would return 2 where the floor is 1.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        cell = self.tmp / "inj" / "c1"
        cell.mkdir(parents=True)
        (cell / "c1.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.01, "k": 1, "seed": 1, "n_total": 10,
            "injected": {"i1": {"true": TRUE, "wrong": WRONG}},
        }))
        run_dir = self.tmp / "runs" / "c1__cond__rep1"
        run_dir.mkdir(parents=True)
        (run_dir / "c1__cond__rep1.mis").write_text(HEADER + "\n" + "\n".join([
            mis_row("i1", 0.995, 0.995),
            mis_row("u1", 0.990, 0.990),   # kept at 0.99, dropped at 1.0
            mis_row("u2", 1.000, 1.000),   # kept at both
            mis_row("u3", 0.500, 0.500),   # dropped at both
        ]) + "\n")

    def test_floor_is_the_minimum_of_the_curve_and_not_the_value_at_099(self):
        out = self.tmp / "cc.json"
        r = run("column_comparison.py", "--injected-dir", self.tmp / "inj",
                "--runs-dir", self.tmp / "runs", "--condition", "cond__rep1", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(out.read_text())
        for column in ("confidence", "exclusion"):
            curve = d["curves"][column]
            at_099 = next(p for p in curve if p["threshold"] == 0.99)
            self.assertEqual(at_099["untouched_kept"], 2, f"{column} at 0.99")
            self.assertEqual(d["untouched_floor"][column], 1, f"{column} floor")
            self.assertEqual(d["untouched_floor"][column],
                             min(p["untouched_kept"] for p in curve))


class ThresholdBoundaries(unittest.TestCase):
    """A row whose value is exactly the threshold is kept.

    Both scripts compare with >= against thresholds drawn from the observed values themselves, so
    the boundary row is not an edge case here, it is the common case: every point of the exclusion
    curve is placed at a value some row carries. A mutation sweep turned both comparisons strict and
    no test noticed, because the fixtures used 0.95 and 0.50 against a threshold of 0.9. These use
    0.90 and 0.99, which are two of the published thresholds, and 31.3 % of the real flags sit on a
    single confidence value, so a strict comparison would move a published recall by a third.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.truth = self.tmp / "t.truth.json"
        self.truth.write_text(json.dumps({
            "distance": "family", "rate": 0.01, "k": 1, "seed": 1, "n_total": 10,
            "injected": {n: {"true": TRUE, "wrong": WRONG} for n in ("i1", "i2")},
        }))
        self.mis = self.tmp / "run.mis"
        self.mis.write_text(HEADER + "\n" + "\n".join([
            mis_row("i1", 0.900, 0.990),   # exactly on two published thresholds
            mis_row("i2", 0.899, 0.989),   # just below both
        ]) + "\n")

    def test_score_injection_keeps_the_row_sitting_on_the_threshold(self):
        out = self.tmp / "s.json"
        r = run("score_injection.py", "--truth", self.truth, "--mis", self.mis, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(out.read_text())
        conf = {x["threshold"]: x["recall"] for x in d["by_confidence"]}
        excl = {x["threshold"]: x["recall"] for x in d["by_exclusion"]}
        self.assertEqual(conf[0.9], 0.5, "i1 is at 0.900 and counts at a 0.9 threshold")
        self.assertEqual(conf[0.95], 0.0, "both rows are below 0.95")
        self.assertEqual(excl[0.99], 0.5, "i1 is at 0.990 and counts at a 0.99 threshold")

    def test_column_comparison_curve_and_budget_include_their_own_boundary(self):
        """injected_kept uses >= on the threshold, and the budget comparison uses <= on the count of
        calls on untouched sequences. The fixture puts one untouched flag at each value so the two
        boundaries are separately visible: at a budget of exactly 1 the 0.9 point is eligible."""
        inj = self.tmp / "inj" / "c1"
        inj.mkdir(parents=True)
        (inj / "c1.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.01, "k": 1, "seed": 1, "n_total": 10,
            "injected": {"i1": {"true": TRUE, "wrong": WRONG}}}))
        d = self.tmp / "runs" / "c1__cond"
        d.mkdir(parents=True)
        (d / "c1__cond.mis").write_text(HEADER + "\n" + "\n".join([
            mis_row("i1", 0.900, 0.900),
            mis_row("u1", 0.900, 0.900),
            mis_row("u2", 0.500, 0.500),
        ]) + "\n")
        out = self.tmp / "cc.json"
        r = run("column_comparison.py", "--injected-dir", self.tmp / "inj",
                "--runs-dir", self.tmp / "runs", "--condition", "cond", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        curve = json.loads(out.read_text())["curves"]["confidence"]
        at_09 = next(p for p in curve if p["threshold"] == 0.9)
        self.assertEqual(at_09["injected_kept"], 1, "i1 is at exactly 0.900")
        self.assertEqual(at_09["untouched_kept"], 1, "u1 is at exactly 0.900")
        self.assertIn("budget      1:", r.stdout)
        self.assertIn("confidence     1", r.stdout.split("budget      1:")[1].splitlines()[0],
                      "the 0.9 point costs exactly the budget, so it is reachable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
