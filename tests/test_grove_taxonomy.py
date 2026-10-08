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


class GroveTaxonomy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.n = 200
        plain, flipped = yule(cls.n, 7, 0.5)
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

    def test_sibling_order_does_not_matter(self):
        self.assertEqual((self.tmp / "tree.tax").read_bytes(),
                         (self.tmp / "flipped.tax").read_bytes())

    def test_negative_branch_length_refused(self):
        bad = self.tmp / "bad.newick"
        bad.write_text("((a:1,b:1):-1,(c:1,d:1):1,(e:1,f:1):1,(g:1,h:1):1);")
        r = subprocess.run([sys.executable, str(BIN / "grove_taxonomy.py"), "--tree", str(bad),
                            "--prefix", str(self.tmp / "bad")], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("negative branch length", r.stderr)


if __name__ == "__main__":
    unittest.main()
