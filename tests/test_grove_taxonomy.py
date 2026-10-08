#!/usr/bin/env python3
"""The three properties the Grove control's taxonomy has to have to be worth anything.

If any one of them breaks, the control stops being a control and nobody downstream can tell: the
labels would simply be wrong, and a tool that flags them would look wrong instead.

  every tip labelled at every rank   a sequence with no species is not in the reference at all,
                                     and the first version of this rule silently dropped three
                                     quarters of a phylogram's tips this way
  ranks nested                       a genus that spans two families is not a taxonomy
  independent of sibling order       the same tree written with its children in another order has
                                     to give byte-identical labels, or no result is reproducible

  python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"
RANKS = 7


def yule(n, seed, rate_sd):
    """Pure birth to n tips, then each branch scaled by a lognormal rate, so not ultrametric."""
    rng = random.Random(seed)
    root = {"name": "t0001", "len": 0.0, "kids": []}
    nodes, tips = [root], [root]
    while len(tips) < n:
        dt = rng.expovariate(len(tips))
        for t in tips:
            t["len"] += dt
        i = rng.randrange(len(tips))
        kids = [{"name": f"t{len(nodes) + j:04d}", "len": 0.0, "kids": []} for j in (0, 1)]
        tips[i]["kids"] = kids
        nodes += kids
        tips[i:i + 1] = kids
    out = []
    stack = [root]
    while stack:                                    # scale every branch, iteratively
        nd = stack.pop()
        nd["len"] *= pow(2.718281828, rng.gauss(0, rate_sd))
        stack += nd["kids"]
        out.append(nd)

    def newick(nd, flip):
        if not nd["kids"]:
            return f"{nd['name']}:{nd['len']:.6f}"
        kids = nd["kids"][::-1] if flip else nd["kids"]
        return "(" + ",".join(newick(k, flip) for k in kids) + f"):{nd['len']:.6f}"

    return newick(root, False) + ";\n", newick(root, True) + ";\n"


class NewickParser(unittest.TestCase):
    """The hand-written parser, which everything else here is downstream of.

    It exists because this repository's scripts take no dependencies, and it is the piece most likely
    to be quietly wrong: a tip name attached to the wrong node, or a branch length read onto its
    parent, would shift every rank without raising anything.
    """

    def setUp(self):
        spec = importlib.util.spec_from_file_location("gt", BIN / "grove_taxonomy.py")
        self.gt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gt)

    def tips(self, newick):
        nodes = self.gt.parse_newick(newick)
        h, _ = self.gt.heights(nodes)
        return {n["name"]: h[i] for i, n in enumerate(nodes) if not n["children"]}

    def test_root_distances(self):
        # A is 0.1 under a 0.3 branch, C hangs straight off the root.
        self.assertEqual(self.tips("((A:0.1,B:0.2)X:0.3,C:0.4);"),
                         {"A": 0.4, "B": 0.5, "C": 0.4})

    def test_internal_labels_do_not_steal_a_tip_name(self):
        nodes = self.gt.parse_newick("((A:0.1,B:0.2)X:0.3,C:0.4);")
        named = {n["name"] for n in nodes}
        self.assertEqual(named, {"", "A", "B", "C", "X"})
        inner = [n for n in nodes if n["children"]]
        self.assertEqual({n["name"] for n in inner}, {"", "X"})

    def test_trailing_name_and_missing_semicolon(self):
        # Both legal, and both end the string somewhere the scanner has to stop by itself.
        self.assertEqual(set(self.tips("(A:1,(B:1,C:1):2)Root")), {"A", "B", "C"})
        self.assertEqual(set(self.tips("(A:1,(B:1,C:1):2)")), {"A", "B", "C"})

    def test_comments_are_dropped(self):
        self.assertEqual(set(self.tips("((A:0.1,B:0.2)[&&NHX:x=1]:0.3,C:0.4);")),
                         {"A", "B", "C"})

    def test_unbalanced_parentheses_refused(self):
        with self.assertRaises(SystemExit):
            self.gt.parse_newick("((A:0.1,B:0.2):0.3,C:0.4;")


class GroveTaxonomy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.n = 200
        # Seed 3 rather than any seed: it is the one in 1..14 whose taxonomy has species of exactly
        # six members (six of them), which is the boundary the donor-group field is counted on. On a
        # seed with none, `>= 6` and `> 6` give the same answer and the assertion below proves
        # nothing.
        plain, flipped = yule(cls.n, 3, 0.5)
        (cls.tmp / "tree.newick").write_text(plain)
        (cls.tmp / "flipped.newick").write_text(flipped)
        for tag in ("tree", "flipped"):
            r = subprocess.run([sys.executable, str(BIN / "grove_taxonomy.py"),
                                "--tree", str(cls.tmp / f"{tag}.newick"),
                                "--prefix", str(cls.tmp / tag)],
                               capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
        cls.paths = {sid: lin.split(";") for sid, lin in
                     (l.split("\t") for l in (cls.tmp / "tree.tax").read_text().splitlines())}
        cls.record = json.loads((cls.tmp / "tree.grove_tax.json").read_text())

    def test_every_tip_has_every_rank(self):
        self.assertEqual(len(self.paths), self.n)
        for sid, path in self.paths.items():
            self.assertEqual(len(path), RANKS, sid)
            self.assertTrue(all(path), sid)

    def test_ranks_are_nested(self):
        for r in range(1, RANKS):
            parents = {}
            for path in self.paths.values():
                parents.setdefault(path[r], set()).add(path[r - 1])
            spanning = {k: v for k, v in parents.items() if len(v) > 1}
            self.assertEqual(spanning, {}, f"rank {r} clades spanning two parents: {spanning}")

    def test_ranks_refine(self):
        counts = [len({p[r] for p in self.paths.values()}) for r in range(RANKS)]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual(counts[-1], self.record["n_species"])

    def test_clade_counts_match_the_ladder(self):
        """Nothing else here notices if every rank comes out the same size.

        A mutation sweep made the target `min(2, ...)` instead of `max(2, ...)`, which gives seven
        ranks of two clades each. That is still nested, still refining in the weak sense, and still
        labels every tip, so the other four tests all passed: a taxonomy with two species for 200
        sequences would have gone out as a control.
        """
        ladder = [max(2, round(self.n ** ((r + 1) / (RANKS + 1)))) for r in range(RANKS)]
        counts = [len({p[r] for p in self.paths.values()}) for r in range(RANKS)]
        self.assertEqual(counts, ladder)
        self.assertEqual(list(self.record["clades"].values()), ladder)

    def test_clade_names_are_dense_and_one_based(self):
        """The names are the labels a reference is judged on, so their form is part of the output."""
        for r, rank in enumerate(("domain", "phylum", "class", "order", "family", "genus",
                                  "species")):
            seen = {p[r] for p in self.paths.values()}
            self.assertEqual(seen, {f"{rank[0]}__{i:04d}" for i in range(1, len(seen) + 1)})

    def test_clade_one_holds_the_smallest_tip(self):
        """The documented naming rule, which is what makes the labels independent of file order.

        Naming by the largest tip instead would be just as deterministic and just as order-blind, so
        the dense-names test above cannot see the difference. This can.
        """
        smallest = min(self.paths)
        for r in range(RANKS):
            self.assertEqual(self.paths[smallest][r][3:], "0001")

    def test_sibling_order_does_not_matter(self):
        self.assertEqual((self.tmp / "tree.tax").read_bytes(),
                         (self.tmp / "flipped.tax").read_bytes())

    def test_the_record_describes_the_taxonomy_it_wrote(self):
        """Every counted field recomputed from the .tax, because these are the control's own numbers.

        `species_of_six_or_more` is the one that decides whether the grid's k=5 cells have any donor
        group to use, and `judgeable_fraction` is the number the whole control is judged on. A record
        that disagrees with its own .tax would be believed.
        """
        species = {}
        for path in self.paths.values():
            species.setdefault(path[-1], []).append(path)
        sizes = sorted(len(v) for v in species.values())
        self.assertEqual(self.record["n_species"], len(species))
        self.assertEqual(self.record["n_singleton_species"], sizes.count(1))
        self.assertEqual(self.record["largest_species"], sizes[-1])
        self.assertEqual(self.record["species_of_six_or_more"],
                         sum(1 for n in sizes if n >= 6))
        self.assertEqual(self.record["sequences_in_species_of_six_or_more"],
                         sum(n for n in sizes if n >= 6))
        self.assertEqual(self.record["judgeable_fraction"]["species"],
                         round(sum(n for n in sizes if n > 1) / self.n, 4))

    def test_cut_heights_do_not_go_backwards(self):
        """A rank cannot be cut above the rank it refines. Reported, so it has to be right."""
        cuts = list(self.record["cut_height"].values())
        self.assertEqual(cuts, sorted(cuts))

    def test_too_few_tips_refused_at_the_boundary(self):
        """Seven ranks need eight tips, so seven is refused and eight is not. The guard is one
        comparison and the sweep could flip it either way without a test on the boundary itself."""
        for n, ok in ((7, False), (8, True)):
            tree = self.tmp / f"n{n}.newick"
            tree.write_text("(" + ",".join(f"t{i}:0.{i}" for i in range(1, n + 1)) + ");")
            r = subprocess.run([sys.executable, str(BIN / "grove_taxonomy.py"), "--tree", str(tree),
                                "--prefix", str(self.tmp / f"n{n}")], capture_output=True, text=True)
            self.assertEqual(r.returncode == 0, ok, r.stderr)
            if not ok:
                self.assertIn("too few", r.stderr)

    def test_negative_branch_length_refused(self):
        bad = self.tmp / "bad.newick"
        bad.write_text("((a:1,b:1):-1,(c:1,d:1):1,(e:1,f:1):1,(g:1,h:1):1);")
        r = subprocess.run([sys.executable, str(BIN / "grove_taxonomy.py"), "--tree", str(bad),
                            "--prefix", str(self.tmp / "bad")], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("negative branch length", r.stderr)


if __name__ == "__main__":
    unittest.main()
