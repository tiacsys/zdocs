# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: the symbolneeds directive — one need per API symbol that
satisfies a requirement.

A Doxygen 1.16 ``\\satisfies <UID>`` on a function or macro becomes, in the XML,
a ``<satisfies>`` child of its memberdef. This directive turns each such symbol
into a need (the ``implementation`` role) linked to those requirements (the
``satisfies`` role), so a requirement's page shows what implements it next to
what verifies it.

Loaded only for a document whose registry entry has a ``symbol_needs:`` block,
which also names the Doxygen document whose XML is read.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import ViewList
from doxygen_parser import load_group_index, parse_symbol
from input_tracking import _note_input
from needs_fields import depends_field
from rst_builders import build_symbol_need_rst

from sphinx.util import logging

logger = logging.getLogger(__name__)

#: Compound kinds whose XML holds member definitions a symbol need can come
#: from. Pages, directories and requirements hold none.
_MEMBER_COMPOUNDS = ("group", "file", "namespace", "struct", "union", "class")


def _need_names_from_config(config):
    return {
        **getattr(config, "symbolneeds_need_types", {}),
        **getattr(config, "symbolneeds_need_links", {}),
    }


def _compounds(xml_dir, group=None):
    """``[(refid, title)]`` of the compounds to read: one group, or all of them."""
    if group is not None:
        refid = load_group_index(xml_dir).get(group)
        return [(refid, group)] if refid else []
    root = ET.parse(xml_dir / "index.xml").getroot()
    return [
        (c.get("refid"), c.findtext("name", c.get("refid")))
        for c in root.findall("compound")
        if c.get("kind") in _MEMBER_COMPOUNDS
    ]


def symbol_needs_rst(
    xml_dir, html_dir, group=None, need_names=None, note_input=None, depends_field=None
):
    """RST lines for the symbol needs of ``group`` (or the whole project).

    With no group, the needs are sectioned by compound (group or file), each
    heading taken from the compound's title. A member is emitted once, where
    Doxygen defines it, however many compounds list it. ``note_input`` is
    called with every XML file read. ``depends_field(conditions, subject)``
    decides whether a need gets the ``depends_on`` field
    (`needs_fields.depends_field`); without it, none does.
    """
    xml_dir = Path(xml_dir)
    lines, seen = [], set()
    for refid, name in _compounds(xml_dir, group):
        xml = xml_dir / f"{refid}.xml"
        if note_input:
            note_input(xml)
        if not xml.exists():
            logger.warning(f"symbolneeds: compound XML not found: {xml}")
            continue
        cdef = ET.parse(xml).getroot().find("compounddef")
        blocks = []
        for md in cdef.iter("memberdef"):
            if md.find("satisfies") is None or md.get("id") in seen:
                continue
            seen.add(md.get("id"))
            info = parse_symbol(md, html_dir)
            with_depends = bool(depends_field) and depends_field(
                info["depends_on"], f"symbolneeds: {info['name']}"
            )
            blocks += build_symbol_need_rst(info, need_names, with_depends).splitlines()
            blocks.append("")
        if not blocks:
            continue
        if group is None:
            title = cdef.findtext("title") or name
            lines += [title, "-" * len(title), ""]
        lines += blocks
    return lines


class SymbolNeedsDirective(Directive):
    """Emit one need per API symbol carrying a Doxygen ``\\satisfies``.

    Usage::

        .. symbolneeds::

        .. symbolneeds:: queue_apis

    The optional argument is a Doxygen group name; without it every annotated
    symbol in the project is emitted, sectioned by group or file.
    """

    required_arguments = 0
    optional_arguments = 1
    has_content = False
    option_spec = {}

    def run(self):
        group = self.arguments[0].strip() if self.arguments else None
        env = self.state.document.settings.env
        config = env.app.config
        xml_dir = Path(config.symbolneeds_xml_dir)
        _note_input(env, xml_dir / "index.xml")
        if not (xml_dir / "index.xml").is_file():
            msg = f"symbolneeds: Doxygen XML not found: {xml_dir / 'index.xml'}"
            logger.warning(msg, location=(env.docname, self.lineno))
            return [nodes.paragraph(text="[symbolneeds: Doxygen XML not found: index.xml]")]

        page_prefix = "../" * (len(Path(env.docname).parts) - 1)
        doxygen_url = config.symbolneeds_doxygen_url
        html_dir = page_prefix + doxygen_url if doxygen_url else ""
        try:
            rst = symbol_needs_rst(
                xml_dir, html_dir, group, _need_names_from_config(config),
                note_input=lambda path: _note_input(env, path),
                depends_field=lambda conditions, subject: depends_field(
                    env, conditions, subject
                ),
            )
        except (OSError, ET.ParseError) as exc:
            logger.warning(f"symbolneeds: cannot read {xml_dir}: {exc}")
            return [nodes.paragraph(text="[symbolneeds: cannot read the Doxygen XML]")]
        if group is not None and not rst:
            logger.warning(
                f"symbolneeds: group '{group}' not found or has no symbol with \\satisfies",
                location=(env.docname, self.lineno),
            )
            return []

        container = nodes.container()
        self.state.nested_parse(
            ViewList(rst, source="<symbolneeds>"), self.content_offset, container,
            match_titles=True,
        )
        return container.children


def setup(app):
    app.add_config_value("symbolneeds_xml_dir", "", "env")
    app.add_config_value("symbolneeds_doxygen_url", "", "env")
    app.add_config_value("symbolneeds_need_types", {"implementation": "impl"}, "env")
    app.add_config_value("symbolneeds_need_links", {"satisfies": "satisfies"}, "env")
    app.setup_extension("input_tracking")
    app.add_directive("symbolneeds", SymbolNeedsDirective)
    return {"version": "0.1", "parallel_read_safe": True}
