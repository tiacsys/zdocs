# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

import pytest

# Make _extensions/ importable without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = Path(__file__).parent / "fixtures"

pytest_plugins = "sphinx.testing.fixtures"
# rootdir is intentionally left as the sphinx.testing default (None).
# Tests pass srcdir as an absolute path so Sphinx uses the source tree directly
# without copying, keeping __file__-relative paths in conf.py correct.

ROOTS = Path(__file__).parent / "roots"


@pytest.fixture(autouse=True)
def _fresh_sphinx_build_dirs():
    """Wipe every test root's ``_build/`` before each test.

    NOT hygiene — this is load-bearing, and without it the directive-level
    tests in this suite are worthless. Because ``srcdir`` is the real
    directory (see the note above, which is why it must stay that way), each
    root's ``_build/doctrees`` pickle SURVIVES BETWEEN SEPARATE PYTEST
    INVOCATIONS. Sphinx invalidates that cache on changed sources or config —
    but NOT on changed extension code, which is precisely what this suite
    exists to test. So a second run of ``app.build()`` reprocesses nothing and
    emits no warnings, and every directive test passes without ever
    exercising the code under test.

    Measured, with a control, rather than assumed (rule 11). Replacing
    ``.. test_case::`` with ``.. DELIBERATELY_BROKEN::`` in rst_builders.py:

        stale _build/  ->  10 passed, 0 failed   <- the defect is invisible
        wiped _build/  ->   8 passed, 2 failed   <- the defect is caught

    This is the same shape as D10 and the step-15 html/latex doctree bug
    recorded in zdocs-next-session.md §3: a cached doctree silently answering
    for work that was never redone. Do not remove this fixture, and do not
    "optimise" it by wiping only the roots a given test uses.
    """
    import shutil

    for build_dir in ROOTS.glob("*/_build"):
        shutil.rmtree(build_dir, ignore_errors=True)
