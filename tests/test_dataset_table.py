#!/usr/bin/env python3
"""The two producers that read a GTDB release file: the protocol's dataset table and the bacterial
clade selection. Both are counting, and counting is where a benchmark's numbers quietly go wrong,
so the fixture is small enough that every figure below is checked by hand.

Six archaeal records of two species: one species has three sequences from two genomes (one genome
contributing two SSU copies, the `~` suffix), the other has one; a sixth record is a short fragment
of the first species. A reps file holds one sequence per species.

    python3 -m unittest tests.test_dataset_table
"""

import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"
ARC = "d__Archaea;p__P;c__C;o__O;f__F;g__G"
BAC = "d__Bacteria;p__Bacillota;c__Clostridia;o__Lachno;f__F;g__G"


def record(acc, lineage, length):
    return f">{acc} {lineage} [location=1..{length}] [ssu_len={length}] [contig_len={length}]\nACGT\n"


class DatasetTable(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.all = self.tmp / "ssu_all.fna.gz"
        self.reps = self.tmp / "reps.fna.gz"
        with gzip.open(self.all, "wt") as fh:
            fh.write(record("GB_GCA_1.1~A", f"{ARC};s__G one", 1500))
            fh.write(record("GB_GCA_1.1~B", f"{ARC};s__G one", 1500))   # same genome, second copy
            fh.write(record("GB_GCA_2.1", f"{ARC};s__G one", 1500))     # second genome
            fh.write(record("GB_GCA_3.1", f"{ARC};s__G two", 1500))     # a species of one
            fh.write(record("GB_GCA_4.1", f"{ARC};s__G one", 800))      # a fragment
            fh.write(record("GB_GCA_9.1", f"{BAC};s__G bact", 1500))    # another domain
            # A species of exactly two sequences from exactly two genomes, one of them exactly
            # 1 200 nt: the three boundaries a sweep flipped without the fixture noticing.
            fh.write(record("GB_GCA_5.1", f"{ARC};s__G three", 1200))
            fh.write(record("GB_GCA_6.1", f"{ARC};s__G three", 1500))
        with gzip.open(self.reps, "wt") as fh:
            fh.write(record("GB_GCA_1.1", f"{ARC};s__G one", 1500))
            fh.write(record("GB_GCA_3.1", f"{ARC};s__G two", 1500))

    def table(self):
        out = self.tmp / "table.json"
        r = subprocess.run([sys.executable, str(BIN / "dataset_table.py"), "--ssu-all", str(self.all),
                            "--ssu-reps", str(self.reps), "--out", str(out)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(out.read_text())["rows"]

    def test_counts_and_evaluability_by_hand(self):
        rows = self.table()
        self.assertEqual(rows["ssu_reps"]["sequences"], 2)
        self.assertEqual(rows["ssu_reps"]["evaluable_species_pct"], 0.0, "one per species")
        self.assertEqual(rows["ssu_reps"]["evaluable_genus_pct"], 100.0, "both share the genus")
        self.assertEqual(rows["ssu_all"]["sequences"], 7, "the bacterial record is not archaea")
        # Seven archaeal sequences: four in a species of four, two in a species of two, one alone.
        self.assertEqual(round(rows["ssu_all"]["evaluable_species_pct"], 1), round(100 * 6 / 7, 1))
        self.assertEqual(round(rows["ssu_all"]["evaluable_species_two_genomes_pct"], 1),
                         round(100 * 6 / 7, 1), "four from three genomes, two from two")
        after = rows["ssu_all_over_1200"]
        self.assertEqual(after["sequences"], 6, "the fragment is gone, the 1 200 nt one stays")
        self.assertEqual(round(after["evaluable_species_pct"], 1), round(100 * 5 / 6, 1))
        self.assertEqual(after["n_species"], 3)

    def test_the_two_genome_share_sees_through_copies_of_one_genome(self):
        """Two SSU copies of one genome are siblings for leave-one-out but not two isolates."""
        with gzip.open(self.all, "wt") as fh:
            fh.write(record("GB_GCA_1.1~A", f"{ARC};s__G one", 1500))
            fh.write(record("GB_GCA_1.1~B", f"{ARC};s__G one", 1500))
        rows = self.table()
        self.assertEqual(rows["ssu_all"]["evaluable_species_pct"], 100.0)
        self.assertEqual(rows["ssu_all"]["evaluable_species_two_genomes_pct"], 0.0)


class BacterialCladeSelection(unittest.TestCase):

    def test_the_nearest_clade_wins_and_the_runner_up_is_recorded(self):
        """Two orders, one at the archaeal targets and one far from them, with the minimum lifted
        so a six-record fixture qualifies. The score is the sum of two relative distances, so the
        order sitting on both targets scores zero and the other does not."""
        tmp = Path(tempfile.mkdtemp())
        fa = tmp / "ssu_all.fna.gz"
        near = "d__Bacteria;p__P;c__C;o__Near;f__F;g__G"
        far = "d__Bacteria;p__P;c__C;o__Far;f__F;g__G"
        with gzip.open(fa, "wt") as fh:
            for i in range(3):
                fh.write(record(f"GB_GCA_{i}.1", f"{near};s__S a", 1500))
            fh.write(record("GB_GCA_7.1", f"{near};s__S b", 1500))
            for i in range(10, 14):
                fh.write(record(f"GB_GCA_{i}.1", f"{far};s__S c", 1500))
        src = (BIN / "select_bacterial_clade.py").read_text()
        # The targets are the archaeal set's; the fixture cannot have 7 051 sequences, so the test
        # checks the ordering and the record, not the absolute score.
        r = subprocess.run([sys.executable, "-c", src.replace("if n < 1000:", "if n < 1:")
                            .replace('if __name__ == "__main__":\n    main()', "main()"),
                            "--fasta", str(fa), "--ranks", "order", "--out", str(tmp / "sel.json")],
                           capture_output=True, text=True, cwd=BIN)
        self.assertEqual(r.returncode, 0, r.stderr)
        sel = json.loads((tmp / "sel.json").read_text())
        self.assertEqual(len(sel["candidates"]), 2)
        self.assertEqual([c["clade"].split(";")[-1] for c in sel["candidates"]],
                         sorted((c["clade"].split(";")[-1] for c in sel["candidates"]),
                                key=lambda n: [c["score"] for c in sel["candidates"]
                                               if c["clade"].endswith(n)][0]))
        self.assertEqual(sel["chosen"]["over_1200"], 4)
        self.assertIn(sel["chosen"]["judgeable_species_pct"], (75.0, 100.0))
        self.assertLess(sel["chosen"]["score"], sel["candidates"][1]["score"])


if __name__ == "__main__":
    unittest.main()
