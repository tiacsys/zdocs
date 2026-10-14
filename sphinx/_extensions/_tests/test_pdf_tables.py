# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""pdf_tables: need tables in a PDF get widths from their content and break across pages."""

import re
from pathlib import Path

import pytest
from docutils import nodes
from pdf_tables import _add_breaks, _words, column_widths

_ROOT = str(Path(__file__).parent / "roots" / "test-pdftables")


def test_a_need_id_is_one_word_and_a_kconfig_name_breaks_after_an_underscore():
    assert list(_words("SD-REQ-001 kconfig-SAFE_DATA_STATS")) == [
        "SD-REQ-001",
        "kconfig-SAFE_",
        "DATA_",
        "STATS",
    ]
    assert list(_words("native_sim/native/64 safe_data.api.timeout 0.21")) == [
        "native_", "sim/", "native/", "64", "safe_", "data.", "api.", "timeout", "0.21",
    ]


def test_each_column_is_as_wide_as_its_longest_word():
    ids = ["ID", "SD-REQ-001", "SD-REQ-002"]
    titles = ["Title", "Sealing on initialisation " * 4]
    widths = column_widths([ids, titles], line=60)
    assert widths[0] >= len("SD-REQ-001")  # the ID does not break
    assert sum(widths) == 60  # the rest of the line goes to the title


def test_a_short_table_keeps_the_width_of_its_text():
    assert column_widths([["ID", "A-1"], ["Status", "open"]], line=90) == [7, 9]


def test_a_break_after_a_slash_and_after_a_dot_before_a_letter():
    entry = nodes.entry("", nodes.paragraph("", "native_sim/native/64 0.21 a.b"))
    _add_breaks(entry)
    raw = [n.astext() for n in entry.findall(nodes.raw)]
    assert raw == ["\\allowbreak{}"] * 3
    assert entry.astext().replace("\\allowbreak{}", "") == "native_sim/native/64 0.21 a.b"


@pytest.mark.sphinx("latex", srcdir=_ROOT)
def test_need_tables_in_the_pdf(app):
    app.build()
    tex = (Path(app.outdir) / "tables.tex").read_text()
    tables = re.findall(r"\\begin\{sphinxuseclass\}\{zd-needtable\}(.*?)\\end\{(?:longtable|tabular)\}", tex, re.S)
    assert len(tables) == 2  # not the table with :colwidths:
    narrow, wide = tables
    assert "\\begin{longtable}" in narrow
    assert "\\begin{sphinxuseclass}{zd-table-small" in wide or "zd-table-smaller" in wide
    assert "sim/\\allowbreak{}native/\\allowbreak{}64" in wide
    # The table with :colwidths: keeps them.
    assert "\\X{30}{100}\\X{70}{100}" in tex
