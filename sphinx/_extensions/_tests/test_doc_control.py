# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the ``doc_control`` directive's identity fields.

STATUS: RED BY DESIGN. See
``.claude/zdocs/zdocs-brief-doc-control-identity.md`` (the brief this module
implements) for the full defect writeup; the one-line version: ``Title`` and
``Document Id`` both describe whatever precedes ``.. doc_control::`` in the
file it happens to sit in, rather than the controlled document itself.
``Title`` comes from ``doctree.next_node(nodes.title)`` at parse time (so a
preceding heading, or even a preceding ``.. todo::`` admonition's own
generated title node, wins); ``Document Id`` comes from
``posixpath.basename(env.docname)`` (the *fragment's* docname, not the
document's registry id).

The extension has no unit coverage today (brief decision 8), so this whole
module is new. It uses four dedicated roots under ``roots/test-doc-control-*``
that differ ONLY in what precedes the directive (brief decision 7) --
proving placement independence without touching any ACME fixture document
(decision 6). Three of the four ("heading", "admonition", "bare") set the
same ``project`` and the same ``zdocs_doc_id`` and must, once fixed, publish
identical identity rows; the fourth ("fallback") sets no ``zdocs_doc_id`` at
all, pinning the decision-3 standalone fallback
(``posixpath.basename(env.docname)``) as deliberate rather than accidental.

Every assertion here reads RENDERED HTML (rule 4) -- never ``app.config`` --
so a fix that keeps reading the doctree, or that reads
``app.config.zdocs_doc_id`` without registering it, cannot pass by
accident (and the latter would raise ``AttributeError`` at build time
rather than silently passing, per the brief's own §5 note).

PHASE-1 REVIEW FIX (coordinator, this phase): every Title/Document-Id pair
below used to be asserted in ONE test function, Title first. Since pytest
stops a test at its first failing assert, and Title fails first in every
one of those cases today, not one Document-Id assertion had ever actually
executed -- a real defect in the tests themselves, not a stylistic
preference. Title and Document Id are now separate test functions
throughout, so each claim produces its own independent, INDEPENDENTLY
VERIFIED red. The placement-independence test also used to assert only
that the three roots AGREE with each other (``len(set(...)) == 1``), which
is vacuous for Document Id: all three roots put the directive in their own
``index.rst``, so all three already publish the identical (wrong) value
"index" today, regardless of whether ``_extract_document_id()`` is ever
touched. Fixed to assert the shared value equals the constant
(``PROJECT``/``DOC_ID``), which cannot pass by accident.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

_ROOTS = Path(__file__).parent / "roots"

# The three placement roots (brief decision 7): same project, same
# zdocs_doc_id, differing only in what precedes ".. doc_control::".
PROJECT = "Meridian Assurance Manual"
DOC_ID = "meridian-qms"

_PLACEMENT_ROOTS = (
    "test-doc-control-heading",
    "test-doc-control-admonition",
    "test-doc-control-bare",
)


def _identity(html_path: Path) -> dict[str, str]:
    """The rendered ``doc_control`` table of `html_path`, as {label: value}.

    Same shape as ``zdocs-tests/tests/conftest.py``'s ``doc_control_table()``
    (labels lower-cased, cell text tag-stripped), but standalone: these unit
    roots build with the plain "alabaster" theme, which has no
    ``itemprop="articleBody"`` wrapper to scope against, so there is nothing
    to slice out first. Cell text is HTML-unescaped (``doc_control.py``'s
    ``"<no title>"`` fallback renders as ``&lt;no title&gt;``).
    """
    page = html_path.read_text(encoding="utf-8", errors="replace")
    table = re.search(r'<table class="[^"]*doc-ctrl.*?</table>', page, re.S)
    assert table, f"no doc_control table in {html_path}:\n{page[:600]}"

    fields = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(0), re.S):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", cell).strip())
            for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        ]
        if len(cells) == 2:
            fields[cells[0].lower()] = cells[1]
    return fields


