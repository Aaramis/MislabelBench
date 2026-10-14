#!/usr/bin/env python3
"""Check every run record's timing_trusted against what its job script asked for.

The flag decides whether a figure may read a run's seconds, so a wrong one is silent and
dangerous: 737 of 949 records said true when their job had passed --timing_trusted false,
because the string "false" arriving from the command line coerced to a true Groovy boolean.
What protected the published tables was resource_usage.py skipping any dataset not named
gtdb*, which is a name convention and not the guard that was designed for this.

The intent is not restated here. It is read out of slurm/*/*.sh, so a script that changes its
mind is followed rather than contradicted, and two scripts writing into one outdir with
different answers is itself reported.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from _paths import expand


# The outdir may carry a shell variable -- results/staged_timed_f${FPJ} -- in which case the
# literal prefix before it is what identifies the family of directories the script writes. Without
# this the three staged_timed outdirs went unclaimed, which is harmless when their flag happens to
# be right and silent when it is not.
OUTDIR_RE = re.compile(r'--outdir\s+"\$BENCH_ROOT/results/([A-Za-z0-9_]*)(\$\{[^}]+\})?"')
TRUST_RE = re.compile(r"--timing_trusted\s+(true|false)")


def intent(slurm_dir):
    """outdir name -> {declared value: [scripts that declare it]}, from the job scripts."""
    out = defaultdict(lambda: defaultdict(list))
    for script in sorted(Path(slurm_dir).rglob("*.sh")):
        # errors="replace" because *.sh also matches ._baseline.sh and the like: AppleDouble
        # resource forks, which an rsync from a Mac leaves beside every file it copies and which
        # are binary. They match neither regex below, so tolerating them is the whole fix; dying
        # on one stopped the gate from running at all on the cluster.
        text = script.read_text(errors="replace")
        od, tr = OUTDIR_RE.search(text), TRUST_RE.search(text)
        if od and tr:
            # A trailing variable makes this a prefix claim rather than an exact name.
            key = od.group(1) + ("*" if od.group(2) else "")
            out[key][tr.group(1) == "true"].append(script.name)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--glob", default="results/*/runs/*/run.json")
    p.add_argument("--slurm", default="slurm")
    p.add_argument("--fix", action="store_true",
                   help="rewrite the flag to what the job script asked for")
    args = p.parse_args()

    declared = intent(args.slurm)
    for name, values in sorted(declared.items()):
        if len(values) > 1:
            print(f"{name}: job scripts disagree, {dict(values)}", file=sys.stderr)
            sys.exit(1)

    wrong, unknown, checked, fixed = defaultdict(int), defaultdict(int), 0, 0
    for f in sorted(expand(args.glob)):
        name = f.parts[1]
        key = name if name in declared else next(
            (k for k in declared if k.endswith("*") and name.startswith(k[:-1])), None)
        if key is None:
            unknown[name] += 1
            continue
        want = next(iter(declared[key]))
        rec = json.loads(f.read_text())
        checked += 1
        if bool(rec.get("timing_trusted")) != want:
            wrong[(name, rec.get("condition"))] += 1
            if args.fix:
                rec["timing_trusted"] = want
                f.write_text(json.dumps(rec, indent=2))
                fixed += 1

    # A gate that checked nothing must not report success. verify_inputs.py printed
    # "0 cells, 0 consistent" and exited 0 when a job left the working directory at the
    # Nextflow launch dir and the relative glob matched nothing.
    if not checked:
        sys.exit(f"no run record matched {args.glob} from {Path('.').resolve()}")
    if not declared:
        sys.exit(f"no job script in {args.slurm} declares an outdir and a trust flag")
    print(f"{checked} run records checked against {len(declared)} job scripts' declarations, "
          f"{checked - sum(wrong.values())} agree")
    for name, n in sorted(unknown.items()):
        print(f"  {n} records under results/{name}, which no job script claims", file=sys.stderr)
    for (name, cond), n in sorted(wrong.items()):
        print(f"  {name}/{cond}: {n} records disagree with the script that produced them",
              file=sys.stderr)
    if args.fix:
        print(f"{fixed} rewritten")
    elif wrong:
        sys.exit(1)


if __name__ == "__main__":
    main()
