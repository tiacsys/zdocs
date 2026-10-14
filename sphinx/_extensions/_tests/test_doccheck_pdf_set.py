# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""doccheck: a link from one PDF of deploy/pdf into another must have a target."""

import subprocess
import sys
from pathlib import Path

import pytest

DOCCHECK = Path(__file__).resolve().parents[3] / "scripts" / "doccheck.py"


def _pdf(path, dests=(), links=()):
    """A one-page PDF with named destinations and GoToR links (file, dest)."""
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        FloatObject,
        NameObject,
        TextStringObject,
    )

    writer = pypdf.PdfWriter()
    writer.add_blank_page(200, 200)
    for dest in dests:
        writer.add_named_destination(dest, 0)
    annots = ArrayObject()
    for target, dest in links:
        annots.append(writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Link"),
            NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (0, 0, 10, 10)]),
            NameObject("/A"): DictionaryObject({
                NameObject("/S"): NameObject("/GoToR"),
                NameObject("/F"): TextStringObject(target),
                NameObject("/D"): TextStringObject(dest),
            }),
        })))
    writer.pages[0][NameObject("/Annots")] = annots
    with open(path, "wb") as f:
        writer.write(f)


def _doccheck(tmp_path, deploy):
    registry = tmp_path / "documents.yaml"
    registry.write_text('base_url: "http://localhost:8000/"\n')
    return subprocess.run(
        [sys.executable, DOCCHECK, "--registry", registry, "--deploy", deploy],
        capture_output=True,
        text=True,
    )


def test_doccheck_follows_the_links_between_the_pdfs(tmp_path):
    pdf_dir = tmp_path / "deploy" / "pdf"
    pdf_dir.mkdir(parents=True)
    _pdf(pdf_dir / "Requirement-Specification_1.2.pdf", dests=["detailed:SD-REQ-001"])
    _pdf(
        pdf_dir / "Test-Report_1.2.pdf",
        links=[
            ("Requirement-Specification_1.2.pdf", "detailed:SD-REQ-001"),
            ("Requirement-Specification_1.2.pdf", "detailed:SD-REQ-999"),
            ("Test-Specification_1.2.pdf", "spec:TC_1"),
        ],
    )
    result = _doccheck(tmp_path, tmp_path / "deploy")
    assert result.returncode == 1
    assert "dead links between the PDFs (2)" in result.stderr
    assert (
        "pdf/Test-Report_1.2.pdf: dead link -> Requirement-Specification_1.2.pdf"
        "#detailed:SD-REQ-999 (no such destination)" in result.stderr
    )
    assert "Test-Specification_1.2.pdf#spec:TC_1 (no such PDF in deploy/pdf)" in result.stderr
    assert "SD-REQ-001 (" not in result.stderr
