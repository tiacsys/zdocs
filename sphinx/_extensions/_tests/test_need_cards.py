# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""need_cards: the type colors and status classes of the need cards."""

from pathlib import Path

import pytest
from need_cards import CSS_NAME, status_class, type_colors_css

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
