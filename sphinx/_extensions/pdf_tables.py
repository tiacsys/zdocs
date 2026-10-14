# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Need tables in a PDF: column widths from the content, and page breaks.

sphinx-needs gives a ``needtable`` without ``:colwidths:`` fixed widths: 15
parts for the title, 5 for each other column. In a PDF, a column of long
values (tags, Kconfig names) then runs past the edge of the page, and a
column of short ones (need IDs) is so narrow that each ID breaks in two. And
Sphinx writes a table of 30 rows or fewer as a ``tabular``, which does not
break across pages: a long table moves to the next page and leaves an empty
page before it.

In a LaTeX build, this extension gives each such table:

- column widths from its content (`column_widths`): each column is as wide as
  its longest word, and the rest of the line goes to the columns with the
  most text;
- the class ``longtable``, so that it breaks across pages and repeats its
  header row;
- the container class ``zd-needtable``: text not justified, which zdocs.sty
  sets (Sphinx's ``sphinxclass<name>`` environment);
- if it is too wide for the line, a smaller font and less cell padding: the
  class ``zd-table-small`` or ``zd-table-smaller`` too;
- a possible line break after each ``/``, and after each ``.`` before a
  letter, in its text: ``native_sim/native/64``, ``safe_data.api.timeout``.
  (After an underscore, zdocs.sty allows a break everywhere.)

A ``needtable`` with ``:colwidths:`` keeps its widths.
"""

import re

from docutils import nodes

#: The width of a line of a table, in characters of the table font. Only the
#: ratio of the widths is in the PDF (\X{w}{sum}), so this is the scale on
#: which a column is "as wide as its longest word".
LINE = 90

#: The classes for a table that is too wide, and the line width in their
#: font: \footnotesize and \scriptsize, with less padding (zdocs.sty).
SMALLER = (("zd-table-small", 108), ("zd-table-smaller", 124))

#: A word longer than this breaks (after an underscore, zdocs.sty) and does
#: not make its column wider.
LONGEST_WORD = 24

#: The padding of a cell, in characters (Sphinx: 2 \\tabcolsep).
PADDING = 3


def _length(text):
    """The width of ``text`` in characters: a capital letter or a digit is
    wider than a small letter (need IDs are capitals and digits)."""
    return sum(1.3 if c.isupper() or c.isdigit() else 1.0 for c in text)


#: Where a line can break inside a word: after an underscore (zdocs.sty),
#: after a slash, and after a dot before a letter (`_add_breaks`). TeX also
#: breaks after a hyphen, but a need ID (SD-REQ-001) should stay on one line,
#: so a column is as wide as its longest ID.
_BREAK = re.compile(r"(?<=[_/])|(?<=\.)(?=[A-Za-z])")

#: Where `_add_breaks` adds a break: after a slash, and after a dot before a letter.
_ADD_BREAK = re.compile(r"(?<=/)(?=.)|(?<=\.)(?=[A-Za-z])")


def _words(text):
    """The parts of ``text`` that a line does not break."""
    for word in text.split():
        yield from (part for part in _BREAK.split(word) if part)


def _add_breaks(entry):
    """A LaTeX ``\\allowbreak`` at each `_ADD_BREAK` in the text of ``entry``."""
    for text in list(entry.findall(nodes.Text)):
        parts = _ADD_BREAK.split(str(text))
        if len(parts) < 2:
            continue
        new = []
        for part in parts:
            if new:
                new.append(nodes.raw("", "\\allowbreak{}", format="latex"))
            new.append(nodes.Text(part))
        parent = text.parent
        index = parent.index(text)
        parent[index : index + 1] = new


def _least(cells):
    longest = max((_length(w) for c in cells for w in _words(c)), default=1)
    return min(longest, LONGEST_WORD) + PADDING


def _least_width(columns):
    """The width of a table whose columns are as wide as their longest word."""
    return sum(_least(cells) for cells in columns)


def column_widths(columns, line=LINE):
    """The widths of ``columns`` (each a list of cell texts, the header too)."""
    least = [_least(cells) for cells in columns]
    most = [
        max(max((_length(c) for c in cells), default=1) + PADDING, low)
        for cells, low in zip(columns, least)
    ]
    free = line - sum(least)
    want = [m - l for m, l in zip(most, least)]
    if free <= 0 or sum(want) == 0:
        widths = least
    elif sum(want) <= free:
        widths = most
    else:
        widths = [l + free * w / sum(want) for l, w in zip(least, want)]
    return [max(1, round(w)) for w in widths]


#: The key on the doctree: the IDs of the tables of the needtables with
#: ``:colwidths:``. sphinx-needs drops the option when it builds the table.
_GIVEN = "zdocs_needtable_widths_given"


def _note_given_widths(app, doctree, docname):
    if app.builder.format != "latex":
        return
    from sphinx_needs.directives.needtable import Needtable

    doctree[_GIVEN] = {
        node["ids"][0] + "-table_node"
        for node in doctree.findall(Needtable)
        if node.get("colwidths") and node["ids"]
    }


def _columns(table):
    tgroup = next(iter(table.findall(nodes.tgroup)))
    columns = [[] for _ in tgroup.findall(nodes.colspec)]
    for row in tgroup.findall(nodes.row):
        entries = [c for c in row.children if isinstance(c, nodes.entry)]
        for index, entry in enumerate(entries):
            if index < len(columns):
                columns[index].append(entry.astext())
    return tgroup, columns


def _fit(app, doctree, docname):
    if app.builder.format != "latex":
        return
    for table in list(doctree.findall(nodes.table)):
        if not any(c.startswith("NEEDS_") for c in table["classes"]):
            continue
        if set(table["ids"]) & doctree.get(_GIVEN, set()):
            continue
        tgroup, columns = _columns(table)
        if not columns:
            continue
        line, size = LINE, None
        for cls, smaller_line in SMALLER:
            if _least_width(columns) <= line:
                break
            line, size = smaller_line, cls
        colspecs = list(tgroup.findall(nodes.colspec))
        for colspec, width in zip(colspecs, column_widths(columns, line)):
            colspec["colwidth"] = width
        if "longtable" not in table["classes"]:
            table["classes"].append("longtable")
        for entry in list(tgroup.findall(nodes.entry)):
            _add_breaks(entry)
        wrapper = nodes.container("", classes=["zd-needtable"] + ([size] if size else []))
        table.replace_self(wrapper)
        wrapper += table


def setup(app):
    # Before sphinx-needs builds the need tables (doctree-resolved, 500).
    app.connect("doctree-resolved", _note_given_widths, priority=450)
    # After sphinx-needs filled the need tables (doctree-resolved, 500).
    app.connect("doctree-resolved", _fit, priority=650)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
