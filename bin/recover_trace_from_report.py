#!/usr/bin/env python3
"""Pull the task records out of a Nextflow HTML report, for a run whose trace was not written.

A job resubmitted after a failure finds its predecessor's trace file already there, warns once and
writes nothing, so the run that actually produced a result can leave no trace at all. The report
and timeline are written at completion under the same tag and do get created, and the report
embeds the same records as JSON under `window.data`. This is the only way back to them.

The embedded JSON holds the task scripts, whose shell escapes are not valid JSON escapes, so they
are stripped before parsing. Nothing is read from them here.

Nothing calls this and nothing can: the one report it was run on,
results/grid_fork/pipeline_info/report-kexact_k2.html, is gone from both the repository and the
cluster. It was overwritten by a later Kexact run writing the same untagged name, which is exactly the
collision that per-tag naming in nextflow.config now prevents and that this script existed to repair.
Six reports survive on the cluster and all six are per-tag.

So trace-kexact_k2_recovered.txt cannot be re-derived, and the numbers it carries do not rest on it
alone: the five sibling Kexact runs, each with its own committed trace, peak at 9.2 to 9.7 GB against
its 9.83, and the cell's own run.json gives a wall clock of 4 257.74 s against its 4 259.3. The script
is kept rather than deleted because reports are still written and a lost trace is still repairable.
"""

import json
import re
import sys

# Not pcpu: it is empty for the fork-grid tasks in report-grid_fork.html and carried an
# uninterpretable 982648 for the Kexact one, so there is no unit to report it in. peak_rss is
# calibrated: the report gives 9968144384 for a task the text trace records as 9.3 GB, so the
# report's figure is bytes and the two measure the same thing. submit is epoch milliseconds,
# duration and realtime are milliseconds.
FIELDS = ("process", "name", "status", "exit", "submit", "duration", "realtime",
          "peak_rss", "peak_vmem", "container")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: recover_trace_from_report.py <report-*.html>")
    html = open(sys.argv[1], errors="replace").read()
    start = html.find("window.data = ")
    if start < 0:
        sys.exit("no window.data in this report")
    start += len("window.data = ")
    depth, end = 0, None
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        sys.exit("window.data is not a closed object")
    data = json.loads(re.sub(r'\\(?!["\\/bfnrtu])', "", html[start:end]), strict=False)
    rows = data.get("trace", [])
    if not rows:
        sys.exit("the report holds no task records")
    print("\t".join(FIELDS))
    for r in rows:
        print("\t".join("" if r.get(k) is None else str(r.get(k, "")) for k in FIELDS))


if __name__ == "__main__":
    main()
