# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the plain modules in ``_scripts/``.

A test that imports a Sphinx extension from ``_extensions/`` belongs in
``_extensions/_tests``. The fixtures of both suites are in ``sphinx/_fixtures``.
"""

import sys
from pathlib import Path

import pytest

# Make _scripts/ importable without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOTS = Path(__file__).parent / "roots"


@pytest.fixture(autouse=True)
def _fresh_sphinx_build_dirs():
    """Wipe every test root's ``_build/`` before each test.

    Load-bearing, not hygiene: see the same fixture in
    ``_extensions/_tests/conftest.py`` for why.
    """
    import shutil

    for build_dir in ROOTS.glob("*/_build"):
        shutil.rmtree(build_dir, ignore_errors=True)
