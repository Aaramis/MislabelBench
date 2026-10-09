#!/usr/bin/env python3
"""Does every dataset manifest tell the truth about its files?

`n_seqs` and `aln_len` are declared in a manifest, flow into `meta`, and are recorded in every
`run.json`, where they end up in figures and tables. Nothing checked them against the files they
describe, and the five manifests in this repo were all written by hand.

It also insists each fasta is an alignment of one width, which is the assumption every consumer
makes and which was violated once: a size subset was drawn from the ragged release file instead of
the aligned one, and it looked entirely plausible until the widths were measured.

And it refuses an absolute path twice over: in a manifest entry, and in the symlink a relative entry
may point at. Those are the same defect and only the first was checked. Every cell's alignment is a
link to the one file the cells share, 45 of them are committed, and all 45 named
/Users/auguste/Documents/git/sativa-epang-benchmark -- so every clone on any other machine had 45
dangling alignments, and no documented command repaired them.

A check, so it exits non-zero when something disagrees.
"""

import argparse
import hashlib
import json
from collections import defaultdict
import os
import re as _re
import sys
from pathlib import Path

from _paths import expand


def measure(fasta):
    """Sequence count and the set of sequence lengths, counted rather than trusted."""
    n, widths, cur = 0, set(), 0
    for line in Path(fasta).read_text().splitlines():
        if line.startswith(">"):
            if n:
                widths.add(cur)
            n, cur = n + 1, 0
        else:
            cur += len(line.strip())
    if n:
        widths.add(cur)
    return n, widths



def check_symlinks(problems, root=Path("data")):
    """Every link under data/ must be relative and must resolve.

    Relative because an absolute target names one machine under one home, which is what the manifest
    check below says of a path and is no less true of a link. Resolving because a link that does not
    is a dataset that is not there, and the manifest check only sees the cells a manifest lists.
    """
    links = [p for p in root.rglob("*") if p.is_symlink()]
    for link in links:
        target = os.readlink(link)
        if os.path.isabs(target):
            problems.append(f"{link}: links to {target}, an absolute path that resolves on one "
                            f"machine under one home")
        elif not link.exists():
            problems.append(f"{link}: links to {target}, which is not there")
    return len(links)



def _block(text, key, value=r"([0-9.]+)\s*$"):
    """The `name: number` entries indented under `key:`, as a dict.

    Parsed with a regular expression rather than with pyyaml, for the reason check_alignment_model
    already parses this file that way: this runs in bin/analyses.sh on a fresh clone, and a gate that
    needs a package the rest of the chain does not is a gate that is skipped.
    """
    m = _re.search(rf"^(\s*){key}:\s*(#.*)?$", text, _re.M)
    if not m:
        return None
    indent, out = len(m.group(1)), {}
    for line in text[m.end():].splitlines()[1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip()) <= indent:
            break
        entry = _re.match(rf"\s+(\w+):\s*{value}", line)
        if entry:
            out[entry.group(1)] = float(entry.group(2))
    return out


