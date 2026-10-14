# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Need layouts that a document's ``conf.py`` gets from the engine.

Not a Sphinx extension: a document calls :func:`need_layout` in its
``conf.py`` (re-exported by ``zdocs_conf``) and puts the result in its own
``needs_layouts``, under a name that starts with ``zdocs``::

    from zdocs_conf import configure, need_layout

    needs_layouts = {
        "zdocs_requirement": need_layout(
            fields=[("rtype", "Kind"), ("component", "Component")],
            hide_backlinks=["covers"],
        )
    }
    needs_default_layout = "zdocs_requirement"

The layout is a card: a head with the type, the ID, the status and the title;
then the text of the need; then its fields and links. ``zdocs-needs.css``
styles a need whose layout name starts with ``zdocs`` (the HTML class
``needs_layout_<name>``), and the ``need_cards`` extension gives each
need type its ``color`` from the needs configuration.

The rows stay in the sphinx-needs order (head, fields, text); the CSS shows
the fields last, so a screen reader still gives the fields first. In a PDF,
``need_cards`` writes the card with the macros of ``zdocs.sty``: head, title,
text, then the fields and links.

sphinx-needs shows every incoming link of a need. A requirement can have
hundreds of test results that cover it, and that list hides the rest of the
need. ``hide_backlinks`` names the links whose incoming side the layout does
not show. The links stay in the need data, so ``needs.json``, need tables and
need flows still have them.
"""

import re

#: A link or field name as sphinx-needs accepts it: an option name.
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")

#: A field label: words, not RST or the quotes of the layout call.
_LABEL = re.compile(r"^[\w][\w .,()/-]*$")

def _head(pill):
    """The head: type, ID and the ``pill`` field on one line, the title on the next."""
    return [f'<<meta("type_name")>> <<meta_id()>> <<meta("{pill}")>>', '<<meta("title")>>']


def _check_names(what, names):
    for name in names:
        if not _NAME.match(name):
            raise ValueError(f"{what}: {name!r} is no name; give the name, not its title")


def links_line(hide_backlinks=()):
    """The layout line that shows the links of a need, without ``hide_backlinks``.

    For a document's own layout: put it in place of ``<<meta_links_all()>>``.
    """
    _check_names("hide_backlinks", hide_backlinks)
    if not hide_backlinks:
        return "<<meta_links_all()>>"
    exclude = ", ".join(f'"{name}_back"' for name in hide_backlinks)
    return f"<<meta_links_all(exclude=[{exclude}])>>"


def field_line(name, label):
    """The layout line for field ``name``, shown as ``label: value``.

    The space after the colon is for the PDF, where the label and the value
    follow each other in one line. In the HTML card, the label is a grid
    column and the browser drops the space at its end.
    """
    _check_names("fields", [name])
    if not _LABEL.match(label):
        raise ValueError(f"fields: the label {label!r} of {name!r} must be plain words")
    return f'<<meta("{name}", prefix="{label}: ")>>'


def need_layout(fields=None, hide_backlinks=(), pill="status"):
    """The zdocs need card.

    ``fields`` is a list of ``(name, label)`` pairs, in the order to show. If it
    is ``None``, the card shows every field that has a value, under its own
    name.

    ``hide_backlinks`` are link names from ``needs_config.toml``
    (``"covers"``), not their incoming titles (``"covered by"``).

    ``pill`` is the field that the head shows as a pill, next to the ID: the
    ``status``, or the ``verdict`` of an adequacy need. ``zdocs-needs.css``
    colors the pill of a test result status and of a verdict.
    """
    _check_names("pill", [pill])
    if fields is None:
        meta = [f'<<meta_all(no_links=True, exclude=["{pill}"])>>']
    else:
        meta = [field_line(name, label) for name, label in fields]
    return {
        "grid": "simple",
        "layout": {"head": _head(pill), "meta": [*meta, links_line(hide_backlinks)]},
    }
