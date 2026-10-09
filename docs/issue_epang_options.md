# Draft issue for Aaramis/sativa-epang (not posted; for the maintainer to open)

**Title:** Expose EPA-ng's heuristic options, and SATIVA's `epa_use_heuristic`, for the engine comparison

**Body:**

In the benchmark for the application note, sativa-epang and SATIVA disagree on a small set of
sequences under strict leave-one-out: on six injected cells of a 2,023-sequence archaeal reference,
84 injected sequences are flagged by sativa-epang only and 4 by SATIVA only (82 and 4 distinct). Both
read the same alignment and taxonomy; only the placement engine differs. When one of those sequences
is the only wrong label in the reference, both engines flag it at the same confidence to three
decimals, at every reference size tried; the difference appears only when the reference carries
several wrong labels at once.

A co-author who wrote RAxML-EPA suggests the difference is in the engines' algorithmic shortcuts, and
asks us to vary EPA-ng's heuristics and compare placements where results deviate. Two things make
that impossible from outside today:

1. `epac/epang_l1o.py` builds the EPA-ng command line itself and the fork exposes only
   `SATIVA_L1O_ENGINE`, `SATIVA_EPANG_FOLDS` and `SATIVA_EPANG_FOLD_ORDER`. There is no way to pass
   `--no-heur`, `--baseball-heur`, `--dyn-heur <x>` or `--fix-heur <x>` through.
2. Upstream SATIVA runs RAxML-EPA heuristically above 1,000 leaves (`epa_use_heuristic=auto`, rate
   `0.5 * 1000 / n`, so 0.247 at 2,023 sequences). The symmetric comparison needs `FALSE` on that
   side, which is a `sativa.cfg` key the fork could expose the same way.

**Requested:**

- A `SATIVA_EPANG_ARGS` environment variable (or a `-epang-args` flag) whose contents are appended to
  every EPA-ng invocation verbatim, recorded in the task directory's `manifest.json` beside the
  command it already records.
- Documentation of which EPA-ng heuristic the fork uses by default, so that the benchmark can state
  what the current numbers were measured under.

The benchmark's harness already fails a condition whose knob does not reach the tool
(`bin/verify_conditions_differ.py`), so a release with this can be tested the day it lands. Planned
for the 1.0.0 release before the application note is submitted; not blocking the current benchmark,
which compares the placements themselves on the deviating sequences in the meantime.
