"""bin/truncate_alignment.py and bin/memory_width.py on hand-written inputs."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"


def run(script, *args):
    return subprocess.run([sys.executable, str(BIN / script), *map(str, args)],
                          capture_output=True, text=True)


class Truncate(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "a.fasta").write_text(">s1\nACGTACGT\nAC\n>s2\nTTTTTTTTTT\n")
        (self.tmp / "a.tax").write_text("s1\td__A;p__P\ns2\td__A;p__Q\n")

    def test_columns_spread_over_the_alignment_and_the_taxonomy_unchanged(self):
        # 10 columns, 4 kept: indices 0, 2, 5, 7 of ACGTACGTAC -> A G C T.
        r = run("truncate_alignment.py", "--fasta", self.tmp / "a.fasta", "--tax", self.tmp / "a.tax",
                "--columns", 4, "--prefix", self.tmp / "w" / "w")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.tmp / "w" / "w.fasta").read_text(), ">s1\nAGCT\n>s2\nTTTT\n")
        self.assertEqual((self.tmp / "w" / "w.tax").read_text(), (self.tmp / "a.tax").read_text())

    def test_a_sequence_left_without_a_residue_is_refused(self):
        # s3 has residues only in columns 1 and 3, which a 2-column cut (indices 0, 5) drops.
        (self.tmp / "c.fasta").write_text(">s1\nACGTACGTAC\n>s3\n-C-T------\n")
        r = run("truncate_alignment.py", "--fasta", self.tmp / "c.fasta", "--tax", self.tmp / "a.tax",
                "--columns", 2, "--prefix", self.tmp / "w" / "w")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no residue", r.stderr)
        self.assertIn("s3", r.stderr)

    def test_a_width_beyond_the_alignment_is_refused(self):
        r = run("truncate_alignment.py", "--fasta", self.tmp / "a.fasta", "--tax", self.tmp / "a.tax",
                "--columns", 11, "--prefix", self.tmp / "w" / "w")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("1..10", r.stderr)

    def test_unequal_widths_are_refused(self):
        (self.tmp / "b.fasta").write_text(">s1\nACGT\n>s2\nAC\n")
        r = run("truncate_alignment.py", "--fasta", self.tmp / "b.fasta", "--tax", self.tmp / "a.tax",
                "--columns", 2, "--prefix", self.tmp / "w" / "w")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not an alignment", r.stderr)


class MemoryWidth(unittest.TestCase):

    def test_the_fit_recovers_a_line_through_three_widths(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "datasets.json").write_text(json.dumps({"datasets": [
            {"name": "w0100", "aln_len": 100}, {"name": "w0200", "aln_len": 200},
            {"name": "w0400", "aln_len": 400}]}))
        # peak = 50 MB + 0.001 MB per sequence per column, 10 sequences
        for w in (100, 200, 400):
            d = tmp / "runs" / f"w{w:04d}__epang_T1_K25__rep1"
            d.mkdir(parents=True)
            (d / "run.json").write_text(json.dumps({"n_seqs": 10, "max_rss_mb": 50 + 0.001 * 10 * w}))
        r = run("memory_width.py", "--runs-dir", tmp / "runs", "--datasets", tmp / "datasets.json",
                "--out", tmp / "m.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads((tmp / "m.json").read_text())["epang_T1_K25"]
        self.assertAlmostEqual(m["intercept_mb"], 50.0, places=1)
        self.assertAlmostEqual(m["kb_per_seq_per_column"], 1.024, places=3)
        self.assertEqual([x["columns"] for x in m["rows"]], [100, 200, 400])
        self.assertEqual(m["rows"][2]["residual_mb"], 0.0)

    def test_no_run_is_refused(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "datasets.json").write_text(json.dumps({"datasets": []}))
        (tmp / "runs").mkdir()
        r = run("memory_width.py", "--runs-dir", tmp / "runs", "--datasets", tmp / "datasets.json")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no width run", r.stderr)


if __name__ == "__main__":
    unittest.main()
