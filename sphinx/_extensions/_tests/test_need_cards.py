# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""need_cards: the type colors and status classes of the need cards."""

from pathlib import Path

import need_cards
import pytest
from need_cards import (
    _JS_SOURCE,
    CSS_NAME,
    JS_NAME,
    NEED_REF_CLASS,
    status_class,
    type_colors_css,
)

_ROOT = str(Path(__file__).parent / "roots" / "test-needcards")


def test_a_type_gets_its_color():
    css = type_colors_css([{"directive": "req", "color": "#FDEBD0"}])
    assert css == "table.need.need.need.need.needs_type_req { --zd-type: #FDEBD0; }\n"


@pytest.mark.parametrize("color", ["#abc", "#abcd", "#aabbcc", "#aabbccdd"])
def test_a_hex_color_of_a_css_length_gets_a_rule(color):
    assert f"--zd-type: {color};" in type_colors_css([{"directive": "req", "color": color}])


@pytest.mark.parametrize(
    "color", ["", None, "red; } body { x: y", "url(x)", "#12", "#12345", "#1234567", "#123456789"]
)
def test_a_type_without_a_css_color_gets_no_rule(color):
    assert type_colors_css([{"directive": "req", "color": color}]) == "\n"


def test_the_class_has_the_type_name_without_white_space():
    css = type_colors_css([{"directive": "my type", "color": "teal"}])
    assert ".needs_type_mytype " in css


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_the_page_links_the_css_and_the_build_writes_it(app):
    app.build()
    assert CSS_NAME in (Path(app.outdir) / "index.html").read_text()
    css = (Path(app.outdir) / "_static" / CSS_NAME).read_text()
    assert "needs_type_req { --zd-type: #FDEBD0; }" in css
    assert "needs_type_spec" not in css


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_the_page_loads_the_preview_script(app):
    # The root has no zdocs_conf, so no zdocs _static in html_static_path.
    app.build()
    assert f'src="_static/{JS_NAME}' in (Path(app.outdir) / "index.html").read_text()
    assert (Path(app.outdir) / "_static" / JS_NAME).read_text() == _JS_SOURCE.read_text()


@pytest.mark.parametrize(
    "status, cls",
    [("passed", "zd-status-passed"), ("Draft", "zd-status-draft"),
     ("Passed / OK", "zd-status-passed-ok"), ("", None), (None, None)],
)
def test_the_status_class(status, cls):
    assert status_class(status) == cls


def test_the_class_of_a_verdict():
    assert status_class("no-cov", "verdict") == "zd-verdict-no-cov"


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_each_need_table_gets_its_status_class(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    req = html[html.rfind("<table", 0, html.index('id="REQ_1"')):html.index('id="REQ_1"')]
    spec = html[html.rfind("<table", 0, html.index('id="SPEC_1"')):html.index('id="SPEC_1"')]
    assert "zd-status-draft" in req
    assert "zd-status-passed-ok" in spec
    assert "zd-verdict-" not in req  # no verdict field: no class


@pytest.mark.sphinx("html", srcdir=_ROOT)
def test_only_a_link_to_a_need_gets_the_need_ref_class(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    spec = html[html.index('id="SPEC_1"'):]

    def link(href_part):
        end = spec.index(href_part)
        return spec[spec.rfind("<a ", 0, end):end]

    assert NEED_REF_CLASS in link('href="#REQ_1"')  # the links field of SPEC_1
    assert NEED_REF_CLASS not in link("main_8c_source.html#l00042")
    assert f"a.{NEED_REF_CLASS}" in _JS_SOURCE.read_text()


# -- The card in a PDF ---------------------------------------------------------

_LATEX_ROOT = str(Path(__file__).parent / "roots" / "test-needcards-latex")


@pytest.mark.parametrize(
    "color, rgb",
    [
        ("#FDEBD0", "8B6001"),  # the type color of a requirement: brown-orange
        ("#D6EAF8", "0571A3"),
        ("#eeeeee", "696969"),  # a grey stays grey
        ("#fff", "696969"),
        ("", None),
        ("red", None),  # a name: no hue that the engine can compute
    ],
)
def test_the_accent_of_a_type_color(color, rgb):
    assert need_cards.accent(color) == rgb


@pytest.mark.parametrize(
    "cls, tone",
    [
        ("zd-status-passed", "good"),
        ("zd-status-failed", "bad"),
        ("zd-verdict-partial", "gap"),
        ("zd-status-skipped", "none"),
        ("zd-status-approved", "accent"),
    ],
)
def test_the_tone_of_a_status(cls, tone):
    assert need_cards.tone(cls) == tone


@pytest.mark.sphinx("latex", srcdir=_LATEX_ROOT)
def test_a_card_is_written_with_the_macros_of_zdocs_sty(app):
    app.build()
    tex = (Path(app.outdir) / "cards.tex").read_text()
    req = tex[tex.index("\\begin{zdneed}{8B6001}") :]
    req = req[: req.index("\\end{zdneed}")]
    assert "\\phantomsection\\label{\\detokenize{index:REQ_1}}" in req
    assert "\\zdneedhead{Requirement}{REQ\\_\\allowbreak{}1}{accent}{approved}" in req
    assert "\\zdneedtitle{" in req and "A requirement" in req
    # The title, then the text, then the fields and links.
    text = req.index("The text of the requirement.")
    assert req.index("\\zdneedtitle{") < text < req.index("\\zdneedfield{Component}")
    assert req.index("\\zdneedfield{Component}") < req.index("\\zdneedfield{links incoming}")
    assert "SPEC\\_A\\_LONG\\_ID" in req[req.index("\\zdneedfield{links incoming}") :]

    spec = tex[tex.index("\\begin{zdneed}{666666}") :]
    assert spec.index("{good}{passed}") < spec.index("\\end{zdneed}")
    # A need of another layout keeps the sphinx-needs table.
    assert tex.count("\\begin{zdneed}") == 2
    assert "\\label{\\detokenize{index:REQ_2}}" in tex
