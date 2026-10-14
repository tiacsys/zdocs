# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""pdf_links: no link to a local server or a relative HTML path in a PDF."""

from pathlib import Path

import pytest
from pdf_links import dead_in_pdf, pdf_target

_ROOT = str(Path(__file__).parent / "roots" / "test-pdflinks")


@pytest.mark.parametrize(
    "uri, dead",
    [
        ("http://localhost:8000/html/peer/index.html#REQ-1", True),
        ("http://127.0.0.1:8001/x.html", True),
        ("http://127.0.0.2/x.html", True),
        ("http://[::1]:8000/x.html", True),
        ("http://0.0.0.0:8000/x.html", True),
        ("https://localhost.example.org/x.html", False),
        ("https://192.0.2.1/x.html", False),
        ("file:///tmp/x.html", True),
        ("../../dox-api/main_8c_source.html#l00061", True),
        ("https://example.org/html/peer/index.html#REQ-1", False),
        ("mailto:someone@example.org", False),
        ("#REQ-1", False),
        ("%index#target", False),
        ("", False),
    ],
)
def test_dead_in_pdf(uri, dead):
    assert dead_in_pdf(uri) is dead


PEERS = {
    "https://docs.example.org/html/requirement-specification": "Requirement-Specification_1.2.pdf"
}


@pytest.mark.parametrize(
    "uri, target",
    [
        (
            "https://docs.example.org/html/requirement-specification/detailed.html#SD-REQ-001",
            "Requirement-Specification_1.2.pdf#detailed:SD-REQ-001",
        ),
        (
            "https://docs.example.org/html/requirement-specification/safe_data/x.html#a-b",
            "Requirement-Specification_1.2.pdf#safe_data/x:a-b",
        ),
        (
            "https://docs.example.org/html/requirement-specification/detailed.html",
            "Requirement-Specification_1.2.pdf#detailed::doc",
        ),
        (
            "https://docs.example.org/html/requirement-specification/",
            "Requirement-Specification_1.2.pdf#index::doc",
        ),
        ("https://docs.example.org/html/requirement-specification-old/x.html#A", None),
        ("https://docs.example.org/html/test-report/index.html#TR-1", None),
    ],
)
def test_pdf_target(uri, target):
    assert pdf_target(uri, PEERS) == target


@pytest.mark.sphinx("latex", srcdir=_ROOT)
def test_a_link_to_a_peer_in_the_set_goes_to_its_pdf(app):
    app.build()
    tex = (Path(app.outdir) / "pdflinks.tex").read_text()
    assert "\\sphinxhref{Requirement-Specification\\_1.2.pdf\\#detailed:SD-REQ-001}{" in tex
    assert "\\PassOptionsToPackage{destlabel}{hyperref}" not in tex  # zdocs_conf sets it


@pytest.mark.sphinx("latex", srcdir=_ROOT)
def test_a_pdf_has_no_dead_link(app):
    app.build()
    tex = (Path(app.outdir) / "pdflinks.tex").read_text()
    assert "localhost" not in tex and "main\\_8c\\_source" not in tex
    assert "peer" in tex and "listing" in tex  # the text stays
    assert "\\sphinxhref{https://example.org/html/peer/index.html\\#REQ-1}{site}" in tex
    assert "\\hyperref[\\detokenize{index:target}]" in tex
    warnings = app._warning.getvalue()
    assert "pdf_links: 2 link(s) written as text" in warnings
    assert "http://localhost:8000/html/peer/index.html#REQ-1" in warnings


def test_a_link_marked_internal_with_an_external_target_is_text_too():
    # sphinx-needs marks a needtable link "internal" by the row's need.
    from types import SimpleNamespace

    from docutils import nodes
    from docutils.utils import new_document
    from pdf_links import _unlink

    doc = new_document("index")
    para = nodes.paragraph()
    para += nodes.reference(
        "", "TC_1", internal=True, refuri="http://localhost:8000/html/spec/index.html#TC_1"
    )
    para += nodes.reference("", "here", internal=True, refuri="%index#target")
    doc += para
    app = SimpleNamespace(builder=SimpleNamespace(format="latex"), config=SimpleNamespace())
    _unlink(app, doc, "index")
    refs = list(doc.findall(nodes.reference))
    assert [r["refuri"] for r in refs] == ["%index#target"]
    assert para.astext() == "TC_1here"


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_html_keeps_every_link(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert 'href="http://localhost:8000/html/peer/index.html#REQ-1"' in html
    assert 'href="../../dox-api/main_8c_source.html#l00061"' in html
    assert "pdf_links" not in app._warning.getvalue()
