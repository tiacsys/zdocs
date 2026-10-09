# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _scripts/

from need_layouts import links_line, need_layout  # noqa: E402

extensions = ["sphinx_needs"]
master_doc = "index"
exclude_patterns = ["_build"]

needs_types = [
    dict(directive="req",  title="Requirement", prefix="REQ_",  color="#FDEBD0", style="node"),
    dict(directive="spec", title="Test Case",   prefix="SPEC_", color="#E2EFDA", style="node"),
    dict(directive="res",  title="Test Result", prefix="RES_",  color="#DDEBF7", style="node"),
]
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"
needs_links = {
    "verifies": {"description": "verifies", "incoming": "verified by", "outgoing": "verifies"},
    "covers":   {"description": "covers",   "incoming": "covered by",  "outgoing": "covers"},
}
needs_build_json = True
suppress_warnings = ["config.cache"]

needs_layouts = {
    # The engine's layout, without the incoming "covered by" links.
    "slim": need_layout(hide_backlinks=["covers"]),
    # A document's own layout, with the engine's links line in it.
    "own": {
        "grid": "simple",
        "layout": {
            "head": ['<<meta("title")>> <<meta_id()>>'],
            "meta": [
                '<<meta("status", prefix="\\*\\*state:\\*\\* ")>>',
                links_line(["covers"]),
            ],
        },
    },
}
needs_default_layout = "slim"
