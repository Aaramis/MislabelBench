# Running the benchmark on a cluster

Everything runs as a Nextflow workflow. Each tool is pinned by container and each dataset by sha256
(`assets/datasets.yml`). There is no conda environment to build. The Slurm scripts in `slurm/` were
written for the IFB core cluster and use Singularity. Another Slurm site needs its own account,
partition and node constraint in `slurm/prelude.sh`.

## Setup

```bash
export BENCH_ROOT=/path/to/a/working/copy      # the scripts default to the repository they sit in
export BENCH_REMOTE=user@cluster               # only for bin/push_code.sh, repatriate.sh, restore_cluster.sh
```

`bin/push_code.sh` copies the code to the cluster. `bin/repatriate.sh` brings the runs back.
`bin/restore_cluster.sh` rebuilds a cluster working copy from this repository: code, kept datasets,
every generated cell from its seed, and the container images. `--dry-run` prints the plan. It refuses to
run against a directory that already holds results.

## Order

The first five scripts regenerate the datasets from their seeds. They need neither the cluster nor a
container nor the network, and take a couple of minutes.

```bash
bash slurm/make_grid.sh                        # the injection grid, 180 cells
bash slurm/make_foreign.sh                     # error kind 6, foreign sequences
bash slurm/make_clade.sh                       # error kind 3, whole-taxon relabelling
bash slurm/make_simulation.sh                  # simulated control, 37 cells
bash slurm/make_chimera.sh                     # chimeras
```

Run all of them. `bin/analyses.sh` stops at its truth checks if a dataset was never built.
[`data/README.md`](../data/README.md) says what is kept and what is regenerated, and how to check that
the regenerated cells are byte-identical.

The control on a real tree is separate because it needs outside material.

```bash
slurm/submit.sh slurm/fetch_grove.sh           # RAxML Grove, pinned by sha256 and by commit
slurm/submit.sh slurm/make_grove_simulation.sh # the control on an empirical tree, 37 cells
```

It needs the 140 MB Grove database, network access, the AliSim binary that ships inside the pinned
Grove scripts, and a Python with biopython and scikit-optimize (`GROVE_PY`).

Then the measurements. Each script is one experiment, listed in [reproduce.md](reproduce.md).

```bash
slurm/submit.sh slurm/baseline.sh              # both tools on the unmodified database, timed
slurm/submit.sh slurm/grid_fork.sh             # SATIVA-epang over the grid
bin/analyses.sh                                # rebuild every table, then run every check
```

`slurm/submit.sh` excludes the nodes listed in `slurm/bad_nodes.txt`, which jobs append to when they
land on a node without Singularity. Start from `slurm/bad_nodes.txt.example`.

## Without a cluster

```bash
python3 -m unittest discover -s tests
bash tests/smoke.sh
```

`tests/smoke.sh` runs the workflow with `-stub-run`, which replaces every tool with a few `touch` commands.
It exercises the grid, the joins and the shard split and nothing else. It caps the resource requests so
that it starts on a laptop.

## Rules the scripts enforce

**A timed run pins the CPU model.** The cluster mixes processor generations, and the oldest has about
half the per-core speed of the newest. The `--constraint` is therefore required for timed runs, and
`cpu_model` is written into `run.json`. Untimed runs, which answer detection questions, do not pin.

**No run takes a whole node.** `--exclusive` is charged all 510 cores of an epyc-9754 node against a
600-core cap per user, so rounds that use several nodes cannot be exclusive. The spread over replicates
bounds the interference instead.

**A timed run has the harness to itself.** `executor.queueSize = 1` when `params.timed`. `maxForks` is
per process and would let SATIVA and SATIVA-epang run side by side.

**A run that is not trusted says so.** `--timing_trusted false` is recorded in `run.json`, and no
figure reads seconds from such a run.
