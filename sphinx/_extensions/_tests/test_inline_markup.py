# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Doxygen prose becomes RST that docutils parses as written.

RST accepts inline markup only next to whitespace or some punctuation. The
test specification writes ``<computeroutput>data_r</computeroutput>[]`` and
``<computeroutput><ref>k_msgq_init()</ref></computeroutput>ed``; joined as
written, the page showed the backticks and the build warned "Inline literal
start-string without end-string".
"""

import xml.etree.ElementTree as ET

import doxygen_parser as dp
import pytest
from docutils import nodes
from docutils.core import publish_doctree

LINKS = dp.RefLinks(api="../api", local="../testspec")
REF = "<ref refid='group__msgq_1ga54' kindref='member' external='/t/api.tag'>k_msgq_init()</ref>"


def _parse(rst):
    """The doctree of ``rst`` and the system messages docutils wrote for it."""
    tree = publish_doctree(rst, settings_overrides={"report_level": 5, "halt_level": 5})
    return tree, list(tree.findall(nodes.system_message))


def _text(xml, **kw):
    return dp.para_text(ET.fromstring(f"<para>{xml}</para>"), **kw)


@pytest.mark.parametrize(
    "xml, shown",
    [
        ("All of <computeroutput>data_r</computeroutput>[] are gone.", "All of data_r[] are gone."),
        ("<computeroutput>data</computeroutput>[0..N-1] first", "data[0..N-1] first"),
        (
            "Once <computeroutput>" + REF + "</computeroutput>ed, wait.",
            "Once k_msgq_init()ed, wait.",
        ),
        ("Once " + REF + "ed, wait.", "Once k_msgq_init()ed, wait."),
        ("re<computeroutput>x</computeroutput>", "rex"),
        ("<computeroutput>a</computeroutput><computeroutput>b</computeroutput>", "ab"),
        ("x=<computeroutput>a</computeroutput>+2", "x=a+2"),
    ],
)
def test_markup_next_to_a_word_parses(xml, shown):
    rst = _text(xml, links=LINKS)
    tree, messages = _parse(rst)
    assert messages == []
    assert tree.astext() == shown
    assert "`" not in tree.astext()


@pytest.mark.parametrize(
    "xml, rst",
    [
        # Space and punctuation are already a boundary: no escape goes in.
        ("Calls <computeroutput>f</computeroutput>, then (<computeroutput>g</computeroutput>).",
         "Calls ``f``, then (``g``)."),
        ("Calls " + REF + ".", "Calls `k_msgq_init() <../api/group__msgq.html#ga54>`__."),
        ("Put <computeroutput>x</computeroutput> in", "Put ``x`` in"),
    ],
)
def test_markup_at_a_boundary_is_unchanged(xml, rst):
    assert _text(xml, links=LINKS) == rst


def test_without_links_the_role_is_escaped_too():
    rst = _text("Once <computeroutput>" + REF + "</computeroutput>ed")
    assert rst == "Once :c:func:`k_msgq_init`\\ ed"


def test_plain_text_has_no_markup():
    xml = ("Drain <computeroutput>data1</computeroutput>[] via <computeroutput>" + REF
           + "</computeroutput>, then " + REF + ".")
    text = _text(xml, links=LINKS, plain=True)
    assert text == "Drain data1[] via k_msgq_init(), then k_msgq_init()."