# ---------------------------------------------------------------------------
# Claim 1: each placement root publishes Title == project.
# ---------------------------------------------------------------------------


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-doc-control-heading"))
def test_heading_root_title_is_the_configured_project(app):
    """Today, a heading preceding the directive wins: Title becomes the
    heading's own text ("Falcon Bay Notes"), not the configured project."""
    app.build()
    fields = _identity(Path(app.outdir) / "index.html")
    assert fields.get("title") == PROJECT, (
        f"title: {fields.get('title')!r} != {PROJECT!r} "
        "(doctree.next_node(nodes.title) found the preceding heading instead "
        "of reading env.config.project)"
    )


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-doc-control-admonition"))
def test_admonition_root_title_is_the_configured_project(app):
    """Today, a ``.. todo::`` block preceding the directive wins: its own
    generated title node ("Todo") is what next_node(nodes.title) finds
    first, so Title becomes "Todo"."""
    app.build()
    fields = _identity(Path(app.outdir) / "index.html")
    assert fields.get("title") == PROJECT, (
        f"title: {fields.get('title')!r} != {PROJECT!r} "
        "(the todo admonition's own title node was read instead of "
        "env.config.project)"
    )


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-doc-control-bare"))
def test_bare_root_title_is_the_configured_project(app):
    """Today, nothing at all precedes the directive: next_node(nodes.title)
    finds no title node, so Title becomes the literal "<no title>"."""
    app.build()
    fields = _identity(Path(app.outdir) / "index.html")
    assert fields.get("title") == PROJECT, (
        f"title: {fields.get('title')!r} != {PROJECT!r} "
        "(no title node exists, so _determine_doc_title() fell back to "
        "the literal '<no title>' instead of reading env.config.project)"
    )


# ---------------------------------------------------------------------------
# Claim 2: each placement root publishes Document Id == zdocs_doc_id.
#
# Separate functions from claim 1's, on purpose (phase-1 review fix): all
# three roots put the directive directly in their own index.rst, so all
# three currently publish Document Id "index" -- the SAME wrong value that
# Title's own defect would otherwise mask if these lived in the same
# function and Title's assertion failed first.
# ---------------------------------------------------------------------------


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-doc-control-heading"))
def test_heading_root_document_id_is_the_configured_doc_id(app):
    app.build()
    fields = _identity(Path(app.outdir) / "index.html")
    assert fields.get("document id") == DOC_ID, (
        f"document id: {fields.get('document id')!r} != {DOC_ID!r} "
        "(posixpath.basename(env.docname) was used instead of zdocs_doc_id)"
    )


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-doc-control-admonition"))
def test_admonition_root_document_id_is_the_configured_doc_id(app):
    app.build()
    fields = _identity(Path(app.outdir) / "index.html")
    assert fields.get("document id") == DOC_ID, (
        f"document id: {fields.get('document id')!r} != {DOC_ID!r} "
        "(posixpath.basename(env.docname) was used instead of zdocs_doc_id)"
    )


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-doc-control-bare"))
def test_bare_root_document_id_is_the_configured_doc_id(app):
    app.build()
    fields = _identity(Path(app.outdir) / "index.html")
    assert fields.get("document id") == DOC_ID, (
        f"document id: {fields.get('document id')!r} != {DOC_ID!r} "
        "(posixpath.basename(env.docname) was used instead of zdocs_doc_id)"
    )


# ---------------------------------------------------------------------------
# Claim 3: placement independence, stated directly -- the three roots must
# publish the SAME Title and the SAME Document Id as each other, AND that
# shared value must be the configured one (PROJECT / DOC_ID) -- not merely
# mutual agreement. Mutual-agreement-only would be vacuous for Document Id:
# all three roots put the directive in their own index.rst, so all three
# already publish the identical "index" today, and would keep agreeing with
# each other under ANY implementation, including one that never touches
# _extract_document_id() at all.
# ---------------------------------------------------------------------------


def _build_all_placements(make_app) -> dict[str, dict[str, str]]:
    identities = {}
    for root in _PLACEMENT_ROOTS:
        srcdir = _ROOTS / root
        built_app = make_app("html", srcdir=srcdir, builddir=srcdir / "_build")
        built_app.build()
        identities[root] = _identity(Path(built_app.outdir) / "index.html")
    return identities


