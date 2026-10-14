# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""zdocs_conf: the PDF loads zdocs.sty, then a consumer's style file."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # sphinx/
import zdocs_conf  # noqa: E402

STY = Path(zdocs_conf.__file__).parent / "_latex" / "zdocs.sty"


def _configure(tmp_path, monkeypatch, **kwargs):
    monkeypatch.setenv("VERSION", "1.2")
    for name in ("ZDOCS_REGISTRY", "ZDOCS_PROJECT_BASE", "LATEX_DOC"):
        monkeypatch.delenv(name, raising=False)
    doc_dir = tmp_path / "handbook"
    doc_dir.mkdir()
    namespace = {}
    zdocs_conf.configure(namespace, doc_dir, **kwargs)
    return namespace


def test_the_pdf_loads_zdocs_sty_with_the_values_of_the_build(tmp_path, monkeypatch):
    namespace = _configure(tmp_path, monkeypatch, project="R&D Handbook", copyright_holder="Smith & Co")
    assert namespace["latex_additional_files"] == [str(STY)]
    preamble = namespace["latex_elements"]["preamble"]
    assert preamble.startswith("\\usepackage{zdocs}\n")
    assert "title={R\\&D Handbook}" in preamble
    assert "version={1.2}" in preamble
    assert "footer={Copyright " in preamble and "Smith \\& Co}" in preamble
    assert "docid={handbook}" in preamble
    assert "set={}" in preamble  # no registry, no set
    assert "All rights reserved" not in preamble


def test_the_title_page_names_the_pdfs_of_the_set(tmp_path, monkeypatch):
    class Refs:
        version_scope = None
        testmodule = None
        symbol_needs = None
        intersphinx_mapping = doxylink = needs_external_needs = reference_groups = {}
        doxygen_docs = {}
        pdf_peers = {
            "https://x.example/html/test-report": "Test-Report_1.2.pdf",
            "https://x.example/html/requirement-specification": "Requirement-Specification_1.2.pdf",
        }

    registry = tmp_path / "documents.yaml"
    registry.write_text("documents: {}\n")
    monkeypatch.setenv("ZDOCS_REGISTRY", str(registry))
    monkeypatch.setattr(zdocs_conf.docrefs, "load", lambda **kwargs: Refs())
    monkeypatch.setenv("VERSION", "1.2")
    doc_dir = tmp_path / "handbook"
    doc_dir.mkdir()
    namespace = {}
    zdocs_conf.configure(namespace, doc_dir)
    preamble = namespace["latex_elements"]["preamble"]
    assert (
        "set={\\zdsetfile{Requirement-Specification\\_1.2.pdf}"
        "\\zdsetfile{Test-Report\\_1.2.pdf}}"
    ) in preamble


def test_a_consumer_style_file_is_loaded_last(tmp_path, monkeypatch):
    style = tmp_path / "acme-pdf.sty"
    style.write_text("\\zdsetup{footer={ACME}}\n")
    namespace = _configure(tmp_path, monkeypatch, latex_style=style)
    assert namespace["latex_additional_files"] == [str(STY), str(style)]
    preamble = namespace["latex_elements"]["preamble"]
    assert preamble.index("\\usepackage{zdocs}") < preamble.index("\\usepackage{acme-pdf}")


@pytest.mark.parametrize("name", ["acme.tex", "zdocs.sty"])
def test_a_consumer_style_file_must_be_a_sty_of_its_own_name(tmp_path, monkeypatch, name):
    with pytest.raises(ValueError, match="latex_style"):
        _configure(tmp_path, monkeypatch, latex_style=tmp_path / name)


def test_zdocs_sty_defines_what_the_engine_writes():
    sty = STY.read_text()
    # zdocs_conf writes \zdsetup, doc_control writes \signatureline.
    for macro in (
        "\\newcommand{\\zdsetup}",
        "\\newcommand{\\signatureline}",
        "\\newcommand{\\zdsetfile}",
        "\\renewcommand{\\sphinxmaketitle}",
    ):
        assert macro in sty
    for key in ("title", "version", "footer", "docid", "set"):
        assert f"\\define@key{{zd}}{{{key}}}" in sty
