# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``imports:`` — a document imports the needs of the documents it lists.

Without it every document imports the needs of every needs-publishing peer.
A downstream set that builds upstream documents then had to list every
indirect upstream document, and each needs warning repeated once per
importing document. With it, a document imports from the documents it lists
and, transitively, from the documents those list in their own ``imports:``.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import docrefs  # noqa: E402

# stkreq <- sysreq <- swreq <- swtest; `index` imports everything (no list);
# `notes` publishes no needs.
REGISTRY = """\
groups:
  - id: all
    title: All
documents:
  stkreq:
    group: all
    builders: [html]
    needs: {source: json}
    imports: []
  sysreq:
    group: all
    builders: [html]
    needs: {source: json}
    imports: [stkreq]
  swreq:
    group: all
    builders: [html]
    needs: {source: json}
    imports: [sysreq]
  swtest:
    group: all
    builders: [html]
    needs: {source: json}
    imports: [swreq]
  index:
    group: all
    builders: [html]
    needs: {source: json}
  notes:
    group: all
    builders: [html]
"""

NEEDS_DOCS = ("stkreq", "sysreq", "swreq", "swtest", "index")


@pytest.fixture
def load(tmp_path, monkeypatch):
    registry = tmp_path / "documents.yaml"
    registry.write_text(REGISTRY)
    for doc_id in NEEDS_DOCS:  # every peer has exported its needs (stage 2)
        out = tmp_path / "deploy" / "html" / doc_id
        out.mkdir(parents=True)
        (out / "needs.json").write_text("{}")

    def _load(doc_id, text=None):
        if text is not None:
            registry.write_text(text)
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "deploy" / "html" / doc_id))
        refs = docrefs.load(doc_id, registry=registry)
        return sorted(Path(e["json_path"]).parent.name for e in refs.needs_external_needs)

    return _load


def test_without_imports_a_document_imports_every_peer(load):
    assert load("index") == ["stkreq", "swreq", "swtest", "sysreq"]


def test_an_empty_list_imports_nothing(load):
    assert load("stkreq") == []


def test_a_document_imports_what_it_lists(load):
    assert load("sysreq") == ["stkreq"]


def test_the_imports_of_an_imported_document_are_followed(load):
    # swtest lists only swreq; swreq's needs link into sysreq, and sysreq's
    # into stkreq, so both come along without being listed.
    assert load("swtest") == ["stkreq", "swreq", "sysreq"]


def test_a_listed_document_without_imports_adds_only_itself(load):
    text = REGISTRY.replace("    imports: [stkreq]\n", "")
    assert load("swreq", text) == ["sysreq"]


def test_a_cycle_ends_and_leaves_the_document_out(load):
    text = REGISTRY.replace("    imports: []\n", "    imports: [swtest]\n")
    assert load("sysreq", text) == ["stkreq", "swreq", "swtest"]


def test_imports_change_only_the_needs(load, tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "deploy" / "html" / "stkreq"))
    refs = docrefs.load("stkreq", registry=tmp_path / "documents.yaml")
    assert set(refs.intersphinx_mapping) == {"sysreq", "swreq", "swtest", "index", "notes"}


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("    imports: sysreq\n", "use a list of document ids"),
        ("    imports: [missing]\n", "imports 'missing', which does not exist"),
        ("    imports: [notes]\n", "imports 'notes', which publishes no needs"),
        ("    imports: [index]\n    crossref: false\n", "'imports:' and 'crossref: false'"),
    ],
)
def test_a_bad_imports_list_is_a_configure_error(tmp_path, entry, message):
    text = REGISTRY.replace("    imports: [sysreq]\n", entry)
    path = tmp_path / "documents.yaml"
    path.write_text(text)
    with pytest.raises(ValueError, match=message):
        docrefs.manifest(registry=path)


def test_a_document_cannot_import_itself(tmp_path):
    path = tmp_path / "documents.yaml"
    path.write_text(REGISTRY.replace("imports: [sysreq]", "imports: [swreq]"))
    with pytest.raises(ValueError, match="'swreq' imports itself"):
        docrefs.manifest(registry=path)


def test_only_a_sphinx_document_imports(tmp_path):
    path = tmp_path / "documents.yaml"
    path.write_text(REGISTRY + "  api:\n    kind: doxygen\n    group: all\n    imports: []\n")
    with pytest.raises(ValueError, match="only a 'kind: sphinx' document imports needs"):
        docrefs.manifest(registry=path)
