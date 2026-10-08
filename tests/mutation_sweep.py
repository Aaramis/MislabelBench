#!/usr/bin/env python3
"""Flip one operator at a time in a script and see whether the tests notice.

`tests/test_parsing.py` describes a sweep like this in prose: 26 mutations, 16 survivors, four of
them in code that decides a published figure. The prose is a claim a reader cannot check, so the
sweep is here as something to run:

    python3 tests/mutation_sweep.py bin/grove_taxonomy.py tests.test_grove_taxonomy

It reports how many mutants the suite killed and prints the line of every survivor. A survivor is
not automatically a defect -- some mutations cannot change the answer at all -- but it is a line no
test distinguishes, which is worth knowing before trusting it.

Three things it deliberately does. It refuses to run when the suite already fails, because then every
mutant counts as killed and a broken test reports a perfect score -- which is what the first run of
this file did. It skips occurrences inside comments and string literals, taken from the tokenizer and
not from the look of the line, because mutating prose measures nothing: filtering by line alone left
20 survivors where 7 were real, and a `>=` inside a printed message survives every test there will
ever be. And it restores the file in a `finally`, because leaving a mutant in the working tree when a
run is interrupted is the one way a tool like this can do real damage.
"""

import argparse
import io
import subprocess
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Pairs chosen for the mistakes that actually happen here: an off-by-one on a boundary, a comparison
# flipped, an index walked the wrong way, a min that should be a max.
PAIRS = [(">=", ">"), (">=", "=="), ("<", "<="), (" + ", " - "), (" - ", " + "),
         ("min(", "max("), ("max(", "min("), ("is None", "is not None"),
         ("start=1", "start=0"), ("reversed(", "list(")]


def literal_spans(text):
    """Character ranges that are comments or string text, from the tokenizer rather than by eye.

    Line-based filtering was the first attempt and it is not enough: a `>=` inside a printed message
    is prose, lives on a line of code, and mutating it changes nothing. Under python 3.12 and later an
    f-string's literal parts come through as FSTRING_MIDDLE, which is why that type is here; the
    expressions inside the braces are real code and stay mutable.
    """
    starts, pos = [], 0
    for line in text.splitlines(keepends=True):
        starts.append(pos)
        pos += len(line)
    starts.append(pos)
    spans = []
    want = {tokenize.STRING, tokenize.COMMENT, getattr(tokenize, "FSTRING_MIDDLE", -1)}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in want:
            spans.append((starts[tok.start[0] - 1] + tok.start[1],
                          starts[tok.end[0] - 1] + tok.end[1]))
    return spans


def inside(spans, offset):
    return any(a <= offset < b for a, b in spans)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("target", help="script to mutate, e.g. bin/grove_taxonomy.py")
    p.add_argument("tests", help="test module to run, e.g. tests.test_grove_taxonomy")
    args = p.parse_args()

    target = Path(args.target)
    original = target.read_text()

    # The suite has to pass before anything is mutated, or every mutant counts as killed and the
    # sweep reports a perfect score for a broken test. That happened on the first run of this file.
    first = subprocess.run([sys.executable, "-m", "unittest", args.tests],
                           cwd=REPO, capture_output=True, text=True)
    if first.returncode:
        print(f"{args.tests} already fails on unmutated code; fix that first", file=sys.stderr)
        print(first.stderr[-2000:], file=sys.stderr)
        return 1

    spans = literal_spans(original)
    mutants, killed, survivors = 0, 0, []
    try:
        for old, new in PAIRS:
            for i in range(original.count(old)):
                parts = original.split(old)
                head = old.join(parts[:i + 1])
                mutated = head + new + old.join(parts[i + 1:])
                if mutated == original or inside(spans, len(head)):
                    continue                     # prose in a comment or a message, not behaviour
                mutants += 1
                target.write_text(mutated)
                r = subprocess.run([sys.executable, "-m", "unittest", args.tests],
                                   cwd=REPO, capture_output=True, text=True)
                if r.returncode:
                    killed += 1
                else:
                    survivors.append((old, new,
                                      original.splitlines()[original[:len(head)].count("\n")]))
    finally:
        target.write_text(original)

    print(f"{mutants} mutants in {target}, {killed} killed by {args.tests}, "
          f"{len(survivors)} survived")
    for old, new, line in survivors:
        print(f"  SURVIVED  {old!r} -> {new!r}  {line.strip()[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
