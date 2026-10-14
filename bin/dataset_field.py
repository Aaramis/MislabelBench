#!/usr/bin/env python3
"""Read one field out of assets/datasets.yml, so the fetch scripts stop copying it.

    dataset_field.py gtdb_archaea_ssu sha256
    dataset_field.py gtdb_archaea_ssu url

The manifest is the record of where every input came from, and until now nothing read it: the two
fetch scripts each held their own copy of the sha256 and the url. Two places holding one fact is
how the judgeability figure in that same file came to disagree with the data for days.
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml is needed to read assets/datasets.yml")


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: dataset_field.py <dataset> <field>")
    name, field = sys.argv[1], sys.argv[2]
    here = Path(__file__).resolve().parent.parent / "assets" / "datasets.yml"
    data = yaml.safe_load(here.read_text())["datasets"]
    if name not in data:
        sys.exit(f"no dataset {name} in {here}; known: {', '.join(sorted(data))}")
    if field not in data[name]:
        sys.exit(f"{name} has no field {field}; has: {', '.join(sorted(data[name]))}")
    value = data[name][field]
    # JSON and not a Python repr, so a field like counts can be piped to jq instead of arriving as
    # {'in_release': 1053664} with quotes no parser accepts.
    print(value if isinstance(value, (str, int, float)) else json.dumps(value))


if __name__ == "__main__":
    main()
