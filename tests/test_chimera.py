#!/usr/bin/env python3
"""Error kind 7's generator, gate and scoring, on a six-sequence alignment built by hand.

What cannot be wrong in silence: the breakpoint is a fraction of the ungapped length and lands on
an aligned column; the two parents differ exactly at the requested rank; the base is untouched;
the same seed gives the same file; and the gate refuses a chimera whose columns are not its
parents'. Scoring is checked on a .mis written by hand, where the proposal for one chimera sides
with parent B and the other with neither.

    python3 -m unittest tests.test_chimera
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
# Two families under one order, each with two genera of one species of one or two sequences.
TAX = {
    "a1": "d__A;p__P;c__C;o__O;f__F1;g__G1;s__S1",
    "a2": "d__A;p__P;c__C;o__O;f__F1;g__G1;s__S1",
    "b1": "d__A;p__P;c__C;o__O;f__F1;g__G2;s__S2",
    "c1": "d__A;p__P;c__C;o__O;f__F2;g__G3;s__S3",
    "c2": "d__A;p__P;c__C;o__O;f__F2;g__G3;s__S3",
    "d1": "d__A;p__P;c__C;o__O;f__F2;g__G4;s__S4",
}
# Twelve columns; a1 has gaps so the ungapped breakpoint and the column differ.
SEQ = {"a1": "AA--AAAA--AA", "a2": "AAAAAAAAAAAA", "b1": "CCCCCCCCCCCC",
       "c1": "GGGGGGGGGGGG", "c2": "GGGGGGGGGGGG", "d1": "TTTTTTTTTTTT"}


def run(script, *args):
    return subprocess.run([sys.executable, str(BIN / script), *map(str, args)],
                          capture_output=True, text=True)


class Chimera(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fa = self.tmp / "base.fasta"
        self.tax = self.tmp / "base.tax"
        self.fa.write_text("".join(f">{n}\n{SEQ[n]}\n" for n in SEQ))
        self.tax.write_text("".join(f"{n}\t{l}\n" for n, l in TAX.items()))

    def make(self, cell, distance="family", bp=0.5, n=2, seed=1):
        d = self.tmp / "cells" / cell
        d.mkdir(parents=True, exist_ok=True)
        r = run("inject_chimera.py", "--base-fasta", self.fa, "--base-tax", self.tax,
                "--distance", distance, "--breakpoint", bp, "--n", n, "--seed", seed,
                "--prefix", d / cell)
        self.assertEqual(r.returncode, 0, r.stderr)
        return d, json.loads((d / f"{cell}.truth.json").read_text())

    def test_breakpoint_is_on_the_ungapped_length_and_lands_on_a_column(self):
        """a1 has eight residues over twelve columns; half of them is four residues, and the fourth
        residue is column 6, so a chimera from a1 is a1's first six columns and B's last six."""
        d, truth = self.make("c", n=4, seed=3)
        seqs = {}
        name = None
        for line in (d / "c.fasta").read_text().splitlines():
            if line.startswith(">"):
                name = line[1:]
            else:
                seqs[name] = line
        for cid, rec in truth["injected"].items():
            col = rec["breakpoint_column"]
            a, b = rec["parent_a"], rec["parent_b"]
            self.assertEqual(seqs[cid], SEQ[a][:col] + SEQ[b][col:])
            if a == "a1":
                self.assertEqual(col, 6, "four residues of a1 take six columns")
            else:
                self.assertEqual(col, 6, "no gaps: half of twelve")
            self.assertEqual(len(seqs[cid]), 12, "the width is the alignment's")

    def test_parents_differ_exactly_at_the_requested_rank(self):
        for distance, r in (("genus", 5), ("family", 4)):
            _, truth = self.make(f"d_{distance}", distance=distance, n=2)
            for rec in truth["injected"].values():
                la, lb = rec["lineage_a"].split(";"), rec["lineage_b"].split(";")
                self.assertEqual(la[:r], lb[:r])
                self.assertNotEqual(la[r], lb[r])
                self.assertEqual(rec["wrong"], rec["lineage_a"], "it carries parent A's label")

    def test_base_untouched_and_same_seed_same_bytes(self):
        d1, _ = self.make("s1", seed=5)
        d2, _ = self.make("s2", seed=5)
        self.assertEqual((d1 / "s1.fasta").read_bytes(), (d2 / "s2.fasta").read_bytes())
        base_lines = [l for l in (d1 / "s1.fasta").read_text().splitlines()
                      if l.startswith(">") and not l.startswith(">chimera")]
        self.assertEqual(sorted(base_lines), sorted(f">{n}" for n in SEQ))

    def test_a_distance_with_no_partner_is_refused(self):
        r = run("inject_chimera.py", "--base-fasta", self.fa, "--base-tax", self.tax,
                "--distance", "phylum", "--breakpoint", 0.5, "--n", 1, "--seed", 1,
                "--prefix", self.tmp / "none")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("have a parent at phylum distance", r.stderr)

    def test_a_breakpoint_at_either_end_is_refused(self):
        """A chimera that is all of one parent is not a chimera; the bounds are strict."""
        for bp in (0.0, 1.0):
            r = run("inject_chimera.py", "--base-fasta", self.fa, "--base-tax", self.tax,
                    "--distance", "family", "--breakpoint", bp, "--n", 1, "--seed", 1,
                    "--prefix", self.tmp / "edge")
            self.assertNotEqual(r.returncode, 0, bp)
            self.assertIn("strictly between", r.stderr)

    def test_the_gate_counts_sound_cells_not_problems(self):
        """Two cells, one tampered: the summary reads 2 checked, 1 sound."""
        d1, _ = self.make("ok")
        d2, _ = self.make("bad", seed=2)
        lines = (d2 / "bad.fasta").read_text().splitlines()
        i = lines.index(">chimera_001") + 1
        lines[i] = ("A" if lines[i][0] != "A" else "C") + lines[i][1:]
        (d2 / "bad.fasta").write_text("\n".join(lines) + "\n")
        r = run("verify_chimera.py", "--base-fasta", self.fa, "--base-tax", self.tax,
                "--chimera-dir", self.tmp / "cells")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("2 chimera cells checked, 1 sound", r.stdout)

    def test_the_gate_passes_the_generator_and_refuses_a_changed_column(self):
        d, truth = self.make("g")
        gate = ["verify_chimera.py", "--base-fasta", self.fa, "--base-tax", self.tax,
                "--chimera-dir", self.tmp / "cells"]
        r = run(*gate)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = (d / "g.fasta").read_text().splitlines()
        i = lines.index(">chimera_001") + 1
        lines[i] = ("A" if lines[i][0] != "A" else "C") + lines[i][1:]
        (d / "g.fasta").write_text("\n".join(lines) + "\n")
        r = run(*gate)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("chimera_001: not", r.stderr)

    def test_scoring_reports_detection_and_which_parent_the_proposal_sides_with(self):
        d, truth = self.make("sc", n=2)
        c1, c2 = sorted(truth["injected"])
        other = truth["injected"][c1]["lineage_b"]
        neither = "d__A;p__P;c__C;o__O;f__F9;g__G9;s__S9"
        rows = [f"{c1}\tFamily\tf__x\tf__y\t0.900\t{truth['injected'][c1]['wrong']}\t{other}\t0.9\t1.000",
                f"{c2}\tFamily\tf__x\tf__y\t0.900\t{truth['injected'][c2]['wrong']}\t{neither}\t0.9\t1.000"]
        mis = self.tmp / "sc.mis"
        mis.write_text(HEADER + "\n" + "\n".join(rows) + "\n")
        out = self.tmp / "score.json"
        r = run("score_injection.py", "--truth", d / "sc.truth.json", "--mis", mis, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        score = json.loads(out.read_text())
        row = next(x for x in score["by_confidence"] if x["threshold"] == 0.0)
        self.assertEqual(score["kind"], "chimera")
        self.assertEqual(score["breakpoint"], 0.5)
        self.assertEqual(row["recall"], 1.0)
        self.assertIsNone(row["recall_at_injected_rank"], "no rank is wrong for a half-right label")
        self.assertEqual(row["proposed_sides_with_other_parent"], 0.5)

    def test_detection_table_sums_cells_through_the_scorer(self):
        # The scorer prints a summary to stdout beside the JSON it writes; the first run on the 72
        # real cells read both from /dev/stdout and died on "Extra data".
        d, truth = self.make("sc", n=2)
        runs = self.tmp / "runs" / "sc__epang__rep1"
        runs.mkdir(parents=True)
        (runs / "sc__epang__rep1.mis").write_text(HEADER + "\n" + "\n".join(
            f"{c}\tFamily\tf__x\tf__y\t0.900\t{rec['wrong']}\t{rec['lineage_b']}\t0.9\t1.000"
            for c, rec in sorted(truth["injected"].items())) + "\n")
        out = self.tmp / "det.json"
        r = run("chimera_detection.py", "--chimera-dir", self.tmp / "cells", "--runs-dir",
                self.tmp / "runs", "--condition", "epang__rep1", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(out.read_text())["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["distance"], rows[0]["breakpoint"], rows[0]["injected"],
                          rows[0]["detected"], rows[0]["sides_with_other_parent_of_flagged"]),
                         ("family", 0.5, 2, 2, 1.0))


if __name__ == "__main__":
    unittest.main()
