# Data

## Sources

| source | version | used for | licence |
|---|---|---|---|
| GTDB SSU, `ssu_all_r226.fna.gz` | r226 | the archaeal database, and the bacterial donors and clade | CC BY-SA 4.0 |
| Rfam covariance models | 15.1 | RF01959 (archaea) and RF00177 (bacteria), the alignment model | CC0 |
| Infernal | 1.1.5 | `cmalign` and `cmfetch`, run from a container | BSD-3-Clause |
| RAxML Grove | database of 2026, tree 71741 | the tree and model of the simulated control | none stated upstream |

`assets/datasets.yml` gives each source's URL, sha256, download date, record counts and the rule that
selects sequences. `bin/verify_inputs.py` and `bin/verify_manifests.py` check the files in `data/`
against it.

## From the database to a dataset

1. `bin/prepare_gtdb.py` keeps archaeal sequences of at least 1 200 nt, 7 051 of the 13 754 in the
   domain, and aligns them with `cmalign --matchonly` on RF01959. The alignment has 1 478 columns.
2. `bin/subset_taxa.py` draws the 2 023-sequence set the grid uses, by whole taxa so that the share of
   judgeable sequences stays close to the full set.
3. The injection scripts rewrite labels with a fixed seed. Each dataset records what was injected in its
   `truth.json`, and `bin/verify_injection.py` checks the file against the taxonomy.

The 7 051-sequence set is the headline for time and memory. The 2 023-sequence set carries every
detection result.

## What is committed and what is regenerated

`data/README.md` lists both. In short, the base sets, the alignment, the covariance model, the manifests
and the ground truth are committed. The 180 injected taxonomies, the foreign and chimera cells are
rebuilt from their seeds by the `slurm/data/make_*.sh` scripts, and `bin/verify_regeneration.py` compares the
rebuilt files with the committed ones. The raw GTDB download is fetched by URL and checked by sha256.

## Licence

`data/`, `results/` and `assets/` are CC BY-SA 4.0, see [LICENSE-DATA](../LICENSE-DATA). That follows
from GTDB. The Grove database states no licence. Only the one tree used for the control and its model
parameters are kept here, and the database itself is fetched from its host.
