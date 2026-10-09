#!/bin/bash
# Which node did each placement shard run on?
#
#   slurm/shard_nodes.sh results/staged_timed_f7_r1
#
# This is what --exclusive used to guarantee and the QOS will not allow: an exclusive job is charged
# all 510 cores of an epyc-9754 against a 600-core cap, so two shards could never both have it. Two
# shards on one node is the one disturbance that would corrupt the measurement rather than add noise
# to it, so it has to be recorded rather than assumed.
#
# Nextflow's `hostname` trace field is empty under the Slurm executor on this cluster -- checked on
# three rounds, every row blank -- so the node is recovered the only way that works here: a trace's
# native_id *is* the Slurm job id under -profile ifb, and sacct knows where each job ran. Under
# -profile singularity native_id is a process id instead and this script would resolve nonsense, so
# it refuses a round whose ids do not look like job ids.
#
# bin/staged_scaling.py reads the file this writes. Run it on the cluster, after the round.
set -euo pipefail
dir="${1:?usage: shard_nodes.sh <round directory>}"
info="$dir/pipeline_info"
[ -d "$info" ] || { echo "no $info" >&2; exit 1; }

# Named after the trace it was resolved from, because bin/repatriate.sh flattens every round's
# pipeline_info into one results/pipeline_info and an untagged name would have nine rounds overwrite
# each other there.
# The newest trace by the job id in its name, not the first one ls returns. A round resubmitted
# after a cancelled attempt holds one trace per attempt in the same directory -- three for the
# second pinned round -- and resolving all of them lists every attempt's shards as if they were one
# round's, seven shards for four and the verdict "shared". The attempt that completed is the last.
trace=$(ls "$info"/trace-*.txt | sed 's/.*_\([0-9]*\)\.txt$/\1 &/' | sort -n | tail -1 | cut -d' ' -f2)
tag=$(basename "$trace" .txt | sed 's/^trace-//')
out="$info/shard_nodes-$tag.tsv"
python3 - "$info" "$out" "$trace" <<'PY'
import csv, glob, os, re, subprocess, sys
info, out, trace = sys.argv[1], sys.argv[2], sys.argv[3]
rows = []
for p in [trace]:
    for r in csv.DictReader(open(p), delimiter="\t"):
        if "LOOPLACE" not in (r.get("name") or "").upper() or r.get("status") != "COMPLETED":
            continue
        nid = (r.get("native_id") or "").strip()
        m = re.search(r"shard (\d+)/(\d+)", r["name"])
        if not nid.isdigit() or not m:
            continue
        rows.append((nid, m.group(1), m.group(2), r["name"].split(" (")[1].split(" shard")[0]))
if not rows:
    sys.exit("no completed placement shards with a numeric native_id in " + info)
ids = ",".join(r[0] for r in rows)
acct = subprocess.run(["sacct", "-j", ids, "-o", "JobID,NodeList", "-P", "-n"],
                      capture_output=True, text=True).stdout
node = {}
for line in acct.splitlines():
    jid, _, nl = line.partition("|")
    if jid and "." not in jid and "_" not in jid:
        node[jid] = nl.strip()
missing = [r[0] for r in rows if r[0] not in node]
if missing:
    sys.exit(f"sacct does not know {len(missing)} of {len(rows)} shard jobs, e.g. {missing[0]}: "
             "either this round ran under -profile singularity, where native_id is a process id, "
             "or accounting has aged it out")
with open(out, "w") as fh:
    fh.write("cell\tshard\tn_shards\tjob\tnode\n")
    for nid, shard, n, cell in sorted(rows, key=lambda r: (r[3], int(r[1]))):
        fh.write(f"{cell}\t{shard}\t{n}\t{nid}\t{node[nid]}\n")
print(f"{len(rows)} shard(s) resolved into {out}")
seen = {}
for nid, shard, n, cell in rows:
    seen.setdefault(cell, []).append(node[nid])
for cell, nodes in seen.items():
    verdict = "one shard each" if len(set(nodes)) == len(nodes) else "SHARED"
    print(f"  {cell}: {', '.join(sorted(nodes))} -> {verdict}")
PY
