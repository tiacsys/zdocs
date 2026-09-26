# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``crossref: false`` removes a document from the link graph in both
directions, while keeping it in the navigation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import docrefs  # noqa: E402

REGISTRY = """\
base_url: "http://localhost:8000/"
groups:
  - id: reference
    title: Reference
documents:
  guide:
    kind: sphinx
    group: reference
    builders: [html]
    needs:
      source: json
  api:
    kind: doxygen
    group: reference
  design:
    kind: doxygen
    group: reference
  full-api:
    kind: doxygen
    group: reference
    crossref: false
"""


@pytest.fixture
def registry(tmp_path):
    path = tmp_path / "documents.yaml"
    path.write_text(REGISTRY)
    return path


@pytest.fixture
def load(registry, tmp_path, monkeypatch):
    def _load(doc_id):
        # load() derives the build root from the per-target OUTPUT_DIR.
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "deploy" / "html" / doc_id))
        return docrefs.load(doc_id, registry=registry)

    return _load


def test_tagfiles_skip_an_isolated_peer(registry, tmp_path):
    entries = docrefs.tagfiles("api", tmp_path / "deploy", registry=registry)
    assert "html/design/doxygen.tag" in entries
    assert "full-api" not in entries


def test_isolated_document_imports_no_tagfiles(registry, tmp_path):
    assert docrefs.tagfiles("full-api", tmp_path / "deploy", registry=registry) == ""


def test_load_skips_an_isolated_peer(load):
    refs = load("guide")
    assert set(refs.doxylink) == {"api", "design"}


def test_isolated_document_gets_no_link_maps(load):
    refs = load("full-api")
    assert refs.doxylink == {}
    assert refs.intersphinx_mapping == {}
    assert refs.needs_external_needs == []


def test_isolated_document_stays_in_navigation(load):
    refs = load("guide")
    hrefs = [link["href"] for group in refs.reference_groups for link in group["links"]]
    assert "../full-api/index.html" in hrefs


def test_crossref_must_be_a_boolean(tmp_path):
    path = tmp_path / "documents.yaml"
    path.write_text(REGISTRY.replace("crossref: false", 'crossref: "false"'))
    with pytest.raises(ValueError, match="not a boolean"):
        docrefs.tagfiles("api", tmp_path / "deploy", registry=path)
