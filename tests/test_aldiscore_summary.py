"""bin/analysis/aldiscore_summary.py on three hand-written score lines."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from binpath import find



def line(name, n, out):
    import re
    return json.dumps({"set": name, "n_sequences": n, "stdout": out,
                       "numbers_in_output": re.findall(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", out)})


class AldiscoreSummary(unittest.TestCase):

    def run_it(self, lines):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "scores.jsonl").write_text("\n".join(lines) + "\n")
        out = tmp / "s.json"
        r = subprocess.run([sys.executable, str(find("aldiscore_summary.py")), "--scores",
                            str(tmp / "scores.jsonl"), "--out", str(out)], capture_output=True, text=True)
        return r, out

    def test_foreign_cells_are_a_delta_from_the_subset_by_rate(self):
        r, out = self.run_it([line("gtdb_arc2k", 2023, "0.10"), line("fgn_r0.01_s1", 2043, "0.13"),
                              line("fgn_r0.01_s2", 2043, "0.11"), line("fgn_r0.05_s1", 2124, "0.20")])
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads(out.read_text())
        self.assertAlmostEqual(s["foreign_vs_base"]["0.01"]["mean_delta"], 0.02)
        self.assertEqual(s["foreign_vs_base"]["0.01"]["cells"], 2)
        self.assertAlmostEqual(s["foreign_vs_base"]["0.01"]["min_delta"], 0.01)
        self.assertAlmostEqual(s["foreign_vs_base"]["0.01"]["max_delta"], 0.03)
        self.assertAlmostEqual(s["foreign_vs_base"]["0.05"]["max_delta"], 0.10)
        self.assertRegex(r.stdout, r"0\.01\s+2\s+0\.02000\s+0\.01000\s+0\.03000")
        self.assertEqual(s["sets"]["gtdb_arc2k"]["n_sequences"], 2023)

    def test_an_output_that_is_not_one_number_is_refused(self):
        r, _ = self.run_it([line("gtdb_arc2k", 2023, "warning: 3 sequences dropped\n0.10")])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("expected one number", r.stderr)

    def test_an_empty_file_is_refused(self):
        r, _ = self.run_it([""])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no set scored", r.stderr)


if __name__ == "__main__":
    unittest.main()