def check_staged_reference(problems):
    """assets/staged_check_reference.sha256 must match the file it names.

    slurm/staged_check.sh compares the four-stage path's flag list against that digest rather than
    against the file, because the file lives under results/ and bin/restore_cluster.sh leaves results/
    empty by construction on the cluster: the check was passing only where the original run happened to
    survive, and it failed with "no single-process .mis at ..." once the cluster was rebuilt. A digest
    travels with the code, and this is what keeps it from drifting from what it describes.
    """
    rec = Path("assets/staged_check_reference.sha256")
    if not rec.exists():
        problems.append(f"{rec} is missing; slurm/staged_check.sh has nothing to compare against")
        return 0
    rows = [l.split() for l in rec.read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    for row in rows:
        if len(row) != 2:
            problems.append(f"{rec}: expected '<digest>  <path>', got {' '.join(row)[:60]}")
            continue
        digest, path = row
        target = Path(path)
        if not target.exists():
            problems.append(f"{rec}: {path} does not exist")
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            problems.append(f"{rec}: {path} does not match the recorded digest")
    return len(rows)


def check_subsets(problems):
    """Every size subset takes whole species groups, which is what makes it resemble its parent.

    `bin/subset_taxa.py` opens by saying it cuts "by taking whole taxa, never part of one", and why:
    leave-one-out needs a sequence to have a sibling in its taxon, so removing half the members of a
    species turns judgeable sequences into unjudgeable ones and the subset stops resembling the set it
    came from. Nothing checked it. `bin/verify_regeneration.py` rebuilds the four subsets and compares
    them byte for byte, which would reproduce a wrong subset faithfully.

    Two things per subset: no sequence from outside the parent, and no species group present in part.
    """
    n = 0
    for rec_path in sorted(Path("data").glob("*/*.subset.json")):
        rec = json.loads(rec_path.read_text())
        # The record names the source by basename and digest rather than by path, the way every
        # provenance record here does, so it resolves beside the subset it describes.
        src = rec_path.parent / Path(rec["source_taxonomy"]).name
        sub = rec_path.with_name(rec_path.name.replace(".subset.json", ".tax"))
        if not src.exists() or not sub.exists():
            problems.append(f"{rec_path}: {src} or {sub} is missing")
            continue
        parent = read_tax(src)
        child = read_tax(sub)
        groups = defaultdict(set)
        for name, lineage in parent.items():
            groups[lineage].add(name)
        outside = [x for x in child if x not in parent]
        if outside:
            problems.append(f"{sub.name}: {len(outside)} sequence(s) not in {src.name}, "
                            f"e.g. {outside[0]}")
        partial = [lin for lin in {child[x] for x in child}
                   if {x for x in child if child[x] == lin} != groups.get(lin, set())]
        if partial:
            problems.append(f"{sub.name}: {len(partial)} species group(s) taken in part, "
                            f"e.g. {partial[0][-44:]}")
        n += 1
    return n


def read_tax(path):
    out = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if line.strip():
            name, _, lineage = line.partition("\t")
            out[name] = lineage
    return out


def check_provenance(problems):
    """assets/datasets.yml states counts and judgeability; committed files hold both.

    Every figure here had a counterpart in the repository and nothing compared the two -- the file
    even carries the command that reproduces one of them, in a comment, which is a check written down
    and never run. It is not hypothetical: the same block's own comment records that it published
    81.5 % at species where the rule gives 72.7, "only this file and the protocol said 81.5 %", and
    that an adjacent label described a different statistic for 35 points.
    """
    yml = Path("assets/datasets.yml")
    if not yml.exists():
        return 0
    text = yml.read_text()
    checked = 0

    def records(path):
        p = Path(path)
        return sum(1 for l in p.read_text().splitlines() if l.startswith(">")) if p.exists() else None

    def shape(path, field="judgeable_pct_of_labelled"):
        p = Path(path)
        return json.loads(p.read_text()).get(field) if p.exists() else None

    # A declared count against the file it describes.
    for key, path, what in (
            ("judgeable_pct_after_length", "results/shape_gtdb_arc1200.json", "the archaeal set"),
            ("judgeable_pct", "data/unite/unite_shape.json", "UNITE RepS"),
            ("refs_judgeable_pct", "data/unite/unite_refs_shape.json", "UNITE RefS")):
        want = _block(text, key) or _block(text, key, r"\{of_labelled:\s*([0-9.]+)")
        have = shape(path)
        if not want or not have:
            continue
        for rank, v in want.items():
            if rank not in have:
                problems.append(f"datasets.yml: {key} names {rank}, {path} does not")
            elif abs(have[rank] - v) > 0.05:
                problems.append(f"datasets.yml: {key}.{rank} says {v}, {path} computes "
                                f"{have[rank]} for {what}")
            checked += 1

    # The protocol's dataset table, produced by bin/dataset_table.py from the release files and
    # committed as data/gtdb/dataset_table.json. Its filtered row and results/shape_gtdb_arc1200.json
    # are two computations of one quantity and must agree; its ssu_all row is what the YAML's
    # judgeable_pct_after_domain asserts, which nothing could rebuild before the table existed.
    table = Path("data/gtdb/dataset_table.json")
    if table.exists():
        rows = json.loads(table.read_text())["rows"]
        have = shape("results/shape_gtdb_arc1200.json") or {}
        row = rows.get("ssu_all_over_1200", {})
        for rank in ("genus", "species"):
            a, b = row.get(f"evaluable_{rank}_pct"), have.get(rank)
            if a is not None and b is not None:
                checked += 1
                if abs(a - b) > 0.05:
                    problems.append(f"dataset_table.json says {a} at {rank} after the length "
                                    f"filter, results/shape_gtdb_arc1200.json computes {b}")
        want = _block(text, "judgeable_pct_after_domain")
        row = rows.get("ssu_all", {})
        for rank, v in (want or {}).items():
            a = row.get(f"evaluable_{rank}_pct")
            if a is not None:
                checked += 1
                if abs(a - v) > 0.05:
                    problems.append(f"datasets.yml: judgeable_pct_after_domain.{rank} says {v}, "
                                    f"dataset_table.json computes {a}")
        n = rows.get("ssu_all", {}).get("sequences")
        m = _re.search(r"^\s*after_domain:\s*(\d+)\s*$", text, _re.M)
        if m and n is not None:
            checked += 1
            if int(m.group(1)) != n:
                problems.append(f"datasets.yml: after_domain says {m.group(1)}, "
                                f"dataset_table.json holds {n}")

    for key, path, label in (("after_length", "data/gtdb/gtdb_arc1200.fasta", "archaeal"),
                             ("drawn", "data/bacteria/donor_pool.fasta", "donor")):
        m = _re.search(rf"^\s*{key}:\s*(\d+)\s*$", text, _re.M)
        n = records(path)
        if m and n is not None:
            checked += 1
            if int(m.group(1)) != n:
                problems.append(f"datasets.yml: {key} says {m.group(1)}, {path} holds {n} "
                                f"{label} records")
    return checked


def check_alignment_model(problems):
    """The covariance models and the widths they impose, which nothing else here checks.

    assets/datasets.yml records the sha256 of the whole Rfam.cm.gz, not of the model extracted from
    it, so the file every alignment was actually built against had no recorded identity. It does
    now, along with the consensus length: cmalign --matchonly keeps the model's own columns, so
    CLEN is the width of every alignment built against that model, and the archaeal set and the
    bacterial donors sharing RF01959's width is what makes error kind 6's concatenation possible
    rather than lucky.

    Two models since the bacterial replication: RF01959 for the archaea and the donors, RF00177 for
    the bacterial clade, which runs alone and is aligned against the model for its own molecule.
    Each alignment is checked against the model its path names, not against one width for all.
    """
    import re as _re

    yml = Path("assets/datasets.yml")
    if not yml.exists():
        return 0
    text = yml.read_text()
    models = {
        "rfam_ssu_archaea": ("data/gtdb/RF01959.cm", ("data/gtdb/gtdb_arc", "data/bacteria/")),
        "rfam_ssu_bacteria": ("data/gtdb/RF00177.cm", ("data/gtdb/gtdb_bac",)),
    }
    checked = 0
    for key, (cm_path, prefixes) in models.items():
        cm = Path(cm_path)
        block = _re.search(rf"^  {key}:\n((?:    .*\n|\s*#.*\n)+)", text, _re.M)
        if not cm.exists() or not block:
            continue
        want = _re.search(r"extracted_sha256:\s*([0-9a-f]{64})", block.group(1))
        clen = _re.search(r"consensus_length:\s*(\d+)", block.group(1))
        if not want or not clen:
            problems.append(f"assets/datasets.yml: {key} records no extracted_sha256 or "
                            f"consensus_length")
            continue
        got = hashlib.sha256(cm.read_bytes()).hexdigest()
        if got != want.group(1):
            problems.append(f"{cm}: sha256 {got[:16]}... against {want.group(1)[:16]}... recorded")
        header = dict(line.split(None, 1) for line in cm.read_text().splitlines()[:12]
                      if " " in line and not line.startswith("INFERNAL"))
        if header.get("CLEN", "").strip() != clen.group(1):
            problems.append(f"{cm}: CLEN {header.get('CLEN')} against consensus_length "
                            f"{clen.group(1)}")
        alns = [a for a in sorted(Path("data").rglob("*.aligned.fasta"))
                + [Path("data/gtdb/gtdb_arc2k.fasta"), Path("data/gtdb/gtdb_bac2k.fasta")]
                if a.exists() and any(str(a).startswith(pr) for pr in prefixes)]
        for aln in alns:
            widths, cur = set(), 0
            for line in aln.read_text().splitlines():
                if line.startswith(">"):
                    if cur:
                        widths.add(cur)
                    cur = 0
                else:
                    cur += len(line.strip())
            if cur:
                widths.add(cur)
            checked += 1
            if widths != {int(clen.group(1))}:
                problems.append(f"{aln}: widths {sorted(widths)} against {key}'s "
                                f"{clen.group(1)} columns")
    return checked


def check_data_readme(problems):
    """data/README.md states how many files the generators produce; the directories decide.

    It said "378 files from the two make_ scripts" while there were four generators and 481 files,
    which is the fourth table in this repository to have been written once and left while the thing
    it described grew. The counts are parsed from the sentence rather than from a machine-readable
    block, because the sentence is what a reader reads.
    """
    import re as _re

    readme = Path("data/README.md")
    if not readme.exists():
        return 0
    text = readme.read_text()
    counted = {}
    for sub in ("injected", "foreign", "clade", "simulated"):
        d = Path("data") / sub
        if not d.is_dir():
            return 0
        counted[sub] = sum(1 for f in d.rglob("*") if f.is_file() and f.name != "warn.txt"
                           and not f.name.endswith(("truth.json", "datasets.json")))
    total = sum(counted.values())
    stated_total = _re.search(r"\*\*(\d+) files --", text)
    if not stated_total:
        problems.append("data/README.md states no total for the regenerated files")
        return 0
    if int(stated_total.group(1)) != total:
        problems.append(f"data/README.md says {stated_total.group(1)} regenerated files, "
                        f"the directories hold {total}")
    # Anchored to the list that follows the total, not to the first "N injected" in the document:
    # the loose form matched "180 injected cells" forty lines earlier and reported a false drift.
    listing = text[stated_total.end():stated_total.end() + 200]
    for sub, n in counted.items():
        m = _re.search(rf"(\d+) {sub}\b", listing)
        if not m:
            problems.append(f"data/README.md gives no count for {sub}")
        elif int(m.group(1)) != n:
            problems.append(f"data/README.md says {m.group(1)} {sub}, the directory holds {n}")
    return len(counted)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--glob", default="data/*/datasets*.json",
                   help="manifests to check, relative to the working directory")
    args = p.parse_args()

    manifests = sorted(expand(args.glob))
    if not manifests:
        sys.exit(f"no manifest matched {args.glob}")

    problems, checked, unsound = [], 0, set()
    for man in manifests:
        for ds in json.loads(man.read_text()).get("datasets", []):
            checked += 1
            before = len(problems)
            # An absolute path in a manifest is a defect, not a style: it binds the file to one
            # machine under one home. All 180 entries of data/injected/datasets.json named
            # /shared/home/agardette/bench, and this check tolerated it, so nothing said so.
            # main.nf resolves a relative path against projectDir.
            for key in ("fasta", "tax"):
                if Path(ds[key]).is_absolute():
                    problems.append(f"{man.name}:{ds['name']}: {key} is an absolute path, "
                                    f"{ds[key]}, which only resolves on one machine")
            fa = Path(ds["fasta"])
            if not fa.exists():
                problems.append(f"{man.name}:{ds['name']}: {ds['fasta']} does not exist")
                unsound.add((man.name, ds["name"]))
                continue
            n, widths = measure(fa)
            if ds.get("n_seqs") != n:
                problems.append(f"{man.name}:{ds['name']}: n_seqs says {ds.get('n_seqs')}, "
                                f"the file holds {n}")
            if len(widths) != 1:
                problems.append(f"{man.name}:{ds['name']}: not an alignment, lengths "
                                f"{min(widths)} to {max(widths)}")
            elif ds.get("aln_len") != widths.pop():
                problems.append(f"{man.name}:{ds['name']}: aln_len says {ds.get('aln_len')}")

            # One dataset can break several ways at once, so count datasets rather than
            # problems: the old arithmetic reported minus 371 sound out of 196.
            if len(problems) > before:
                unsound.add((man.name, ds["name"]))

    n_aln = check_alignment_model(problems)
    n_data = check_data_readme(problems)
    n_links = check_symlinks(problems)
    n_prov = check_provenance(problems)
    n_sub = check_subsets(problems)
    n_ref = check_staged_reference(problems)
    print(f"{checked} datasets in {len(manifests)} manifests checked, "
          f"{checked - len(unsound)} sound; the covariance model and {n_aln} alignment widths "
          f"against it; {n_data} generated-file counts against data/README.md; {n_links} links "
          f"under data/ checked for being relative and resolving; {n_prov} provenance "
          f"figures in assets/datasets.yml against what the repository holds; {n_sub} size subsets "
          f"for taking whole species groups; {n_ref} digest(s) in "
          f"assets/staged_check_reference.sha256 against the files they name")
    for pb in problems:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
