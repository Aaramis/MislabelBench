#!/usr/bin/env python3
"""Tests that a cut-down case is the same problem as the run it is cut from.

The case built by bin/minimal_case.py is what gets sent to someone else, so two things have to hold
that reading the code cannot establish. At full count the case must reproduce the cell exactly, or a
negative result means nothing: it would be a different experiment. And the selection must not depend
on a draw, because the case is found by shrinking and each step has to differ from the last by the
sequences it drops and by nothing else.

The count below the target's own group is rejected rather than quietly satisfied. One wrong label is
found by both tools everywhere it has been tried, so a case that dropped the companion would look
like a case that reproduces nothing.

  python3 -m unittest discover -s tests -v
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"
ORDER = "d__A;p__P;c__C;o__O"
OUT_ORDER = "d__A;p__P;c__C;o__Q"
TARGET = "s1"
# Two families in the order under test, one outside it. The target and s2 share a species, which is
# what makes them one group: inject_mislabels.py relabels a group together, and k is its size.
TAX = {
    "s1": f"{ORDER};f__F1;g__G1;s__S1",
    "s2": f"{ORDER};f__F1;g__G1;s__S1",
    "s3": f"{ORDER};f__F1;g__G1;s__S2",
    "s4": f"{ORDER};f__F2;g__G2;s__S3",
    "s5": f"{ORDER};f__F2;g__G2;s__S4",
    "s6": f"{OUT_ORDER};f__F3;g__G3;s__S5",
    "s7": f"{OUT_ORDER};f__F3;g__G3;s__S6",
}
WRONG = f"{ORDER};f__F2;g__G2;s__S3"
OTHER_WRONG = f"{ORDER};f__F1;g__G1;s__S2"
# s4 and s5 are relabelled into F1 as a second, unrelated injection, so --injected-count has
# something to add beyond the target's group.
INJECTED = {
    "s1": {"true": TAX["s1"], "wrong": WRONG},
    "s2": {"true": TAX["s2"], "wrong": WRONG},
    "s4": {"true": TAX["s4"], "wrong": OTHER_WRONG},
    "s5": {"true": TAX["s5"], "wrong": OTHER_WRONG},
}
# A column no sequence occupies, to check it is dropped.
SEQS = {n: ("ACGT" + "ACGT"[i % 4] + "-") for i, n in enumerate(TAX)}


def write_inputs(d):
    d = Path(d)
    (d / "aln.fasta").write_text("".join(f">{n}\n{s}\n" for n, s in SEQS.items()))
    (d / "tax.tsv").write_text("".join(f"{n}\t{l}\n" for n, l in TAX.items()))
    (d / "truth.json").write_text(json.dumps({"distance": "family", "k": 2, "injected": INJECTED}))
    return d


def build(d, *args):
    return subprocess.run([sys.executable, str(BIN / "minimal_case.py"),
                           "--alignment", str(Path(d) / "aln.fasta"),
                           "--taxonomy", str(Path(d) / "tax.tsv"),
                           "--sequence", TARGET, "--wrong-label", WRONG, *map(str, args)],
                          capture_output=True, text=True)


def read_tax(path):
    return dict(line.split("\t", 1) for line in Path(path).read_text().splitlines() if line.strip())


class MinimalCase(unittest.TestCase):
    def test_full_count_reproduces_the_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_inputs(tmp)
            r = build(d, "--truth", d / "truth.json", "--injected-count", 99,
                      "--keep-rank", "order", "--outgroup", 99, "--out", d / "case")
            self.assertEqual(r.returncode, 0, r.stderr)
            want = dict(TAX)
            want.update({n: rec["wrong"] for n, rec in INJECTED.items()})
            self.assertEqual(read_tax(d / "case" / "case.tax"), want)

    def test_default_relabels_the_group_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_inputs(tmp)
            r = build(d, "--truth", d / "truth.json", "--keep-rank", "order",
                      "--outgroup", 99, "--out", d / "case")
            self.assertEqual(r.returncode, 0, r.stderr)
            got = read_tax(d / "case" / "case.tax")
            self.assertEqual({n for n in got if got[n] != TAX[n]}, {"s1", "s2"})
            self.assertEqual(json.loads((d / "case" / "case.json").read_text())["n_wrong_labels"], 2)

    def test_a_count_below_the_group_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_inputs(tmp)
            r = build(d, "--truth", d / "truth.json", "--injected-count", 1,
                      "--keep-rank", "order", "--out", d / "case")
            self.assertEqual(r.returncode, 1)
            self.assertIn("below the target's own group", r.stderr)

    def test_the_selection_does_not_depend_on_a_draw(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_inputs(tmp)
            for name in ("a", "b"):
                self.assertEqual(build(d, "--keep-rank", "order", "--per-family", 2,
                                       "--outgroup", 1, "--out", d / name).returncode, 0)
            for fn in ("case.fasta", "case.tax"):
                self.assertEqual((d / "a" / fn).read_bytes(), (d / "b" / fn).read_bytes())

    def test_an_all_gap_column_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_inputs(tmp)
            self.assertEqual(build(d, "--keep-rank", "order", "--outgroup", 99,
                                   "--out", d / "case").returncode, 0)
            width = json.loads((d / "case" / "case.json").read_text())["alignment_width"]
            self.assertEqual(width, len(SEQS[TARGET]) - 1)

    def test_a_label_no_sequence_carries_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_inputs(tmp)
            r = subprocess.run([sys.executable, str(BIN / "minimal_case.py"),
                                "--alignment", str(d / "aln.fasta"),
                                "--taxonomy", str(d / "tax.tsv"), "--sequence", TARGET,
                                "--wrong-label", f"{ORDER};f__NOPE;g__NOPE;s__NOPE",
                                "--out", str(d / "case")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not a lineage", r.stderr)


if __name__ == "__main__":
    unittest.main()
