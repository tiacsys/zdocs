# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``doccheck.py --strict`` (ZDOCS_STRICT): every stage-2 Sphinx warning fails the
gate, and every document that has one is named.

The warning files are written by real ``sphinx-build -w`` runs, at the place
``add_sphinx_target`` writes them (``<build>/<doc>/build/<builder>.log``), so the
test reads what a build writes, not a hand-made file.
"""

import subprocess
import sys
from pathlib import Path

import pytest

DOCCHECK = Path(__file__).resolve().parents[3] / "scripts" / "doccheck.py"

REGISTRY = """\
base_url: "http://localhost:8000/"
groups:
  - id: all
    title: All
documents:
  clean:
    group: all
    builders: [html]
  dangling:
    group: all
    builders: [html]
  broken-ref:
    group: all
    builders: [html]
  sop:
    kind: external
    group: all
    remote-url: sop.html
"""

SOURCES = {
    "clean": ".. req:: A requirement\n   :id: REQ_001\n",
    "dangling": ".. req:: A refinement\n   :id: REQ_002\n   :links: REQ_GONE\n",
    "broken-ref": "See :ref:`no-such-label`.\n",
}


def _sphinx_build(build, doc_id, body):
    src = build / doc_id / "src"
    src.mkdir(parents=True)
    (src / "conf.py").write_text("extensions = ['sphinx_needs']\n")
    (src / "index.rst").write_text(f"{doc_id}\n{'=' * len(doc_id)}\n\n{body}")
    (build / doc_id / "build").mkdir()
    subprocess.run(
        [
            sys.executable, "-m", "sphinx", "-q", "-b", "html",
            "-d", str(build / doc_id / "doctrees"),
            "-w", str(build / doc_id / "build" / "html.log"),
            str(src), str(build / "deploy" / "html" / doc_id),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def build(tmp_path_factory):
    build = tmp_path_factory.mktemp("build")
    for doc_id, body in SOURCES.items():
        _sphinx_build(build, doc_id, body)
    (build / "documents.yaml").write_text(REGISTRY)
    return build


def doccheck(build, *extra):
    return subprocess.run(
        [sys.executable, DOCCHECK, "--registry", build / "documents.yaml",
         "--deploy", build / "deploy", *extra],
        capture_output=True,
        text=True,
    )


def test_without_strict_the_warnings_pass(build):
    result = doccheck(build)
    assert result.returncode == 0, result.stderr
    assert "strict" not in result.stdout


def test_strict_fails_and_names_every_document_with_a_warning(build):
    result = doccheck(build, "--strict")
    assert result.returncode == 1
    findings = [line.strip() for line in result.stderr.splitlines() if "WARNING" in line]
    assert any(f.startswith("dangling (html): ") and "REQ_GONE" in f for f in findings)
    assert any(f.startswith("broken-ref (html): ") and "no-such-label" in f for f in findings)
    assert not any(f.startswith("clean ") for f in findings)


def test_the_finding_has_no_host_path(build):
    result = doccheck(build, "--strict")
    assert str(build) not in result.stderr
    assert "dangling (html): dangling/src/index.rst:" in result.stderr


def test_a_strict_finding_can_be_accepted(build, tmp_path):
    result = doccheck(build, "--strict")
    findings = [line.strip() for line in result.stderr.splitlines() if " (html): " in line]
    registry = tmp_path / "documents.yaml"
    registry.write_text(
        REGISTRY
        + "doc_check_accepted:\n"
        + "".join(f"  - finding: {f!r}\n    reason: known\n" for f in findings)
    )
    accepted = subprocess.run(
        [sys.executable, DOCCHECK, "--registry", registry, "--deploy", build / "deploy",
         "--strict"],
        capture_output=True,
        text=True,
    )
    assert accepted.returncode == 0, accepted.stderr
    assert "3 Sphinx warning file(s) clean" in accepted.stdout


def test_strict_without_any_warning_file_fails(tmp_path):
    (tmp_path / "deploy").mkdir()
    (tmp_path / "documents.yaml").write_text(REGISTRY)
    result = doccheck(tmp_path, "--strict")
    assert result.returncode == 1
    assert "no Sphinx warning file" in result.stderr
