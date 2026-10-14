#!/usr/bin/env python3
"""The flags of a SATIVA .mis file, as a dict from sequence id to the rank where the label goes wrong."""

from pathlib import Path


def flagged(mis_path, min_confidence=0.0):
    out = {}
    for line in Path(mis_path).read_text().splitlines():
        if line.startswith(";") or not line.strip():
            continue
        f = line.split("\t")
        if float(f[4]) >= min_confidence:
            out[f[0]] = f[1]
    return out
