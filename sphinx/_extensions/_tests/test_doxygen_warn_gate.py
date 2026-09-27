# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""The stage-2 Doxygen warning gate fails only on the configured patterns."""

import shutil
import subprocess
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[3] / "cmake" / "check_doxygen_warnings.cmake"
DEFAULT = "Reference to unknown requirement"

TYPO = "src/main.c:467: warning: Reference to unknown requirement 'ZEP-SRS-24-' found"
UNDOC = "src/main.c:12: warning: Member foo (function) of file main.c is not documented."

pytestmark = pytest.mark.skipif(shutil.which("cmake") is None, reason="needs cmake")


def run(tmp_path, lines, patterns=DEFAULT, write_log=True):
    log = tmp_path / "doc.warnings.log"
    if write_log:
        log.write_text("".join(line + "\n" for line in lines))
    return subprocess.run(
        ["cmake", "-DDOC_ID=doc", f"-DLOGFILE={log}", f"-DPATTERNS={patterns}", "-P", GATE],
        capture_output=True,
        text=True,
    )


def test_unknown_requirement_fails_and_names_the_line(tmp_path):
    result = run(tmp_path, [UNDOC, TYPO])
    assert result.returncode != 0
    assert "1 Doxygen warning(s) match" in result.stderr
    assert "'ZEP-SRS-24-'" in result.stderr


def test_other_warnings_pass_and_are_still_printed(tmp_path):
    result = run(tmp_path, [UNDOC])
    assert result.returncode == 0
    assert UNDOC in result.stderr


def test_empty_patterns_gate_nothing(tmp_path):
    result = run(tmp_path, [TYPO], patterns="")
    assert result.returncode == 0
    assert TYPO in result.stderr


def test_any_of_several_patterns_fails(tmp_path):
    result = run(tmp_path, [UNDOC], patterns=f"{DEFAULT};is not documented")
    assert result.returncode != 0


def test_missing_log_passes(tmp_path):
    assert run(tmp_path, [], write_log=False).returncode == 0
