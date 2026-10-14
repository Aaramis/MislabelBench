#!/usr/bin/env python3
"""Drawing primitives shared by main_figure.py and supplement_figures.py.

Figures are written as SVG by hand rather than with a plotting library. Every other script in bin/
runs on the standard library alone, so a clone rebuilds all of results/ with no environment to
install, and the output is text that is identical on any machine and carries no timestamp.
"""

# Black for SATIVA-epang, colour and a dash for the comparator; it survives greyscale printing.
FORK, UP = "#000000", "#c1462c"
COMPARATOR_DASH = "5 2"

# Every font size passes through txt(), so one factor sets the printed size of the whole figure. The
# journal's two-column text block is 424 pt and the canvas is 760, so 1.6 puts the smallest label at
# 5.8 pt in print.
FONT_SCALE = 1.6

# "upper" draws panel letters as A, B, C; "paren-lower" as (a), (b), (c).
LABEL_STYLE = "paren-lower"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, size=9, anchor="middle", weight="normal", rot=None, fill="#000"):
    t = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot is not None else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size * FONT_SCALE:.1f}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}"{t}>{esc(s)}</text>')


def panel_label(key):
    return key.upper() if LABEL_STYLE == "upper" else f"({key.lower()})"
