# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""The PDF set: deploy/pdf holds <title>_<version>.pdf per document, linked to each other."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import docrefs  # noqa: E402

REGISTRY = """\
groups:
  - id: docs
    title: Documents
documents:
  requirement-specification:
    title: "Requirement Specification"
    kind: sphinx
    group: docs
    builders: [html, latex]
  test-report:
    title: "Test Report"
    kind: sphinx
    group: docs
    builders: [html, latex]
  notes:
    title: "Notes"
    kind: sphinx
    group: docs
    builders: [html]
"""


def _registry(tmp_path, text=REGISTRY):
    path = tmp_path / "documents.yaml"
    path.write_text(text)
    return path


@pytest.mark.parametrize(
    "title, version, name",
    [
        ("Requirement Specification", "1.2", "Requirement-Specification_1.2.pdf"),
        ("Test Report", "1.2-3-gabc1234", "Test-Report_1.2-3-gabc1234.pdf"),
        ("API Traceability", "v0.0-dev+ge63ae8c", "API-Traceability_v0.0-dev+ge63ae8c.pdf"),
        (
            "RC ↔ ST Interface Specification",
            "1.0-dirty",
            "RC-ST-Interface-Specification_1.0-dirty.pdf",
        ),
        ("Übersicht: Plan/Ziele", "2.0", "Ubersicht-Plan-Ziele_2.0.pdf"),
        ("Test_Report", "rel/1.0", "TestReport_rel-1.0.pdf"),
    ],
)
def test_pdf_file_name(title, version, name):
    assert docrefs.pdf_file_name(title, version) == name


def test_only_a_document_with_a_latex_builder_is_in_the_set(tmp_path, monkeypatch):
    monkeypatch.setenv("VERSION", "1.2")
    documents = docrefs._registry(_registry(tmp_path))["documents"]
    assert docrefs.pdf_files(documents) == {
        "requirement-specification": "Requirement-Specification_1.2.pdf",
        "test-report": "Test-Report_1.2.pdf",
    }


def test_two_documents_with_one_file_name_are_an_error(tmp_path):
    text = REGISTRY.replace('title: "Test Report"', 'title: "Requirement  Specification"')
    with pytest.raises(ValueError, match="same title in their PDF file name"):
        docrefs.manifest(_registry(tmp_path, text))


def test_deliver_keeps_one_version_of_a_document(tmp_path, monkeypatch):
    registry = _registry(tmp_path)
    pdf_dir = tmp_path / "deploy" / "pdf"
    pdf_dir.mkdir(parents=True)
    (pdf_dir / "Test-Report_1.1.pdf").write_bytes(b"old")
    (pdf_dir / "Test-Report-Annex_1.1.pdf").write_bytes(b"other document")
    latexmk_pdf = tmp_path / "test-report.pdf"
    latexmk_pdf.write_bytes(b"new")
    monkeypatch.setenv("VERSION", "1.2")
    target = docrefs.deliver_pdf("test-report", latexmk_pdf, pdf_dir, registry)
    assert target == pdf_dir / "Test-Report_1.2.pdf"
    assert sorted(p.name for p in pdf_dir.iterdir()) == [
        "Test-Report-Annex_1.1.pdf",
        "Test-Report_1.2.pdf",
    ]
    docrefs.remove_pdfs("test-report", pdf_dir, registry)
    assert [p.name for p in pdf_dir.iterdir()] == ["Test-Report-Annex_1.1.pdf"]


def test_a_pdf_build_knows_the_pdfs_of_its_peers(tmp_path, monkeypatch):
    monkeypatch.setenv("VERSION", "1.2")
    monkeypatch.setenv("ZDOCS_DOC_BASE_URL", "https://docs.example.org/")
    monkeypatch.setenv("ZDOCS_DOC_BUILD_DIR", str(tmp_path))
    monkeypatch.setenv("ZDOCS_DOC_ID", "test-report")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "test-report" / "latex"))
    refs = docrefs.load("test-report", _registry(tmp_path))
    peer = "https://docs.example.org/html/requirement-specification"
    assert refs.pdf_peers == {peer: "Requirement-Specification_1.2.pdf"}
    assert docrefs.build_root() == tmp_path.resolve()
    assert docrefs._this_doc() == "test-report"

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "deploy" / "html" / "test-report"))
    assert docrefs.load("test-report", _registry(tmp_path)).pdf_peers == {}
