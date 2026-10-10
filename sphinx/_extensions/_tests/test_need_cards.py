# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""need_cards: the type colors and status classes of the need cards."""

from pathlib import Path

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
