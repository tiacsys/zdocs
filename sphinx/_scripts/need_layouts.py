# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Need layouts that a document's ``conf.py`` gets from the engine.

Not a Sphinx extension: a document calls :func:`need_layout` in its
``conf.py`` (re-exported by ``zdocs_conf``) and puts the result in its own
``needs_layouts``::

    from zdocs_conf import configure, need_layout

    needs_layouts = {"requirement": need_layout(hide_backlinks=["covers"])}
    needs_default_layout = "requirement"

sphinx-needs shows every incoming link of a need. A requirement can have
hundreds of test results that cover it, and that list hides the rest of the
need. ``hide_backlinks`` names the links whose incoming side the layout does
not show. The links stay in the need data, so ``needs.json``, need tables and
need flows still have them.
"""

import re

#: A link name as sphinx-needs accepts it: an option name.
_LINK_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")

#: The head line of the sphinx-needs "clean" layout.
_CLEAN_HEAD = (
    '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>  '
    '<<collapse_button("meta", collapsed="icon:arrow-down-circle", '
    'visible="icon:arrow-right-circle", initial=False)>> '
)


def links_line(hide_backlinks=()):
    """The layout line that shows the links of a need, without ``hide_backlinks``.

    For a document's own layout: put it in place of ``<<meta_links_all()>>``.
    """
    for name in hide_backlinks:
        if not _LINK_NAME.match(name):
            raise ValueError(
                f"hide_backlinks: {name!r} is no link name; give the name of the "
                f"link, not its incoming title"
            )
    if not hide_backlinks:
        return "<<meta_links_all()>>"
    exclude = ", ".join(f'"{name}_back"' for name in hide_backlinks)
    return f"<<meta_links_all(exclude=[{exclude}])>>"


def need_layout(hide_backlinks=()):
    """The sphinx-needs "clean" layout, without the incoming links ``hide_backlinks``.

    ``hide_backlinks`` are link names from ``needs_config.toml`` (``"covers"``),
    not their incoming titles (``"covered by"``).
    """
    return {
        "grid": "simple",
        "layout": {
            "head": [_CLEAN_HEAD],
            "meta": ["<<meta_all(no_links=True)>>", links_line(hide_backlinks)],
        },
    }
