# Contributing

Issues and pull requests are welcome, in particular a new method scored on the benchmark.

**Before a pull request**

```bash
python3 -m unittest discover -s tests
bin/analyses.sh
```

`bin/analyses.sh` rebuilds every table in `results/` and runs every check. It should exit 0 and leave
`git status results/` showing only the files your change is meant to alter.

**A new method.** Follow [docs/adding-a-method.md](docs/adding-a-method.md). Send the `.mis` files, the
`score.json` of the 180 datasets and of the unmodified database, the command and the version of the tool.
A method that cannot be run here can still be listed if its outputs are given.

**A new error type or dataset.** Add the generator under `bin/`, a `slurm/data/make_*.sh` that builds the cells
from a seed, a `verify_*` check against the declared truth, and the source in `assets/datasets.yml`
with its sha256.

**Style.** Scripts use only the Python standard library. A script's header says what it reads and writes.
Comments say why, not what. Results are never edited by hand.

By contributing you agree that code is released under MIT and data under CC BY-SA 4.0.
