# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``doc_check_accepted:`` lets named findings through without hiding them."""

import subprocess
import sys
from pathlib import Path

import pytest

DOCCHECK = Path(__file__).resolve().parents[3] / "scripts" / "doccheck.py"

DEAD = "html/api/index.html: dead link -> missing.html"


@pytest.fixture
def deploy(tmp_path):
    page = tmp_path / "deploy" / "html" / "api" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text('<a href="missing.html">x</a> <a href="index.html">self</a>')
    return tmp_path / "deploy"


def run(tmp_path, deploy, accepted_yaml=""):
    registry = tmp_path / "documents.yaml"
    registry.write_text('base_url: "http://localhost:8000/"\n' + accepted_yaml)
    return subprocess.run(
        [sys.executable, DOCCHECK, "--registry", registry, "--deploy", deploy],
        capture_output=True,
        text=True,
    )


def test_dead_link_fails_without_acceptance(tmp_path, deploy):
    result = run(tmp_path, deploy)
    assert result.returncode == 1
    assert DEAD in result.stderr


def test_accepted_finding_passes_but_is_still_reported(tmp_path, deploy):
    result = run(
        tmp_path,
        deploy,
        f'doc_check_accepted:\n  - finding: "{DEAD}"\n    reason: "issue 042"\n',
    )
    assert result.returncode == 0
    assert "accepted (1)" in result.stderr
    assert DEAD in result.stderr
    assert "issue 042" in result.stderr


def test_acceptance_is_exact_not_a_pattern(tmp_path, deploy):
    result = run(
        tmp_path,
        deploy,
        'doc_check_accepted:\n  - finding: "html/api/index.html: dead link"\n'
        '    reason: "prefix only"\n',
    )
    assert result.returncode == 1
    assert "no longer found (1)" in result.stderr


def test_stale_acceptance_is_reported_but_does_not_fail(tmp_path, deploy):
    (deploy / "html" / "api" / "missing.html").write_text("now it exists")
    result = run(
        tmp_path,
        deploy,
        f'doc_check_accepted:\n  - finding: "{DEAD}"\n    reason: "issue 042"\n',
    )
    assert result.returncode == 0
    assert "no longer found (1)" in result.stderr


def test_acceptance_without_reason_is_a_bad_invocation(tmp_path, deploy):
    result = run(tmp_path, deploy, f'doc_check_accepted:\n  - finding: "{DEAD}"\n')
    assert result.returncode == 2
    assert "needs a non-empty 'finding' and 'reason'" in result.stderr
