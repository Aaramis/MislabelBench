#!/usr/bin/env python3
"""One property, over every gate bin/analyses.sh runs: a check that checked nothing must fail.

This repository has been bitten by it four times, and the comment in bin/verify/verify_injection.py records
the shape: `verify_inputs.py` printed "0 cells, 0 consistent" and exited 0 when a job left the working
directory at the Nextflow launch directory and a relative glob matched nothing. The gate said yes, and
nobody looked again.

Pointing each gate at an empty tree found two more of them, and a third defect that was hiding both:
`Path(".").glob` raises `NotImplementedError: Non-relative patterns are unsupported` on an absolute
pattern, so the `--glob` flags of five gates only ever worked for a caller already standing in the
benchmark root. Three of those five already had the guard this file tests for -- it was simply
unreachable from outside the root, and `verify_inputs.py` is the gate whose own silent pass is the
reason this file exists.

The positive cases matter as much: a gate that always fails passes the property above and is just as
useless, so verify_grid_complete is also checked on a sound grid and on one with a cell missing.

    python3 -m unittest tests.test_gates
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from binpath import find



def gate(script, *args):
    return subprocess.run([sys.executable, str(find(script)), *map(str, args)],
                          capture_output=True, text=True)


class NothingCheckedMustFail(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.empty = self.tmp / "empty"
        self.empty.mkdir()
        (self.tmp / "manifest.json").write_text(json.dumps({"datasets": []}))
        (self.tmp / "summary.json").write_text(json.dumps({"a": 1}))
        (self.tmp / "base.tax").write_text("")
        (self.tmp / "two.newick").write_text("(a:1,b:1);")
        (self.tmp / "empty.tax").write_text("")

    def cases(self):
        t, e = self.tmp, self.empty
        return [
            ("verify_recall_independently.py", ["--injected-dir", e, "--runs-dir", e,
                                                "--summary", f"c={t / 'summary.json'}"]),
            ("verify_grid_complete.py", ["--datasets-json", t / "manifest.json",
                                         "--conditions", "c", "--runs-dir", e]),
            ("verify_conditions_differ.py", ["--runs-glob", f"{e}/*"]),
            ("verify_fold_counts.py", ["--results", e]),
            ("verify_runs.py", ["--glob", f"{e}/*/run.json"]),
            ("verify_timed_one_model.py", ["--results", e]),
            ("verify_timing_flags.py", ["--glob", f"{e}/*/run.json", "--slurm", e]),
            ("verify_foreign.py", ["--base", t / "base.tax", "--foreign-dir", e]),
            ("verify_manifests.py", ["--glob", f"{e}/*.json"]),
            ("verify_inputs.py", ["--glob", f"{e}/*/run.json"]),
            ("verify_grove_taxonomy.py", ["--tree", t / "two.newick", "--tax", t / "empty.tax"]),
        ]

    def test_each_gate_refuses_an_empty_tree(self):
        for script, args in self.cases():
            with self.subTest(script=script):
                r = gate(script, *args)
                self.assertNotEqual(r.returncode, 0,
                                    f"{script} reported success over nothing:\n{r.stdout}")

    def test_the_refusal_says_what_was_missing(self):
        """Non-zero is the property; a traceback from inside pathlib is not a diagnosis. Three of
        these exited non-zero only by crashing before they could count anything."""
        for script, args in self.cases():
            with self.subTest(script=script):
                r = gate(script, *args)
                self.assertNotIn("Traceback", r.stderr, f"{script} crashed instead of reporting")

    def test_an_absolute_glob_is_accepted(self):
        """The three --glob gates took a pattern they could not use. Each now reaches its own guard,
        which is why the message above is reachable at all."""
        for script, flag in (("verify_runs.py", "--glob"),
                             ("verify_timing_flags.py", "--glob"),
                             ("verify_conditions_differ.py", "--runs-glob"),
                             ("verify_manifests.py", "--glob"),
                             ("verify_inputs.py", "--glob")):
            with self.subTest(script=script):
                args = [flag, f"{self.empty}/*/run.json"]
                if script == "verify_timing_flags.py":
                    args += ["--slurm", str(self.empty)]
                r = gate(script, *args)
                self.assertNotIn("Non-relative patterns", r.stderr + r.stdout)


class GridCompleteness(unittest.TestCase):
    """The positive half, so the guard above cannot be met by a gate that always says no."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.manifest = self.tmp / "datasets.json"
        self.manifest.write_text(json.dumps({"datasets": [
            {"name": "d1", "n_seqs": 10, "aln_len": 20, "fasta": "a", "tax": "b"},
            {"name": "d2", "n_seqs": 10, "aln_len": 20, "fasta": "a", "tax": "b"}]}))
        self.runs = self.tmp / "runs"
        self.runs.mkdir()

    def make(self, *names):
        for n in names:
            (self.runs / n).mkdir(parents=True, exist_ok=True)

    def check(self, *extra):
        return gate("verify_grid_complete.py", "--datasets-json", self.manifest,
                    "--conditions", "cond", "--runs-dir", self.runs, *extra)

    def test_a_complete_grid_passes(self):
        self.make("d1__cond__rep1", "d2__cond__rep1")
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok", r.stdout)
        self.assertIn("2/2", r.stdout)

    def test_a_missing_cell_fails_and_is_named(self):
        self.make("d1__cond__rep1")
        r = self.check()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("d2__cond__rep1", r.stderr)

    def test_an_unexpected_cell_fails_too(self):
        """Extra is as wrong as missing: a run directory the manifest does not name means the job
        and the manifest disagree about what was run."""
        self.make("d1__cond__rep1", "d2__cond__rep1", "d3__cond__rep1")
        r = self.check()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("d3__cond__rep1", r.stderr)

    def test_the_datasets_subset_narrows_what_is_expected(self):
        self.make("d1__cond__rep1")
        self.assertNotEqual(self.check().returncode, 0)
        r = self.check("--datasets", "d1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1/1", r.stdout)


class FoldCountsOnAStagedStrictRun(unittest.TestCase):
    """A strict leave-one-out run on the staged path keeps its run.json under runs/<cell>/ and its
    stage logs under staged/<cell>/; the gate once looked for the one beside the other."""

    def test_stage_logs_find_the_run_record_two_levels_up(self):
        root = Path(tempfile.mkdtemp())
        cell = "inj_x__epang_T8_Kexact__rep1"
        (root / "runs" / cell).mkdir(parents=True)
        (root / "runs" / cell / "run.json").write_text(json.dumps({"n_seqs": 4, "folds": 999999}))
        (root / "runs" / cell / f"{cell}.log").write_text("wrote 4 fold tasks\n")
        (root / "staged" / cell).mkdir(parents=True)
        (root / "staged" / cell / "reference.stage.log").write_text("reference built\n")
        r = gate("verify_fold_counts.py", "--results", root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 problem(s)", r.stdout)


if __name__ == "__main__":
    unittest.main()
