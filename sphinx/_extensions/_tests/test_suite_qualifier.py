# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``testmodule_suite_qualifier``: a suite group's Doxygen name vs the ztest suite.

Two test modules may declare the same ZTEST_SUITE (Zephyr's workq user_work and
work_queue both declare ``workqueue_api``). One Doxygen group for both would put
every test on both module pages, so each module gets its own group,
``<module>__<suite>``, and the qualifier ``"__"`` tells testmodule the need's
``suite`` is the part after it: the (suite, function) key a twister result is
correlated by must see the real suite name.

fixtures/doxygen-qualifier is hand-written in Doxygen's shape: modules m1 and
m2, each with a group ``m<N>__workqueue_api``; m1 has test_workq_user_mode
(TSPEC-WQ-001), m2 test_workq_start (TSPEC-WQ-002), and both a test_shared
without @testid, so it takes the fallback id.
"""

import json
from pathlib import Path

import pytest
import test_module as tm
from conftest import FIXTURES
from twister_reader import load_spec_lookup

_ROOTS = Path(__file__).parent / "roots"
XML = FIXTURES / "doxygen-qualifier"
M1 = "group__m1____workqueue__api"


def _field(lines, name):
    return [line.split(":", 2)[2].strip() for line in lines if line.startswith(f"   :{name}:")]


# ---------------------------------------------------------------------------
# suite_name_from_group
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "group, qualifier, suite",
    [
        ("kernel_workq_user_work_module__workqueue_api", "__", "workqueue_api"),
        ("a__b__workqueue_api", "__", "workqueue_api"),  # the LAST occurrence
        ("workqueue_api", "__", "workqueue_api"),        # no occurrence
        ("m1__", "__", "m1__"),                          # nothing after it
        ("m1__workqueue_api", "", "m1__workqueue_api"),  # unset
    ],
)
def test_suite_name_from_group(group, qualifier, suite):
    assert tm.suite_name_from_group(group, qualifier) == suite


# ---------------------------------------------------------------------------
# _build_suite_rst
# ---------------------------------------------------------------------------

def test_qualifier_gives_the_need_the_real_suite():
    lines = tm._build_suite_rst(M1, XML, "testspec", "api", "tests/m1", suite_qualifier="__")
    assert _field(lines, "suite") == ["workqueue_api", "workqueue_api"]


def test_fallback_id_keeps_the_group_name():
    # test_shared exists in both modules; the suite name alone would give both
    # `testspec-workqueue_api-test_shared`.
    lines = tm._build_suite_rst(M1, XML, "testspec", "api", "tests/m1", suite_qualifier="__")
    assert _field(lines, "id") == ["TSPEC-WQ-001", "testspec-m1__workqueue_api-test_shared"]


def test_unset_qualifier_keeps_the_group_name_as_suite():
    lines = tm._build_suite_rst(M1, XML, "testspec", "api", "tests/m1")
    assert _field(lines, "suite") == ["m1__workqueue_api", "m1__workqueue_api"]
    assert _field(lines, "id") == ["TSPEC-WQ-001", "testspec-m1__workqueue_api-test_shared"]


def test_group_without_the_qualifier_is_unchanged():
    lines = tm._build_suite_rst(
        "group__queue__api", FIXTURES / "doxygen", "t", "a", "tests/kernel/queue",
        suite_qualifier="__",
    )
    assert set(_field(lines, "suite")) == {"queue_api"}


# ---------------------------------------------------------------------------
# Directive: two modules, one ztest suite, results correlated per module
# ---------------------------------------------------------------------------

def _needs(app):
    data = json.loads((Path(app.outdir) / "needs.json").read_text())
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule-qualifier"))
def test_two_modules_same_suite(app, warning):
    app.build()
    needs = _needs(app)
    assert sorted(needs) == [
        "TSPEC-WQ-001", "TSPEC-WQ-002",
        "testspec-m1__workqueue_api-test_shared", "testspec-m2__workqueue_api-test_shared",
    ]
    assert {n["suite"] for n in needs.values()} == {"workqueue_api"}
    assert needs["TSPEC-WQ-001"]["test_module"] == "tests/m1"
    assert needs["TSPEC-WQ-002"]["test_module"] == "tests/m2"
    assert "already exists" not in warning.getvalue()

    # The report's (suite, function) key, as twister names them.
    lookup = load_spec_lookup(Path(app.outdir) / "needs.json")
    assert lookup.find("workqueue_api", "workq_user_mode")["id"] == "TSPEC-WQ-001"
    assert lookup.find("workqueue_api", "workq_start")["id"] == "TSPEC-WQ-002"


@pytest.mark.sphinx(
    "html", srcdir=str(_ROOTS / "test-testmodule-qualifier"),
    confoverrides={"testmodule_suite_qualifier": ""},
)
def test_directive_without_qualifier_is_todays_behaviour(app):
    app.build()
    assert {n["suite"] for n in _needs(app).values()} == {
        "m1__workqueue_api", "m2__workqueue_api",
    }
