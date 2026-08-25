# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Directive-level (end-to-end) tests for the configurable need-type / link-
type role->name mapping (zdocs step 26).

STATUS: RED BY DESIGN, for the same reason as test_needtype_mapping.py: the
feature does not exist yet. These exercise the wiring from Sphinx config
through to emitted RST via the actual `testmodule`/`testreport` directives
and real sphinx-needs registration, using dedicated test roots under
roots/test-*-mapping and roots/test-testmodule-partial-mapping.

Empirically verified (2026-08-11, ad-hoc script against a scratch copy of
these roots) rather than assumed: with `testmodule_need_types` /
`testmodule_need_links` unregistered, Sphinx does NOT reject the conf.py
assignment and does NOT raise -- `app.build()` completes normally with
`app.config.testmodule_need_types` simply absent (AttributeError if
accessed, silently ignored otherwise). The directives keep emitting the OLD
literal names, which no longer match what the test roots' `needs_types` /
`needs_links` declare (since those roots declare the NEW consumer names, as
a real adopter of this feature would). docutils therefore reports the
emitted directive as unknown, which surfaces as a `sphinx.util.logging`
WARNING (captured by the `warning` fixture) rather than a raised exception,
and the corresponding need/table row is simply absent from the rendered
HTML. So the expected red here is a clean pytest FAILED (AssertionError on
`warning.getvalue()` or on missing HTML content) -- not ERRORED. See the
step 26 test report for the exact `-q` output confirming this.
"""
from pathlib import Path

import pytest

_ROOTS = Path(__file__).parent / "roots"

_MAPPING_ROOTS = (
    "test-testmodule-mapping",
    "test-testmodule-partial-mapping",
    "test-testreport-mapping",
)


# The stale-doctree guard this file used to carry is now GLOBAL, in
# conftest.py's _fresh_sphinx_build_dirs — it turned out the pre-existing
# directive tests needed it just as badly. See that docstring.


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule-mapping"))
def test_testmodule_directive_mapping_builds_without_warnings(app, warning):
    app.build()
    assert not warning.getvalue()


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule-mapping"))
def test_testmodule_directive_honours_case_type_mapping(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "TSPEC-QUEUE-API-001" in html
    assert "TSPEC-QUEUE-API-002" in html


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule-mapping"))
def test_testmodule_directive_honours_procedure_type_mapping(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "test-proc-queue_procedures-setup_queue" in html


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule-mapping"))
def test_testmodule_directive_honours_verifies_link_mapping(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "endorses" in html
    assert "needs_verifies" not in html


# ---------------------------------------------------------------------------
# testmodule directive: PARTIAL mapping — only "case" overridden, "procedure"
# and the "verifies" link left unset and must fall back to defaults.
# ---------------------------------------------------------------------------

@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule-partial-mapping"))
def test_testmodule_directive_partial_mapping_builds_without_warnings(app, warning):
    app.build()
    assert not warning.getvalue()


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule-partial-mapping"))
def test_testmodule_directive_partial_mapping_case_overridden(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    # "case" role was overridden to "tc_item" -- both test_case needs must
    # still render under the new directive name.
    assert "TSPEC-QUEUE-API-001" in html
    assert "TSPEC-QUEUE-API-002" in html


# NOTE: a test asserting that the UNMAPPED "procedure" role still renders
# under its default name in this root was deliberately left out. It would
# pass today exactly as it would after the feature ships (nothing about
# "procedure" changes either way in this root), so it cannot discriminate
# an implementation that honours the fallback from one that never reads
# testmodule_need_types at all -- the same defect class the brief (§4)
# warns about for substring-sharing override names. The fallback-to-default
# guarantee is instead pinned where it CAN fail today: at the rst_builders /
# test_module unit level (test_needtype_mapping.py's partial-mapping tests),
# where the same call is made once with the new parameter and once without.


# ---------------------------------------------------------------------------
# testreport directive: full mapping (result, result_of, covers), including
# the engine's own needtable :filter:/:columns: (brief §3 decision 2) — the
# site most likely to be missed, per the brief.
# ---------------------------------------------------------------------------

@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport-mapping"))
def test_testreport_directive_mapping_builds_without_warnings(app, warning):
    app.build()
    assert not warning.getvalue()


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport-mapping"))
def test_testreport_directive_honours_result_type_mapping(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "TR-qemu-cortex-m3-ti-lm3s6965-kernel-queue-TSPEC-QUEUE-API-001" in html
    assert "TR-qemu-cortex-m3-ti-lm3s6965-kernel-queue-TSPEC-QUEUE-API-002" in html


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport-mapping"))
def test_testreport_directive_honours_result_of_and_covers_link_mapping(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "produced_by" in html
    assert "addresses" in html


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport-mapping"))
def test_testreport_directive_summary_table_not_empty(app):
    """Pins brief §3 decision 2: the engine's own needtable must go through
    the mapping too, or a renamed type/link produces a green build with a
    silently empty summary table."""
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    idx = html.find("Result summary")
    assert idx != -1
    table_region = html[idx:idx + 4000]
    assert "TR-qemu-cortex-m3-ti-lm3s6965-kernel-queue-TSPEC-QUEUE-API-001" in table_region