def test_the_three_placements_publish_the_configured_title(make_app):
    """Today these three disagree ("Falcon Bay Notes" / "Todo" / "<no
    title>") even though all three configure the SAME project. Asserting
    merely that they agree with each other would also be satisfied by an
    implementation that made all three identically wrong (e.g. all three
    reading some other shared, incorrect source) -- so this asserts the
    shared value equals PROJECT, not just that the three match.
    """
    identities = _build_all_placements(make_app)
    titles = {root: fields.get("title") for root, fields in identities.items()}
    assert set(titles.values()) == {PROJECT}, (
        f"the three placement roots do not all publish {PROJECT!r}: {titles}"
    )


def test_the_three_placements_publish_the_configured_document_id(make_app):
    """Today all three publish Document Id "index" -- NOT because placement
    is correctly ignored, but because all three roots happen to put the
    directive directly in their own index.rst (so
    posixpath.basename(env.docname) == "index" for all three by
    coincidence). Asserting only mutual agreement
    (``len(set(doc_ids.values())) == 1``) would already be true today and
    would stay true under any implementation, including one that never
    touches ``_extract_document_id()`` -- a mask, not a safety net. This
    asserts the shared value equals DOC_ID instead.
    """
    identities = _build_all_placements(make_app)
    doc_ids = {root: fields.get("document id") for root, fields in identities.items()}
    assert set(doc_ids.values()) == {DOC_ID}, (
        f"the three placement roots do not all publish {DOC_ID!r}: {doc_ids}"
    )


# ---------------------------------------------------------------------------
# Claim 4: the decision-3 fallback. No zdocs_doc_id set at all (the
# standalone-extension path) -> Document Id falls back to
# posixpath.basename(env.docname). Pinned, not left accidental.
# ---------------------------------------------------------------------------


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-doc-control-fallback"))
def test_fallback_document_id_is_the_docname_basename_when_no_doc_id_configured(app):
    app.build()
    fields = _identity(Path(app.outdir) / "doc-control.html")
    assert fields.get("document id") == "doc-control", (
        f"document id: {fields.get('document id')!r} != 'doc-control' "
        "-- with no zdocs_doc_id configured, the standalone path must still "
        "fall back to posixpath.basename(env.docname) ('doc-control', "
        "since the directive lives in doc-control.rst reached via toctree)"
    )


# ---------------------------------------------------------------------------
# Claim 5: the fixture invariant itself. Every placement root's project must
# share no substring (>=3 chars) with any heading/admonition-title text in
# its own index.rst, so an implementation that keeps reading the doctree
# cannot pass claims 1-3 by accident. A pin on the fixture, not on
# doc_control.py -- it protects the roots above from an edit that
# accidentally reintroduces an overlap.
# ---------------------------------------------------------------------------


def _shares_substring(a: str, b: str, minlen: int = 3) -> str | None:
    a, b = a.lower(), b.lower()
    for i in range(len(a)):
        for j in range(i + minlen, len(a) + 1):
            sub = a[i:j]
            if sub in b:
                return sub
    return None


def test_fixture_projects_share_no_substring_with_their_headings():
    # What must literally appear in each root's index.rst, to guard against
    # the fixture drifting out from under this test's premise (what precedes
    # the directive) without anyone noticing.
    literal_markers = {
        "test-doc-control-heading": "Falcon Bay Notes",
        "test-doc-control-admonition": ".. todo::",
        # "bare" has nothing at all preceding the directive -- no marker to
        # check for.
    }
    for root, marker in literal_markers.items():
        rst = (_ROOTS / root / "index.rst").read_text(encoding="utf-8")
        assert marker in rst, (
            f"fixture drift: {marker!r} is no longer in {root}/index.rst; "
            "this test's premise (what precedes the directive) no longer "
            "holds for that root"
        )

    # What today's (defective) _determine_doc_title() actually renders for
    # each placement -- "Todo" is the todo-admonition's own GENERATED title
    # node, not authored text, so it cannot be grepped out of the rst above.
    rendered_titles = {
        "test-doc-control-heading": "Falcon Bay Notes",
        "test-doc-control-admonition": "Todo",
        "test-doc-control-bare": "<no title>",
    }
    for root, title in rendered_titles.items():
        overlap = _shares_substring(PROJECT, title)
        assert overlap is None, (
            f"{root}: project {PROJECT!r} shares substring {overlap!r} with "
            f"today's rendered title {title!r} -- an implementation that "
            "still reads the doctree's title node could pass by accident"
        )
