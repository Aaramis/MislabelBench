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

**The per-cell `.tax` and `.fasta` of the 180 injected cells**, 56 MB. Each is the base taxonomy with
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
used to license: a cell also carries a `.fasta`, and that is the file SATIVA reads. Rerun from a fresh
clone with nothing but the two `make_` scripts, **all 378 regenerated files are byte-identical** --
180 injected `.tax`, 180 injected `.fasta`, and both for the nine foreign cells, which the earlier
check did not cover either. The 180 injected `.fasta` are *symlinks* to `gtdb_arc2k.fasta`, because
injection rewrites a taxonomy and never an alignment, so comparing them compares one file to itself
180 times; what the check establishes for those is that the link is remade and points where it should.
The nine foreign `.fasta` are real files and are the ones that comparison bites on.
