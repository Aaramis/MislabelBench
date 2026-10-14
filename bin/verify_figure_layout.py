#!/usr/bin/env python3
"""Nothing in a figure may overlap anything else, or run out of the box it sits in.

Every visual defect found in this figure so far was found by looking at it, reported in French, and
fixed by hand -- which works until the text is in English, the panel is 240 points wide and the
reader is a referee. Two of them were still there after four passes of looking:

  the schematic's boxes were sized for 8 pt text and drawn at FONT_SCALE 1.6, so "Reference tree"
  was 99 points of Helvetica in a box of 78 and ran out of both sides;

  the line step inside a box was computed from the unscaled size, 11 apart for glyphs 12.8 tall, so
  every multi-line box had its lines touching;

  and in the runtime panel the "1 min" annotation and the largest reference's label overlapped by 25
  points, because both want the strip just below the top frame.

So the figure is measured rather than looked at. Helvetica's average advance over mixed-case text is
about 0.52 em; 0.55 is used here, which errs towards reporting a collision that is only a near miss.
That is the right direction for a check whose output a human then looks at.

    bin/verify_figure_layout.py results/figure3.svg [more.svg ...]

Four rules:

  no two text elements' boxes intersect
  a text element whose anchor lies inside a filled rectangle fits inside it, with a point to spare
  a text element that starts inside a panel frame does not run out of its right edge
  nothing is drawn outside the canvas

The third was added after the fourth defect of the same family: panel E's legend ran 17 points past
its own frame and this script said nothing, because a frame is an unfilled rectangle and the second
rule only looks at filled ones. Tick labels and axis titles sit outside the frame to begin with and
are not caught by it; a legend, an annotation or a point label inside the plot is.

Rotated text is measured along its own axis. A text that sits in no rectangle is checked by the
first and third rules only, which is every axis label and every point label.

bin/analyses.sh passes it the manuscript's figure, results/figure3.svg.
"""

import argparse
import html
import itertools
import re
import sys

TEXT = re.compile(r"<text ([^>]*)>(.*?)</text>", re.S)
RECT = re.compile(r"<rect ([^>]*)/>")
SVG = re.compile(r"<svg ([^>]*)>")
EM = 0.55            # Helvetica's average advance, rounded up
ASCENT, DESCENT = 0.78, 0.22


def attr(s, key, default=None):
    m = re.search(rf'{key}="([^"]*)"', s)
    return m.group(1) if m else default


def boxes(svg):
    """Every text element as (label, x0, y0, x1, y1)."""
    out = []
    for a, body in TEXT.findall(svg):
        # Entities are one glyph, not four. Measured as written, "&gt;" made a label 21 points
        # wider than it prints and the panel-frame rule reported a legend that fits.
        s = html.unescape(re.sub(r"<[^>]+>", "", body)).strip()
        if not s:
            continue
        x, y = float(attr(a, "x", 0)), float(attr(a, "y", 0))
        size = float(attr(a, "font-size", 10))
        anchor = attr(a, "text-anchor", "middle")
        w = len(s) * size * EM
        if "rotate" in (attr(a, "transform") or ""):
            # Only -90 is used here, and a rotated label is measured along its own axis.
            out.append((s, x - size * ASCENT, y - w / 2, x + size * DESCENT, y + w / 2))
            continue
        x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        out.append((s, x0, y - size * ASCENT, x0 + w, y + size * DESCENT))
    return out


def panel_frames(svg):
    """The plot frames: unfilled rectangles with a stroke. filled_rects() skips them by design."""
    out = []
    for a in RECT.findall(svg):
        if attr(a, "fill", "none") == "none" and attr(a, "stroke"):
            x, y = float(attr(a, "x", 0)), float(attr(a, "y", 0))
            out.append((x, y, x + float(attr(a, "width", 0)), y + float(attr(a, "height", 0))))
    return out


def filled_rects(svg):
    out = []
    for a in RECT.findall(svg):
        fill = attr(a, "fill", "none")
        if fill in ("none", "#fff", "#ffffff"):
            continue
        x, y = float(attr(a, "x", 0)), float(attr(a, "y", 0))
        out.append((x, y, x + float(attr(a, "width", 0)), y + float(attr(a, "height", 0))))
    return out


def check(path, margin=1.0):
    svg = open(path).read()
    head = SVG.search(svg).group(1)
    cw, ch = float(attr(head, "width", 0)), float(attr(head, "height", 0))
    texts, rects, frames = boxes(svg), filled_rects(svg), panel_frames(svg)
    problems = []

    for a, b in itertools.combinations(texts, 2):
        ix = min(a[3], b[3]) - max(a[1], b[1])
        iy = min(a[4], b[4]) - max(a[2], b[2])
        if ix > 0.5 and iy > 0.5:
            problems.append(f"'{a[0]}' and '{b[0]}' overlap by {ix:.0f} x {iy:.0f} points")

    for s, x0, y0, x1, y1 in texts:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        # The last match, not the first: the schematic draws three offset cards for the batched
        # engine and the text belongs to the one on top, which is the one drawn last. Against the
        # cards behind it, every line of that box reads as running out of its left edge.
        holding = [r for r in rects if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]]
        if holding:
            rx0, ry0, rx1, ry1 = holding[-1]
            if x0 < rx0 + margin or x1 > rx1 - margin:
                problems.append(f"'{s}' is {x1 - x0:.0f} points wide in a box of "
                                f"{rx1 - rx0:.0f} and runs out of it")
            if y0 < ry0 + margin or y1 > ry1 - margin:
                problems.append(f"'{s}' runs out of the top or bottom of its box")
        for fx0, fy0, fx1, fy1 in frames:
            if fx0 <= x0 <= fx1 and fy0 <= cy <= fy1 and x1 > fx1:
                problems.append(f"'{s}' starts inside a panel and runs {x1 - fx1:.0f} points out of "
                                f"its right edge")
                break

        if x0 < -0.5 or y0 < -0.5 or x1 > cw + 0.5 or y1 > ch + 0.5:
            problems.append(f"'{s}' is outside the {cw:.0f} by {ch:.0f} canvas")

    print(f"{path}: {len(texts)} text elements, {len(rects)} boxes and {len(frames)} panel "
          f"frames checked; {len(problems)} problem(s)")
    for pb in problems[:12]:
        print(f"  {pb}", file=sys.stderr)
    return problems


def main():
    p = argparse.ArgumentParser()
    p.add_argument("svg", nargs="+")
    args = p.parse_args()
    bad = sum(len(check(s)) for s in args.svg)
    if bad:
        sys.exit(f"{bad} layout problem(s)")


if __name__ == "__main__":
    main()
