# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the stage-1 (`xref` builder) warning suppression.

`_quieten_xref_stage` is a `builder-inited` handler, so it is testable without
a Sphinx build: it only reads `app.builder.name` and rewrites two config
values. These tests use a stand-in app for that reason — a real build would
exercise Sphinx's warning machinery rather than this function's own decision.
"""

import types

import xref_builder as xb


def _fake_app(builder_name, suppress=None, mapping=None):
    """Minimal stand-in for the two attributes the handler touches."""
    return types.SimpleNamespace(
        builder=types.SimpleNamespace(name=builder_name),
        config=types.SimpleNamespace(
            suppress_warnings=list(suppress or []),
            intersphinx_mapping=dict(mapping or {"peer": ("http://x", None)}),
        ),
    )


# ---------------------------------------------------------------------------
# the xref stage
# ---------------------------------------------------------------------------


def test_xref_stage_suppresses_every_expected_warning():
    app = _fake_app("xref")
    xb._quieten_xref_stage(app)
    for subtype in xb._EXPECTED_STAGE_ONE_WARNINGS:
        assert subtype in app.config.suppress_warnings


def test_xref_stage_suppresses_the_cross_document_need_warnings():
    """The four subtypes that exist only because `needs_external_needs` is
    gated on a peer's needs.json, which at stage 1 is this stage's own output."""
    app = _fake_app("xref")
    xb._quieten_xref_stage(app)
    for subtype in (
        "needs.link_outgoing",
        "needs.link_ref",
        "needs.external_link_outgoing",
        "sn_schema_warning.network_missing_target",
    ):
        assert subtype in app.config.suppress_warnings, subtype


def test_xref_stage_clears_intersphinx_mapping():
    app = _fake_app("xref")
    xb._quieten_xref_stage(app)
    assert app.config.intersphinx_mapping == {}


def test_xref_stage_extends_rather_than_replaces_consumer_suppressions():
    app = _fake_app("xref", suppress=["toc.excluded"])
    xb._quieten_xref_stage(app)
    assert "toc.excluded" in app.config.suppress_warnings


# ---------------------------------------------------------------------------
# scoping — what must NOT be suppressed
# ---------------------------------------------------------------------------


def test_other_builders_are_untouched():
    """Stage 2 is where these warnings are a real signal, so html must keep
    them AND keep its intersphinx mapping."""
    for name in ("html", "latex"):
        app = _fake_app(name)
        xb._quieten_xref_stage(app)
        assert app.config.suppress_warnings == []
        assert app.config.intersphinx_mapping != {}


def test_schema_suppression_is_scoped_to_one_rule():
    """`network_local_fail` (a link resolving to a need of the WRONG type)
    requires its target to be PRESENT, so the gating never provokes it and it
    must report even at stage 1. Suppressing `sn_schema_warning` wholesale
    would silence it."""
    assert "sn_schema_warning" not in xb._EXPECTED_STAGE_ONE_WARNINGS
    assert not any(
        s.startswith("sn_schema_violation")
        for s in xb._EXPECTED_STAGE_ONE_WARNINGS
    )
    app = _fake_app("xref")
    xb._quieten_xref_stage(app)
    assert "sn_schema_warning.network_local_fail" not in app.config.suppress_warnings
