# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""What the zdocs need cards (``zdocs-needs.css``) need from the build.

**The color of each need type.** A need type in ``needs_config.toml`` has a
``color``; sphinx-needs uses it in need flows. This extension writes
``_static/zdocs-need-types.css`` with one rule per type, so that a card has the
same color as the type has in a flow::

    table.need.need.need.need.needs_type_req { --zd-type: #FDEBD0; }

A type without a color, or with a value that is no CSS color, gets no rule;
its cards stay grey.

**The status and the verdict of each need.** sphinx-needs gives the table of
a need no class for a field value, and CSS cannot read the text. After
sphinx-needs has rendered the needs of a page, the extension adds
``zd-status-<status>`` and ``zd-verdict-<verdict>`` to each need table that
has the field (``zd-status-passed``, ``zd-verdict-partial``), so that the card
can color the pill. The need data does not change.
"""

import re
from pathlib import Path

from docutils import nodes

CSS_NAME = "zdocs-need-types.css"

#: A CSS color as needs_config.toml gives it: #rgb(a) / #rrggbb(aa) or a name.
_COLOR = re.compile(r"^(#([0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})|[A-Za-z]+)$")


def type_colors_css(types):
    """The CSS rules for ``types`` (the sphinx-needs ``needs_types`` list)."""
    rules = []
    for need_type in types:
        color = str(need_type.get("color") or "").strip()
        if not _COLOR.match(color):
            continue
        # sphinx-needs: "needs_type_" + the type name without white space.
        name = "".join(need_type["directive"].split())
        # One class more than the default in zdocs-needs.css, so the load
        # order of the two files does not matter.
        rules.append(f"table.need.need.need.need.needs_type_{name} {{ --zd-type: {color}; }}")
    return "\n".join(rules) + "\n"


#: The fields that a card shows as a pill: the engine's status and verdict.
PILL_FIELDS = ("status", "verdict")


def status_class(value, field="status"):
    """The class for ``value`` of ``field``: ``zd-<field>-`` and the value in
    lower case, with each run of other characters than letters and digits as
    one ``-``. ``None`` for no value."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return f"zd-{field}-{slug}" if slug else None


def _add_status_classes(app, doctree, docname):
    from sphinx_needs.data import SphinxNeedsData

    needs = SphinxNeedsData(app.env).get_needs_view()
    for table in doctree.findall(nodes.table):
        if "need" not in table["classes"] or not table["ids"]:
            continue
        try:
            need = needs[table["ids"][0]]
        except KeyError:
            continue
        for field in PILL_FIELDS:
            cls = status_class(need.get(field), field)
            if cls and cls not in table["classes"]:
                table["classes"].append(cls)


def _write(app, exception):
    if exception is not None or app.builder.format != "html":
        return
    from sphinx_needs.config import NeedsSphinxConfig

    static = Path(app.outdir) / "_static"
    static.mkdir(parents=True, exist_ok=True)
    css = type_colors_css(NeedsSphinxConfig(app.config).types)
    path = static / CSS_NAME
    if not path.exists() or path.read_text() != css:
        path.write_text(css)


def _add_css(app):
    if app.builder.format == "html":
        app.add_css_file(CSS_NAME)


def setup(app):
    app.connect("builder-inited", _add_css)
    # After sphinx-needs replaced each need node with its table
    # (process_need_nodes, doctree-resolved at the default priority 500).
    app.connect("doctree-resolved", _add_status_classes, priority=600)
    # After the HTML builder copied the static files, which it does at the end.
    app.connect("build-finished", _write)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
