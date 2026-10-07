# Inputs

What is here is what cannot be regenerated without the cluster, plus everything small. What is not
here is regenerable, and that claim is checked rather than asserted.

## Kept

| | |
|---|---|
| `gtdb/gtdb_arc*.fasta`, `gtdb/gtdb_arc*.tax` | the archaeal base datasets and their size subsets. `gtdb_arc1200.aligned.fasta` is the Infernal alignment, which costs an hour and a covariance model to rebuild |
| `gtdb/RF01959.cm` | the Rfam covariance model the alignment uses, so the alignment step does not depend on Rfam staying reachable |
| `gtdb/*.subset.json`, `gtdb/datasets*.json` | which sequences each subset took and with which seed |
| `bacteria/donor_pool.*` | the bacterial donors for the foreign-sequence condition, aligned against the same model |
| `injected/*/\*.truth.json`, `foreign/*/\*.truth.json` | the ground truth every detection number is scored against |
| `injected/datasets.json`, `foreign/datasets.json` | the manifests the harness reads |

## Not kept

**`raw/ssu_all_r226.fna.gz`**, 73 MB. Fetched by URL with its sha256 recorded in
`assets/datasets.yml`, which is a stronger guarantee than a copy in git.

**The per-cell `warn.txt`**, one per generated cell. Each generator redirects its stderr there, and
225 of them were committed -- every one empty, while a full regeneration writes a real note into
**90 of the 180 injected cells**: whole groups of *k* cannot be split, so a cell asked for 101
injections at rate 0.05 and *k*=10 gets 110, an effective 5.44 %. A committed file asserting that no
cell warned, where half of them do, is worse than no file. The note is a transcript of a run; the
record is `truth.json`, which carries `n_requested`, `n_injected` and `rate_effective` for every cell
and is checked by `verify_injection.py`.

**`*.pfam`**, 23 MB. The Pfam-format output of `cmalign`; `*.aligned.fasta` is the same alignment in
the form everything downstream reads.

**The per-cell `.tax` and `.fasta` of the 180 injected cells**, 58 MB of `.tax` and 180 symlinks. Each is the base taxonomy with
a few hundred labels rewritten, and `slurm/make_grid.sh` rebuilds all 180 from their seeds in under
a minute with no cluster and no container. The alignment is shared, so each cell's `.fasta` was only
ever a symlink to the base.

Checked, because "reproducible from the seed" is the sort of claim that is usually almost true:
regenerating the grid on macOS under python 3.14 gives `.tax` files whose md5 matches the python
3.12 Linux ones byte for byte, and `truth.json` files identical in all 180 cells. The only
field that moved was
`source`, which recorded the absolute path of the input and therefore could not match between two
machines; it now records the input's name and sha256, which can.

That check named the `.tax` and the `truth.json` and stopped there, which is narrower than what it is
used to license: a cell also carries a `.fasta`, and that is the file SATIVA reads. It is now
`bin/verify_regeneration.py`, run by `bin/analyses.sh` rather than by hand: a root holding nothing but
the kept inputs above, the four generators run into it, and every file they write compared with this
tree's. **719 files, 719 identical**, in 18 seconds, no cluster and no container. Counting only what
the experiments themselves consist of, without the manifests and the ground truth, that is
**481 files -- 360 injected, 18 foreign, 27 clade, 76 simulated**.

It is run that way because the way it was run before could not work. It was run from a fresh clone
"with nothing but the generators", and a fresh clone is where two of the four experiments are not
regenerated at all: the clade and simulated cells **are** committed, every generator skips a cell whose
`.tax` is already there, so for 103 of those files the check compared git's content with itself. Their
reproducibility was unmeasured until the cells were deleted and rebuilt, which they now are, in a tree
that is not this one. They do come back byte for byte.

The caveat that keeps the number honest: **225 of the 235 regenerated `.fasta` are symlinks** to a base
alignment, because injection rewrites a taxonomy and never an alignment. A link is therefore compared by
its target and not by the bytes it points at -- comparing those compares one file with itself, which is
how 45 committed links stayed absolute and unnoticed, naming
`/Users/auguste/Documents/git/sativa-epang-benchmark` in every clone on every other machine. The ten
real `.fasta` are the nine foreign cells and the simulated reference, and those are where a content
comparison bites.
