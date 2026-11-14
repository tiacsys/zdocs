# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Two registry mistakes that used to pass validation and fail later.

A prefix that two documents share: ``intersphinx_mapping`` and ``doxylink``
are keyed by prefix, so one document replaced the other, without a message.

A group id that gives a document's target name: the ``<group>-<builder>``
aggregate of ``add_docs_from_registry`` and the document's own
``<id>-<builder>`` target had the same name, and CMake stopped with a message
that did not name the registry.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import docrefs  # noqa: E402

BASE = """\
groups:
  - id: guides
    title: Guides
  - id: api
    title: API
documents:
  handbook:
    group: guides
    builders: [html]
  runbook:
    group: guides
    builders: [html, latex]
  widget:
    kind: doxygen
    group: api
"""


def _validate(text, tmp_path):
    path = tmp_path / "documents.yaml"
    path.write_text(text)
    return docrefs.manifest(registry=path)


def test_the_base_registry_is_valid(tmp_path):
    assert [e["id"] for e in _validate(BASE, tmp_path)] == ["handbook", "runbook", "widget"]


# ---------------------------------------------------------------------------
# Prefixes
# ---------------------------------------------------------------------------


def test_two_sphinx_documents_with_one_prefix_are_rejected(tmp_path):
    text = BASE.replace("    builders: [html]\n", "    builders: [html]\n    prefix: shared\n", 1)
    text = text.replace(
        "    builders: [html, latex]\n", "    builders: [html, latex]\n    prefix: shared\n"
    )
    with pytest.raises(ValueError, match=r"'handbook' and 'runbook' have the same prefix 'shared'"):
        _validate(text, tmp_path)


def test_a_default_prefix_counts_too(tmp_path):
    # `my-doc` has the default prefix `my_doc`, which `my_doc` spells out.
    text = BASE + (
        "  my-doc:\n    group: guides\n    builders: [html]\n"
        "  other:\n    group: guides\n    builders: [html]\n    prefix: my_doc\n"
    )
    with pytest.raises(ValueError, match=r"'my-doc' and 'other' have the same prefix 'my_doc'"):
        _validate(text, tmp_path)


def test_a_sphinx_external_document_shares_the_intersphinx_map(tmp_path):
    text = BASE + (
        "  upstream:\n    kind: sphinx-external\n    group: guides\n"
        "    remote-url: https://example.org/\n    prefix: handbook\n"
    )
    with pytest.raises(ValueError, match="intersphinx_mapping is keyed by prefix"):
        _validate(text, tmp_path)


def test_two_doxygen_documents_with_one_prefix_are_rejected(tmp_path):
    text = BASE + "  gadget:\n    kind: doxygen\n    group: api\n    prefix: widget\n"
    with pytest.raises(ValueError, match="doxylink is keyed by prefix"):
        _validate(text, tmp_path)


def test_a_sphinx_and_a_doxygen_document_may_share_a_prefix(tmp_path):
    # Two maps, two roles: no entry replaces another.
    text = BASE + "  widget-guide:\n    group: guides\n    builders: [html]\n    prefix: widget\n"
    _validate(text, tmp_path)


def test_external_and_isolated_documents_have_no_prefix_in_use(tmp_path):
    text = BASE + (
        "  sop:\n    kind: external\n    group: guides\n    remote-url: sop.html\n"
        "    prefix: handbook\n"
        "  full-api:\n    kind: doxygen\n    group: api\n    crossref: false\n"
        "    prefix: widget\n"
    )
    _validate(text, tmp_path)


# ---------------------------------------------------------------------------
# Group ids and target names
# ---------------------------------------------------------------------------


def test_a_group_named_like_a_document_of_its_builder_is_rejected(tmp_path):
    # doc/documents.yaml's own case: a group `manual` with a document `manual`.
    text = BASE.replace("id: guides", "id: handbook").replace("group: guides", "group: handbook")
    with pytest.raises(
        ValueError,
        match=r"group 'handbook' and document 'handbook' both make the CMake target "
        r"'handbook-html'",
    ):
        _validate(text, tmp_path)


def test_a_doxygen_document_counts_as_html(tmp_path):
    # Group `api` makes api-html; a Sphinx document `api` with html makes it too.
    text = BASE + "  api:\n    group: guides\n    builders: [html]\n"
    with pytest.raises(ValueError, match=r"group 'api' and document 'api'.*'api-html'"):
        _validate(text, tmp_path)


def test_the_clash_needs_the_same_builder(tmp_path):
    # Group `widget` makes widget-html; the Doxygen document `widget` makes the
    # targets widget, widget-nodeps, widget-tag and widget-clean: no clash.
    text = BASE.replace("id: api", "id: widget").replace("group: api", "group: widget")
    _validate(text, tmp_path)


def test_a_group_named_like_an_external_document_is_valid(tmp_path):
    # An external document makes no target.
    text = BASE.replace("id: guides", "id: sop").replace("group: guides", "group: sop") + (
        "  sop:\n    kind: external\n    group: api\n    remote-url: sop.html\n"
    )
    _validate(text, tmp_path)
