# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""need_layouts: need layouts that a document's conf.py gets from the engine."""

import json
from pathlib import Path

import pytest
from need_layouts import links_line, need_layout

_ROOT = str(Path(__file__).parent / "roots" / "test-needlayouts")


# -- The generated layout strings ------------------------------------------------

def test_without_hidden_links_the_links_line_shows_all():
    assert links_line() == "<<meta_links_all()>>"


def test_a_hidden_link_is_excluded_by_its_incoming_name():
    assert links_line(["covers", "trace"]) == (
        '<<meta_links_all(exclude=["covers_back", "trace_back"])>>'
    )


@pytest.mark.parametrize("name", ["covered by", 'x"]', "", "a>>b"])
def test_a_name_that_is_no_link_name_is_an_error(name):
    with pytest.raises(ValueError, match="no link name"):
        links_line([name])


def test_the_layout_is_the_clean_layout_of_sphinx_needs():
    from sphinx_needs.defaults import LAYOUTS

    assert need_layout() == LAYOUTS["clean"]


# -- In a build ----------------------------------------------------------------

def _need_html(app, need_id):
    """The rendered need ``need_id`` in index.html."""
    html = (Path(app.outdir) / "index.html").read_text()
    start = html.index(f'id="{need_id}"')
    return html[start:html.index("</table>", start)]


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_a_hidden_backlink_is_not_shown(app):
    app.build()
    req = _need_html(app, "REQ_1")
    assert "verified by" in req and "SPEC_1" in req
    assert "covered by" not in req and "RES_1" not in req


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_a_documents_own_layout_can_use_the_links_line(app):
    app.build()
    req = _need_html(app, "REQ_2")
    assert "state:" in req
    assert "verified by" in req
    assert "covered by" not in req


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_another_layout_still_shows_every_backlink(app):
    app.build()
    req = _need_html(app, "REQ_3")
    assert "covered by" in req and "RES_1" in req


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_the_hidden_links_stay_in_the_need_data(app):
    app.build()
    needs = json.loads((Path(app.outdir) / "needs.json").read_text())
    req = next(iter(needs["versions"].values()))["needs"]["REQ_1"]
    assert req["covers_back"] == ["RES_1"]
