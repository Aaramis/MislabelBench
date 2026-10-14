#!/usr/bin/env python3
"""Tests for the .mis parsing that the main figure and the UpSet tables read their flags through,
and for the eligible pool of detection_law.py.

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
L1 = "d__A;p__B;c__C;o__O;f__F;g__G;s__S1"
L2 = "d__A;p__B;c__C;o__O;f__Z;g__Z;s__Z1"


def mis(names):
    """A .mis with a header line and a blank line, which is what the real files carry."""
    rows = [f"{n}\tFamily\tf__F\tf__Z\t0.900\t{L1}\t{L2}\t0.9;0.9;0.9\t1.000" for n in names]
    return HEADER + "\n" + "\n".join(rows) + "\n\n"


def run(script, *args):
    return subprocess.run([sys.executable, str(BIN / script), *map(str, args)],
                          capture_output=True, text=True)


class MisFlags(unittest.TestCase):
    """The comment/blank skip and the id column of mis_flags.flagged, which the main figure and the
    UpSet tables read their flags through. With `and` instead of `or` the `;SeqID` header line
    becomes a flag named ";SeqID", present in every file, and nothing else would notice."""

    def test_header_and_blank_lines_are_not_flags_and_the_key_is_the_id(self):
        sys.path.insert(0, str(BIN))
        import mis_flags
        path = Path(tempfile.mkdtemp()) / "x.mis"
        path.write_text(mis(["u1", "u2"]))
        self.assertEqual(mis_flags.flagged(path), {"u1": "Family", "u2": "Family"})
        self.assertEqual(mis_flags.flagged(path, 0.95), {})


class DetectionLawEligiblePool(unittest.TestCase):
    """eligible_taxa is the count of taxa that *could* host k injections, which needs k+1 members:
    k relabelled and one survivor. It is the number README's table uses to argue that k is not an
    independent variable, and a strict comparison there would undercount the pool by every taxon of
    exactly the minimum size -- which at k=1 is every pair in the base."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # One taxon with exactly k+1 = 3 members, one with 2, at k = 2.
        (self.tmp / "base.tax").write_text(
            "".join(f"a{i}\t{L1}\n" for i in range(3)) + "".join(f"b{i}\t{L2}\n" for i in range(2)))
        cell = self.tmp / "inj" / "c1"
        cell.mkdir(parents=True)
        (cell / "c1.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.1, "k": 2, "seed": 1,
            "injected": {n: {"true": L1, "wrong": L2} for n in ("a0", "a1")}}))
        d = self.tmp / "runs" / "c1__cond"
        d.mkdir(parents=True)
        (d / "c1__cond.mis").write_text(mis(["a0"]))
        self.out = self.tmp / "dl.json"

    def test_a_taxon_of_exactly_k_plus_one_members_is_eligible(self):
        r = run("detection_law.py", "--base-tax", self.tmp / "base.tax",
                "--injected-dir", self.tmp / "inj", "--runs-dir", self.tmp / "runs",
                "--condition", "cond", "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = next(x for x in json.loads(self.out.read_text())["by_k"] if x["k"] == 2)
        self.assertEqual(row["eligible_taxa"], 1, "the three-member taxon, not the two-member one")
        self.assertEqual(row["injected"], 2)
        self.assertEqual(row["detected"], 1, "a0 is flagged, a1 is not")


if __name__ == "__main__":
    unittest.main(verbosity=2)
