# Publishing this folder

> **Version 1 is already public, and this file used to open by saying nothing was.** `origin` is
> `https://github.com/Aaramis/sativa-epang-benchmark`, `origin/main` holds 8 commits, and GitHub's
> default branch is `main`. Local `main` and `origin/main` are identical, 0 commits either way. So the
> instructions this file used to give -- add the remote, push `main` -- describe a state that ended
> some time ago.
>
> **One published claim is refuted and the refutation is not public.** `RESULTS.md` on `main` reports
> that unmodified SATIVA finds 28 of 33 injected mislabels and the EPA-ng version 33 of 33, and
> explains the gap by shared wrong labels that "a strict leave-one-out cannot see and a fold can". The
> 180-cell grid with three seeds does not bear that out: recall falls with the number of carriers for
> both tools alike, 0.94 at *k*=1 to 0.13 at *k*=10, and the fold scheme is worth 0.035 and only at
> *k*=10. `RESULTS.md` on the `nextflow` branch carries that refutation in a banner at the top of the
> file. On `main` it does not, so a reader of the public repository sees the refuted claim and no
> correction beside it.
>
> **This cannot be fixed from here.** The fix is a push, and nothing in this repository is pushed
> without explicit agreement. The branch is ready: `nextflow` is 201 commits ahead of `origin/main`
> and contains all of its history, so it is a fast-forward and not a rewrite.

## What is where

| | |
|---|---|
| `origin/main`, public | version 1: the ITS measurements, `scripts/`, the vendored `sativa_epang/`, `RESULTS.md` with no banner |
| `nextflow`, local only | the Nextflow harness, the GTDB grid, `REVIEW.md`, and `RESULTS.md` with its banner |

## Decisions to take before any of it goes out

**The refuted claim.** Either `main` moves to `nextflow`, or the banner is cherry-picked onto `main`,
or the repository is left as it is deliberately. The first is the cheapest, being a fast-forward, and
the only one that also publishes the work that did the refuting.

**The version 1 machinery still in the tree.** The plan says `sativa_epang/` is deleted because the
tool now comes from bioconda, and that `config.sh` and `04_run_all.sh` disappear. All of it is still
tracked on `nextflow`: `scripts/` 12 files, `sativa_epang/` 34, `data_ascii/` 13, `data_injected/` 37,
`config.sh` 1 -- 97 files, about 6 MB. Two parts are load-bearing and must not simply be removed:
`slurm/m1_check.sh` builds its comparison from `data_ascii/` and from the version 1 run under
`results/runs/`, which is what shows the harness reproduces version 1's answer byte for byte. The rest
is an open decision rather than an oversight.

**Sequence redistribution.** `data_ascii/` and `data_injected/` hold about 5 MB of ITS sequences drawn
from the curated database. The question is unchanged from version 1 and still open. It now also bears
on `m1_check.sh`, which cannot run without `data_ascii/`.

**Licence.** `LICENSE` is GPL 3, which SATIVA requires. It still applies while `sativa_epang/` is in
the tree: that is a modified copy of GPL 3 code and `sativa_epang/PROVENANCE.md` states the
modifications, as the licence asks. If the directory goes, this question goes with it, because the
harness calls bioconda containers and vendors nothing.

**Cluster paths in the records.** `config.local.sh` and `env/` are gitignored and no longer exist, and
the version 1 runs were rewritten by `scripts/10_sanitise_paths.py`. For version 2 the question is
narrower than it looks. `git grep -l '/shared/home\|/home/agardette'` matches **2 436 files under
`results/`** -- run logs and records where the tool printed its own absolute paths -- and exactly four
anywhere else: `REVIEW.md`, this file, a comment in `bin/verify_manifests.py` and a comment in
`slurm/make_grid.sh`, all four quoting a path deliberately to explain something. No code depends on
one; the two in comments were opened and read rather than counted. (The count here excludes nothing and
includes this file, which is why it is quoted as 2 436 under `results/` and four elsewhere: a single
total changes when this paragraph is edited.) So this is a decision about whether published logs
should carry the cluster's layout, not a portability bug. The one place a path *was* a dependency was
`truth.json`, which recorded the absolute path of its input in all 180 cells and now records the
input's name and sha256; that is finding 22 of `REVIEW.md`.

## The fork

Prepared in `../sativa-epang`. Fork `amkozlov/sativa` on GitHub first, then:

```bash
cd ../sativa-epang
git remote add fork git@github.com:Aaramis/sativa-epang.git
git push fork epa-ng
```

The branch holds one commit on top of v0.9.3 (`68284c2`), so GitHub shows the whole modification as a
single readable diff: two hunks in `sativa.py`, one in `epac/config.py`, one new `epac/epang_l1o.py`,
one config line. `CHANGES-epa-ng.md` at the root of the branch explains it and links back to this
benchmark. Whether that is still accurate has not been rechecked: the fork is a separate repository and
outside the review this file sits next to.

## Repository description and topics

The public description names only what version 1 measured. What version 2 adds and it omits:
distribution across jobs, which upstream cannot do at any price, and what the fork's
`OriginalLabelExclusion` column is worth -- it explains a third of the calls and does not rank them.

Description: *Does replacing SATIVA's placement engine with EPA-ng change its answers? Speed,
agreement, a ground-truth mislabel grid, distribution across jobs, and what the new confidence column
is worth.*

Topics: `sativa`, `epa-ng`, `phylogenetic-placement`, `taxonomy`, `benchmark`, `reference-database`,
`nextflow`.
