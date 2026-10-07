#!/usr/bin/env python3
"""Tests for the .mis and FASTA parsing that three published numbers are read through.

A mutation sweep over the eight tested scripts (26 single-operator mutations, one at a time,
`python3 -m pytest tests` after each) left 16 mutants alive. Most were in docstrings and error
messages, but four sat in code that decides a published figure, and they survived because no test
reached the function at all:

  background_stability.py  the comment/blank skip, and which .mis column is the sequence id
  conflict_enrichment.py   the same skip, and which FASTA header token is the sequence name

Each of the four is killed by one assertion below. The skip mutants are the dangerous pair: with
`and` instead of `or` the `;SeqID` header line becomes a flag named ";SeqID", present in every
file, so it is retained in every cell and inflates the baseline by one with no error anywhere.

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


class BackgroundStability(unittest.TestCase):
    """retained/lost/gained, which answer Daniel's question about the baseline moving.

    The fixture makes the three columns different numbers on purpose: one flag survives injection,
    one disappears, one appears. A parse that keeps the header line, or that reads the level column
    as the id, gives the wrong answer on at least one of them.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "baseline.mis"
        self.base.write_text(mis(["u1", "u2", "i1"]))
        cell = self.tmp / "inj" / "c1"
        cell.mkdir(parents=True)
        (cell / "c1.truth.json").write_text(json.dumps({
            "distance": "family", "rate": 0.1, "k": 1, "seed": 1,
            "injected": {"i1": {"true": L1, "wrong": L2}}}))
        d = self.tmp / "runs" / "c1__cond"
        d.mkdir(parents=True)
        (d / "c1__cond.mis").write_text(mis(["u1", "u3", "i1"]))
        self.out = self.tmp / "bg.tsv"

    def test_one_retained_one_lost_one_gained(self):
        r = run("background_stability.py", "--baseline", self.base, "--runs", self.tmp / "runs",
                "--condition", "cond", "--injected-dir", self.tmp / "inj", "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        head, row = self.out.read_text().splitlines()[:2]
        got = dict(zip(head.split("\t"), row.split("\t")))
        self.assertEqual(got["baseline"], "2", "i1 is injected, so it leaves the baseline side")
        self.assertEqual(got["retained"], "1", "u1 only; a kept header line would make it two")
        self.assertEqual(got["lost"], "1", "u2")
        self.assertEqual(got["gained"], "1", "u3, and not i1, which was injected")

    def test_the_baseline_count_printed_excludes_nothing_silently(self):
        r = run("background_stability.py", "--baseline", self.base, "--runs", self.tmp / "runs",
                "--condition", "cond", "--injected-dir", self.tmp / "inj", "--out", self.out)
        self.assertIn("baseline of 3 flags", r.stdout,
                      "three rows in the baseline .mis, header and blank line not among them")


class ConflictEnrichment(unittest.TestCase):
    """The identical-sequence groups that carry two different lineages.

    Real alignment headers carry a description after the id, so the name is the first token and not
    the whole line nor the second token. Taking the second token makes every name fail to join the
    taxonomy, and the script then reports zero sequences in conflict rather than failing.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "aln.fa").write_text(
            ">s1 first sequence\nAAAA\n>s2 second sequence\nAAAA\n"
            ">s3 third sequence\nCCCC\n>s4 fourth sequence\nGGGG\n")
        (self.tmp / "tax.txt").write_text(
            f"s1\t{L1}\ns2\t{L2}\ns3\t{L1}\ns4\t{L1}\n")
        (self.tmp / "a.mis").write_text(mis(["s1"]))
        (self.tmp / "b.mis").write_text(mis(["s1", "s3"]))
        self.out = self.tmp / "ce.json"

    def result(self):
        r = run("conflict_enrichment.py", "--alignment", self.tmp / "aln.fa",
                "--taxonomy", self.tmp / "tax.txt", "--mis-a", self.tmp / "a.mis",
                "--mis-b", self.tmp / "b.mis", "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(self.out.read_text())

    def test_names_come_from_the_first_header_token(self):
        d = self.result()
        self.assertEqual(d["sequences"], 4)
        self.assertEqual(d["in_conflict"], 2,
                         "s1 and s2 are identical and carry different families")

    def test_group_sizes_do_not_include_the_header_line(self):
        groups = {g["group"]: g for g in self.result()["groups"]}
        self.assertEqual(groups["both"]["n"], 1, "s1 only")
        self.assertEqual(groups["b only"]["n"], 1, "s3 only")
        self.assertEqual(groups["neither"]["n"], 2, "s2 and s4")
        self.assertNotIn("a only", groups, "an empty group is skipped, not printed as zero")


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
