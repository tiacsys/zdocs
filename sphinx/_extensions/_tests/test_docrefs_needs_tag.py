# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``doxygen_tag:`` publishes a Sphinx document's needs as a Doxygen tag file,
so ``\\verifies`` / ``\\satisfies`` resolve against requirements authored in rst."""

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import docrefs  # noqa: E402

REGISTRY = """\
groups:
  - id: reference
    title: Reference
documents:
  requirements:
    kind: sphinx
    group: reference
    builders: [html]
    needs:
      source: json
    doxygen_tag:
      types: [requirement, top_requirement]
  api:
    kind: doxygen
    group: reference
  full-api:
    kind: doxygen
    group: reference
    crossref: false
"""

NEEDS = {
    "SD-REQ-001": {
        "id": "SD-REQ-001",
        "title": "Sealing <on> initialisation & more",
        "type": "requirement",
        "docname": "detailed",
        "is_external": False,
    },
    "SD-TOP-001": {
        "id": "SD-TOP-001",
        "title": "Integrity detection",
        "type": "top_requirement",
        "docname": "sub/top-level",
        "is_external": False,
    },
    "TC_ONE": {
        "id": "TC_ONE",
        "title": "A test case",
        "type": "test_case",
        "docname": "tests",
        "is_external": False,
    },
    "PEER-001": {
        "id": "PEER-001",
        "title": "Imported",
        "type": "requirement",
        "docname": None,
        "is_external": True,
    },
}


def _write_registry(tmp_path, text=REGISTRY):
    path = tmp_path / "documents.yaml"
    path.write_text(text)
    return path


@pytest.fixture
def registry(tmp_path):
    return _write_registry(tmp_path)


@pytest.fixture
def deploy(tmp_path):
    html = tmp_path / "deploy" / "html" / "requirements"
    html.mkdir(parents=True)
    export = {"current_version": "v1", "versions": {"v1": {"needs": NEEDS}}}
    (html / "needs.json").write_text(json.dumps(export))
    return tmp_path / "deploy"


def _compounds(path):
    root = ET.parse(path).getroot()
    return {
        c.findtext("id"): (c.get("kind"), c.findtext("title"), c.findtext("filename"))
        for c in root.iter("compound")
    }


def test_tag_declares_each_own_need_of_the_selected_types(registry, deploy):
    out = docrefs.needs_tag("requirements", deploy, registry=registry)
    assert out == deploy / "html" / "requirements" / docrefs.NEEDS_TAGFILE
    assert _compounds(out) == {
        "SD-REQ-001": ("requirement", "Sealing <on> initialisation & more", "detailed.html"),
        "SD-TOP-001": ("requirement", "Integrity detection", "sub/top-level.html"),
    }


def test_true_selects_every_type_but_never_imported_needs(tmp_path, deploy):
    registry = _write_registry(
        tmp_path,
        REGISTRY.replace(
            "doxygen_tag:\n      types: [requirement, top_requirement]", "doxygen_tag: true"
        ),
    )
    ids = set(_compounds(docrefs.needs_tag("requirements", deploy, registry=registry)))
    assert ids == {"SD-REQ-001", "SD-TOP-001", "TC_ONE"}


def test_unchanged_content_is_not_rewritten(registry, deploy):
    out = docrefs.needs_tag("requirements", deploy, registry=registry)
    stamp = out.stat().st_mtime_ns

    os.utime(out, ns=(stamp - 10**9, stamp - 10**9))
    docrefs.needs_tag("requirements", deploy, registry=registry)
    assert out.stat().st_mtime_ns == stamp - 10**9


def test_missing_export_names_the_document(registry, tmp_path):
    with pytest.raises(ValueError, match="stage-1 index"):
        docrefs.needs_tag("requirements", tmp_path / "nowhere", registry=registry)


def test_doxygen_peers_list_the_tag_relative_to_their_html(registry, tmp_path):
    entries = docrefs.tagfiles("api", tmp_path / "deploy", registry=registry)
    assert f"html/requirements/{docrefs.NEEDS_TAGFILE}=../requirements" in entries


def test_omitted_kind_counts_as_sphinx(tmp_path):
    registry = _write_registry(tmp_path, REGISTRY.replace("    kind: sphinx\n", "", 1))
    entries = docrefs.tagfiles("api", tmp_path / "deploy", registry=registry)
    assert f"html/requirements/{docrefs.NEEDS_TAGFILE}" in entries


def test_isolated_peer_gets_no_needs_tag(registry, tmp_path):
    assert docrefs.tagfiles("full-api", tmp_path / "deploy", registry=registry) == ""


def test_manifest_flags_the_document(registry):
    flags = {e["id"]: e["doxygen_tag"] for e in docrefs.manifest(registry)}
    assert flags == {"requirements": True, "api": False, "full-api": False}


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ("    needs:\n      source: json\n", "", "needs: {source: json}"),
        ("types: [requirement, top_requirement]", "typez: [requirement]", "unknown key"),
        ("types: [requirement, top_requirement]", "types: []", "non-empty list"),
        ("types: [requirement, top_requirement]", "types: requirement", "non-empty list"),
        (
            "    doxygen_tag:\n      types: [requirement, top_requirement]\n",
            "    doxygen_tag: false\n",
            "use 'true' or a mapping",
        ),
    ],
)
def test_invalid_declarations_fail_validation(tmp_path, before, after, message):
    assert before in REGISTRY
    registry = _write_registry(tmp_path, REGISTRY.replace(before, after))
    with pytest.raises(ValueError, match=message):
        docrefs.manifest(registry)


def test_only_a_sphinx_document_can_publish_one(tmp_path):
    registry = _write_registry(
        tmp_path,
        REGISTRY.replace(
            "  api:\n    kind: doxygen\n", "  api:\n    kind: doxygen\n    doxygen_tag: true\n"
        ),
    )
    with pytest.raises(ValueError, match="only a 'kind: sphinx' document"):
        docrefs.manifest(registry)
