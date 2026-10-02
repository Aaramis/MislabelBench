# Version 1 of the benchmark

These scripts are the first benchmark, on ITS data, driven by shell over four hand-built conda
environments. `RESULTS.md` reports their numbers, which is why they are kept.

**They are not what the current harness runs.** That is Nextflow, with each tool pinned by container
and build string; see the top-level `README.md`. Where the two disagree, as on detection, the current
one supersedes this: it has three seeds, 180 cells and replicated timings where this had one run per
condition.

## Scripts

| | |
|---|---|
| `01_make_datasets.py` | Nested random subsets of one alignment, as SATIVA's `.fasta` + `.tax`. `--ascii-taxonomy` transliterates taxon names, which the 2017 python 2 SATIVA needs. |
| `02_bench.py` | One measured run of one condition. Owns the condition table: which SATIVA, which engine, threads, folds, environment overrides. |
| `03_plot.py` | `summary.tsv` and the three-panel figure. |
| `04_run_all.sh` | Every measurement in `RESULTS.md`, in five phases. About 3 h on 32 cores. |
| `05_concordance.py` | Which sequences each version flags, against a reference run. `--details` writes one row per disagreement. |
| `06_cutoff_sensitivity.py` | The same agreement at stricter confidence cutoffs, from the `.mis` files on disk. |
| `07_injected_mislabels.py` | `build` writes datasets with known wrong labels, `score` reads the runs back. |
| `08_build_report.py` | Renders `RESULTS.md` into `results/report.html`, figure inlined. |
| `_timeit.py` | Runs one command in its own process group, reporting wall time and peak RSS. Still used, unchanged, by the Nextflow modules. |

## Setup

The two unmodified references are git checkouts of `amkozlov/sativa`:

```bash
(cd sativa_epang/raxml && make)                                                  # RAxML 8.2.3
git clone https://github.com/amkozlov/sativa.git env/sativa_upstream             # v0.9.3, python 3
git -C env/sativa_upstream worktree add --detach ../sativa_upstream_py2 8c31962   # last python 2 commit
cp sativa_epang/raxml/raxmlHPC8-* env/sativa_upstream/raxml/
cp sativa_epang/raxml/raxmlHPC8-* env/sativa_upstream_py2/raxml/
mkdir -p env/sativa_upstream/tmp env/sativa_upstream_py2/tmp
conda create -y -n sativa_py2 -c conda-forge python=2.7
conda create -y -n sativa_epang -c conda-forge -c bioconda python=3.10 ete3 epa-ng=0.3.8
```

Copying the RAxML binaries matters: all three versions must call the same ones, so the comparison
never changes binary.

Site-specific paths go in `config.local.sh`, which `config.sh` sources if present and `.gitignore`
skips:

```bash
SATIVA_BENCH_PY3_ENV="/path/to/conda/envs/sativa_epang"      # python 3, ete3, epa-ng
SATIVA_BENCH_PY2_ENV="/path/to/conda/envs/sativa_py2"        # bare python 2.7
SATIVA_BENCH_PLOT_PY="/path/to/conda/envs/plot/bin/python"   # matplotlib, markdown, pillow
SATIVA_BENCH_SOURCE_MSA="/path/to/alignment.fasta"
```

## Running

```bash
source config.sh
"$PY3" scripts/01_make_datasets.py --source "$SOURCE_MSA" --outdir data_ascii \
       --sizes 100,200,400,800,1600,full --seed 42 --ascii-taxonomy
./scripts/04_run_all.sh
"$PY3" scripts/07_injected_mislabels.py build
"$PY3" scripts/02_bench.py --datasets-json data_injected/datasets.json \
       --runs-dir results/runs_injected --datasets all \
       --conditions upstream_py3_raxml_T1,port_py3_epang_T8,port_py3_epang_T8_K25 \
       --repeat 1 --untimed
"$PY3" scripts/07_injected_mislabels.py score
```

Two rules this runner enforced, both of which the Nextflow harness kept.

**Timed runs work on local disk.** The project lived on a network filesystem where 200 MB took 14.0 s
to write against 0.14 s locally. Measured there the same run varied by 60 %, locally by 2 %.
`02_bench.py` puts the working directory and SATIVA's `-tmpdir` under `--scratch` and copies back only
`.mis` and `.log`.

**Timed runs do not share the machine.** Runs answering an agreement question pass `--untimed`, which
records `timing_trusted: false`; `03_plot.py` refuses to draw those seconds.

## Adding a condition

Conditions live in one table at the top of `02_bench.py`:

```python
"port_py3_epang_T8_K25": {"impl": "port", "engine": "epang", "threads": 8, "folds": 25},
"upstream_py3_raxml_T8_gamma": {"impl": "upstream_py3", "engine": "raxml", "threads": 8,
                                "cfg": {"raxml_model": "GTRGAMMA",
                                        "epa_use_heuristic": "FALSE"}},
```

The environment variables the EPA-ng version understands are in `sativa_epang/PROVENANCE.md`.
