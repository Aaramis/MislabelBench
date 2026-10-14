# MislabelBench

A benchmark for tools that find mislabelled sequences in a taxonomic reference database.

It starts from a real database, GTDB r226 archaeal 16S rRNA, and changes labels on purpose. The errors
are therefore known, and everything else is real. Seven error types cover a single wrong label, several
sequences sharing one wrong label, a wrong species in the right genus, a whole taxon misnamed, incomplete
lineages, sequences from another domain and chimeras. The core is 180 datasets, which vary the distance
between the true and the false label, the number of sequences carrying it, the share of the database
altered and the seed. A control on sequences simulated along a RAxML Grove tree checks what
a real database cannot, and one bacterial order checks that the findings hold on another domain.

It was built to compare [SATIVA](https://github.com/amkozlov/sativa) (Kozlov *et al.* 2016) with
[SATIVA-epang](https://github.com/Aaramis/sativa-epang), the same method with EPA-ng
(Barbera *et al.* 2019) as the placement engine. Any other method can be scored on the same data, see
[docs/adding-a-method.md](docs/adding-a-method.md).

## What it found

SATIVA-epang runs about 11 times faster than SATIVA on 7 051 sequences, and its leave-one-out can be
split in independent batches across machines. The price is memory, about 36 GB against less than 1 GB at
eight threads. On datasets with 5 % of the labels changed it finds 28 % more of the injected errors,
more in 119 of the 180 datasets, fewer in 8. The gain comes from the case where several sequences share
the same wrong label. More than half of the errors escape both tools. Numbers, tables and the
reasoning are in [docs/results.md](docs/results.md) and in the paper's supplement.

## Quick start

Nothing below needs a cluster or a container. Python 3.12 and the standard library are enough.

```bash
git clone https://github.com/Aaramis/MislabelBench && cd MislabelBench
python3 -m unittest discover -s tests          # the analysis layer's tests
for g in make_grid make_foreign make_clade; do bash slurm/data/$g.sh; done
bin/analyses.sh                                # rebuild every table from the committed runs, then run every check
```

The 180 datasets are rebuilt from their seeds in about a minute. `bin/analyses.sh` exits 0 when every
table matches its runs and every check passes. To rerun the experiments themselves, see
[docs/cluster.md](docs/cluster.md), and for the map from each result in the paper to its script,
[docs/reproduce.md](docs/reproduce.md).

## Layout

| path | content |
|---|---|
| `data/` | base datasets, alignments, injected ground truth, manifests. See [docs/data.md](docs/data.md) |
| `results/` | every run and every table built from them. See [results/README.md](results/README.md) |
| `bin/` | `analyses.sh` runs them all. In `data/` the preparation and injection, in `analysis/` the scoring and tables, in `verify/` the checks, in `figures/`, `timing/` and `ops/` the rest |
| `slurm/` | one script per experiment, grouped by kind, with the `make_*.sh` generators in `data/` |
| `main.nf`, `modules/`, `conf/`, `nextflow.config` | the Nextflow workflow, one container per tool |
| `assets/` | `datasets.yml` (every source with URL and sha256) and `containers.yml` (every image with digest) |
| `tests/` | unit tests and a stub run of the workflow |
| `docs/` | usage, cluster, data, results, reproduction, distribution |

## The seven error types

| kind | what is changed | datasets |
|---|---|---|
| 1 | one sequence gets a wrong label | the grid, *k* = 1 |
| 2 | *k* sequences share the same wrong label | the grid, *k* = 2 to 10 |
| 3 | a whole taxon is renamed | `data/clade/` |
| 4 | right genus, wrong species | the grid, species distance |
| 5 | lineages of other sequences are cut short | `data/ragged/` |
| 6 | a bacterial sequence gets an archaeal label | `data/foreign/` |
| 7 | a chimera of two sequences carries one parent's label | `data/chimera/` |

In the grid, the label is wrong at six taxonomic distances from the true one, from species to phylum,
for 1 % or 5 % of the database, with *k* sequences per wrong label and three seeds. Each dataset ships
a `truth.json` that records what was changed. A tool must not read it.

## Scoring a method

A method reads an alignment and a taxonomy and writes a SATIVA-style `.mis` table. Scoring needs one
command.

```bash
python3 bin/analysis/score_injection.py --truth data/injected/inj_class_r0.01_k1_s1/inj_class_r0.01_k1_s1.truth.json \
  --mis my_method.mis --out score.json
```

[docs/adding-a-method.md](docs/adding-a-method.md) gives the file formats and how to put a method
inside the workflow. To run SATIVA-epang itself, see [docs/usage.md](docs/usage.md).

## Reproducibility

Every tool runs in a container pinned by tag and registry digest, and every input is pinned by sha256.
The datasets are deterministic from their seeds, and `bin/verify/verify_regeneration.py` checks that a rebuild
is byte-identical to the committed files. At fixed dataset and seed the workflow gives the same `.mis` on
three CPU models. Timed runs pin one CPU model and the seconds are comparable only within it.

## Licence

Code is under the [MIT licence](LICENSE). Data, results and documentation are under
[CC BY-SA 4.0](LICENSE-DATA), which follows the GTDB sequences they derive from. Upstream terms for each
source are in [docs/data.md](docs/data.md).

## Citation

If you use the benchmark, cite the paper and the archived release. [CITATION.cff](CITATION.cff) holds the
reference.

The release is archived on Zenodo. The code is at DOI 10.5281/zenodo.23371116 (all versions; v1.1 is
10.5281/zenodo.23378298 and v1.0 is 10.5281/zenodo.23371117). The full runs, with the placement files that are too large for git, are at
DOI 10.5281/zenodo.23373680.
