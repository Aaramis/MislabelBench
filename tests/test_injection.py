#!/usr/bin/env python3
"""The invariants of bin/inject_mislabels.py, which defines the ground truth of 180 grid cells.

Nothing tested this script. A mutation sweep over it survived eleven mutations out of eleven,
including `floor = args.k + 1` flipped to `args.k - 1`, which breaks the one rule its own docstring
calls non-negotiable: a donor taxon always keeps at least one correctly labelled member. Without that
rule the taxon vanishes from the tree when the injected sequences are removed, and the measurement
becomes a structural limit of leave-one-out rather than a property of the tool.

What stood in for a test was `bin/verify_injection.py` over the real cells, which checks that a cell's
.tax matches its truth.json, and the byte-identical regeneration of 378 cells recorded in
data/README.md. Both are checks on the output of one particular run; neither can say what the script
does to a case nobody has generated.

    python3 -m unittest tests.test_injection
    python3 tests/mutation_sweep.py bin/inject_mislabels.py tests.test_injection
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"
RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]
PER_SPECIES = 6


def taxonomy():
    """Four families, two genera each, two species each, six sequences each: 96 sequences.

    Six per species because the grid runs k up to 5 and a donor group needs k+1 members. Two
    children at every rank, including two species per genus: a sequence can only be moved to a
    sibling that shares the ranks above the distance, so one species per genus leaves the species
    distance with nowhere to go and injects nothing at all. That is what the first version of this
    fixture did, and it looked like a bug in the script.
    """
    rows = {}
    for f in range(4):
        for g in range(2):
            for sp in range(2):
                lineage = (f"d__A;p__B;c__C;o__O;f__F{f};g__G{f}_{g};s__S{f}_{g}_{sp}")
                for m in range(PER_SPECIES):
                    rows[f"seq_{f}_{g}_{sp}_{m}"] = lineage
    return rows


class InjectMislabels(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "base.tax"
        self.rows = taxonomy()
        self.base.write_text("".join(f"{n}\t{l}\n" for n, l in self.rows.items()))

    def inject(self, distance="genus", rate=0.25, k=2, seed=1, prefix="c", extra=()):
        out = self.tmp / prefix
        r = subprocess.run([sys.executable, str(BIN / "inject_mislabels.py"), str(self.base),
                            "--distance", distance, "--rate", str(rate), "--k", str(k),
                            "--seed", str(seed), "--prefix", str(out), *extra],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        tax = {l.split("\t")[0]: l.split("\t")[1]
               for l in (self.tmp / f"{prefix}.tax").read_text().splitlines()}
        truth = json.loads((self.tmp / f"{prefix}.truth.json").read_text())
        return tax, truth, r.stderr

    def test_every_donor_keeps_a_correct_member(self):
        """The rule the docstring calls non-negotiable, at the largest k the group can take."""
        for k in (1, 2, 3, 5):
            tax, truth, _ = self.inject(k=k, rate=0.5, prefix=f"k{k}")
            taken = {}
            for name, rec in truth["injected"].items():
                taken.setdefault(rec["donor_group"], []).append(name)
            for donor, names in taken.items():
                members = [n for n, l in self.rows.items() if l == donor]
                left = [n for n in members if n not in names]
                self.assertTrue(left, f"k={k}: donor {donor} lost every correct member")
                for n in left:
                    self.assertEqual(tax[n], donor, "a member left behind must keep its own label")

    def test_each_group_contributes_exactly_k(self):
        for k in (1, 2, 3, 5):
            _, truth, _ = self.inject(k=k, rate=0.5, prefix=f"g{k}")
            taken = {}
            for rec in truth["injected"].values():
                taken[rec["donor_group"]] = taken.get(rec["donor_group"], 0) + 1
            self.assertEqual(set(taken.values()), {k}, f"k={k} gave groups of {set(taken.values())}")

    def test_the_wrong_label_differs_exactly_at_the_requested_rank(self):
        for distance in ("species", "genus", "family"):
            r = RANKS.index(distance)
            _, truth, _ = self.inject(distance=distance, prefix=f"d{distance}")
            self.assertTrue(truth["injected"], f"no injection at {distance}")
            for rec in truth["injected"].values():
                true, wrong = rec["true"].split(";"), rec["wrong"].split(";")
                self.assertEqual(true[:r], wrong[:r], f"{distance}: prefix must be shared")
                self.assertNotEqual(true[r], wrong[r], f"{distance}: rank {r} must differ")

    def test_untouched_sequences_keep_their_exact_lineage(self):
        tax, truth, _ = self.inject()
        for name, lineage in self.rows.items():
            if name not in truth["injected"]:
                self.assertEqual(tax[name], lineage, name)
        self.assertEqual(len(tax), len(self.rows))

    def test_the_same_seed_gives_byte_identical_output(self):
        """The determinism the plan requires of every cell, and the only reason a cell can be
        regenerated from its seed instead of being committed."""
        self.inject(prefix="a")
        self.inject(prefix="b")
        self.assertEqual((self.tmp / "a.tax").read_bytes(), (self.tmp / "b.tax").read_bytes())
        a = json.loads((self.tmp / "a.truth.json").read_text())
        b = json.loads((self.tmp / "b.truth.json").read_text())
        a.pop("prefix", None), b.pop("prefix", None)
        self.assertEqual(a["injected"], b["injected"])

    def test_another_seed_gives_another_draw(self):
        _, one, _ = self.inject(seed=1, prefix="s1")
        _, two, _ = self.inject(seed=7, prefix="s7")
        self.assertNotEqual(set(one["injected"]), set(two["injected"]))

    def test_allow_empty_donor_lifts_the_rule_and_only_then(self):
        """k equal to the group size: impossible under the rule, possible when it is lifted."""
        _, strict, err = self.inject(k=PER_SPECIES, rate=0.5, prefix="strict")
        self.assertEqual(strict["injected"], {})
        self.assertIn("warning:", err)
        _, loose, _ = self.inject(k=PER_SPECIES, rate=0.5, prefix="loose",
                                  extra=("--allow-empty-donor",))
        self.assertTrue(loose["injected"])
        taken = {}
        for rec in loose["injected"].values():
            taken[rec["donor_group"]] = taken.get(rec["donor_group"], 0) + 1
        self.assertEqual(set(taken.values()), {PER_SPECIES}, "a whole group goes")

    def test_a_shortfall_is_warned_about_and_recorded(self):
        """Asking for more than the taxonomy can give must not be rounded down in silence."""
        _, truth, err = self.inject(k=1, rate=1.0, prefix="too_much")
        self.assertIn("warning:", err)
        self.assertLess(truth["n_injected"], truth["n_requested"])
        self.assertEqual(truth["n_injected"], len(truth["injected"]))

    def test_whole_groups_overshoot_by_less_than_k_and_the_rate_says_so(self):
        """96 at 10 % asks for 10, and groups of three reach 9 then 12: the overshoot is the design.

        k=3 rather than a k that divides, on purpose. The loop stops when the count reaches what was
        asked, and a boundary written `==` instead of `>=` would never match a count that steps over
        it -- the loop would then run to the last donor and inject every sequence in the taxonomy.
        """
        _, truth, err = self.inject(k=3, rate=0.1, prefix="over")
        self.assertEqual(truth["n_requested"], 10)
        self.assertEqual(truth["n_injected"], 12, "four groups of three, not every donor there is")
        self.assertEqual(truth["n_injected"], len(truth["injected"]))
        self.assertAlmostEqual(truth["rate_effective"], round(12 / len(self.rows), 6))
        self.assertIn("note:", err, "an overshoot is announced, not silent")

    def test_a_rate_that_divides_is_hit_exactly_and_warns_about_nothing(self):
        """96 sequences at 25 % is 24, and 24 is twelve whole groups of two.

        The loop stops once the count reaches what was asked, and whether that boundary is `>=` or
        `>` only shows up when the arithmetic lands exactly on it: with `>` a thirteenth group goes
        in and the cell runs at 27 % without saying so. The same case pins the shortfall warning,
        which must not fire when nothing fell short.
        """
        _, truth, err = self.inject(k=2, rate=0.25, prefix="exact")
        self.assertEqual(truth["n_requested"], 24)
        self.assertEqual(truth["n_injected"], 24)
        self.assertEqual(truth["rate_effective"], 0.25)
        self.assertNotIn("warning:", err)
        self.assertNotIn("note:", err)

    def test_a_distance_deeper_than_the_taxonomy_is_refused_by_name(self):
        """Not every reference has seven ranks -- an ITS taxonomy may stop at genus -- and asking
        for a distance the lineages do not reach has to be an error with a number in it, not an
        empty cell."""
        shallow = self.tmp / "shallow.tax"
        shallow.write_text("".join(f"s{i}\td__A;p__B;c__C\n" for i in range(6)))
        # Both the rank just past the end and one well past it: the first catches a guard written
        # with the wrong comparison, the second catches one that only tests equality and then walks
        # off the end of the lineage with an IndexError instead of a sentence.
        for distance, ranks_needed in (("order", 4), ("species", 7)):
            r = subprocess.run([sys.executable, str(BIN / "inject_mislabels.py"), str(shallow),
                                "--distance", distance, "--prefix", str(self.tmp / "sh")],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, distance)
            self.assertIn(f"needs at least {ranks_needed} ranks", r.stderr)
            self.assertIn("found 3", r.stderr)

    def test_ragged_lineages_are_refused(self):
        bad = self.tmp / "ragged.tax"
        bad.write_text("a\td__A;p__B\nb\td__A;p__B;c__C\n")
        r = subprocess.run([sys.executable, str(BIN / "inject_mislabels.py"), str(bad),
                            "--distance", "phylum", "--prefix", str(self.tmp / "r")],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ragged", r.stderr)


if __name__ == "__main__":
    unittest.main()
