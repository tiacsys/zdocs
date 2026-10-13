# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""need_layouts: need layouts that a document's conf.py gets from the engine."""

import json
from pathlib import Path

import pytest
from need_layouts import field_line, links_line, need_layout

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
    with pytest.raises(ValueError, match="no name"):
        links_line([name])


def test_the_card_has_the_head_the_fields_and_the_links():
    layout = need_layout(fields=[("rtype", "Kind")], hide_backlinks=["covers"])
    assert layout["grid"] == "simple"
    assert layout["layout"]["head"] == [
        '<<meta("type_name")>> <<meta_id()>> <<meta("status")>>',
        '<<meta("title")>>',
    ]
    assert layout["layout"]["meta"] == [
        '<<meta("rtype", prefix="Kind: ")>>',
        '<<meta_links_all(exclude=["covers_back"])>>',
    ]


def test_without_fields_the_card_shows_all_but_the_status():
    meta = need_layout()["layout"]["meta"]
    assert meta == ['<<meta_all(no_links=True, exclude=["status"])>>', "<<meta_links_all()>>"]


@pytest.mark.parametrize("label", ['Kind"', "a\\b", "**bold**", "<<x>>", ""])
def test_a_label_that_is_no_plain_words_is_an_error(label):
    with pytest.raises(ValueError, match="plain words"):
        field_line("rtype", label)


# -- In a build ----------------------------------------------------------------

def _need_html(app, need_id):
    """The rendered need ``need_id`` in index.html."""
    html = (Path(app.outdir) / "index.html").read_text()
    start = html.rfind("<table", 0, html.index(f'id="{need_id}"'))
    return html[start:html.index("</table>", start)]


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_a_hidden_backlink_is_not_shown(app):
    app.build()
    req = _need_html(app, "REQ_1")
    assert "verified by" in req and "SPEC_1" in req
    assert "covered by" not in req and "RES_1" not in req
    assert "needs_layout_zdocs_slim" in req
    assert '<span class="needs_label">State: </span>' in req


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


def test_the_pill_can_be_another_field():
    layout = need_layout(pill="verdict")
    assert layout["layout"]["head"][0] == '<<meta("type_name")>> <<meta_id()>> <<meta("verdict")>>'
    assert layout["layout"]["meta"][0] == '<<meta_all(no_links=True, exclude=["verdict"])>>'


def test_a_pill_that_is_no_field_name_is_an_error():
    with pytest.raises(ValueError, match="no name"):
        need_layout(pill='status")>> <<x')
