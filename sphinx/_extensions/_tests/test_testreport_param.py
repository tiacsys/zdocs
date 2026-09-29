# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Parameterized tests (ZTEST_P): one result per value, attached to the test's result.

Twister reports a ZTEST_P function as an aggregate ``<scenario>.<suite>.<fn>``
plus one result per value, ``<scenario>.<fn>[<instantiation>/<value>]``, with no
suite segment. The values used to be looked up in the spec as functions named
``sem_init_validity[cases/0]`` and skipped with a warning each, which lost the
one result that says which value failed. The fixture is a real run in which
value 8 fails: the aggregate is ``blocked`` in twister.json and "Testsuite
failed" in the XML, and only ``[cases/8]`` carries the assertion.
"""

from pathlib import Path

import pytest
import rst_builders as rb
import twister_reader as tw
from conftest import FIXTURES
from twister_reader import SpecLookup

_ROOTS = Path(__file__).parent / "roots"
DATA = FIXTURES / "twister-param"
XML = DATA / "twister_report.xml"
AGGREGATE = "kernel.semaphore.semaphore.sem_init_validity"


def _statuses():
    return tw.testcase_statuses(tw.load_twister_meta(DATA / "twister.json"))


def _spec():
    return tw.load_spec_lookup(DATA / "needs.json")


def _result(platform="p", scenario="sc", suite="s", function="fn", status="passed", **kw):
    r = {
        "platform": platform,
        "scenario": scenario,
        "suite": suite,
        "function": function,
        "twister_id": f"{scenario}.{suite}.{function}",
        "time": "0.01",
        "status": status,
        "reason": "",
    }
    r.update(kw)
    return r


def _value(value, status="passed", platform="p", scenario="sc", function="fn", reason=""):
    return _result(
        platform, scenario, "", function, status,
        twister_id=f"{scenario}.{function}[{value}]", instance=value, reason=reason,
    )


# ---------------------------------------------------------------------------
# parse_twister_results
# ---------------------------------------------------------------------------


def test_values_are_recognised():
    values = [r for r in tw.parse_twister_results(XML) if r.get("instance")]
    assert [v["instance"] for v in values] == [f"cases/{i}" for i in range(9)]
    assert {(v["suite"], v["function"]) for v in values} == {("", "sem_init_validity")}


def test_a_failed_value_carries_the_assertion_not_the_suite_message():
    results = tw.parse_twister_results(XML)
    failed = [r for r in results if r["status"] == "failed" and r.get("instance")]
    assert len(failed) == 1
    reason = failed[0]["reason"]
    assert "Assertion failed at CMAKE_SOURCE_DIR/src/main.c:363" in reason
    assert "-22 != 0" in reason
    assert "START -" not in reason and "FAIL -" not in reason


def test_a_value_containing_dots_keeps_them(tmp_path):
    tmp = tmp_path / "twister_report.xml"
    tmp.write_text(XML.read_text().replace("[cases/1]", "[conversions/ms.to.cyc]"))
    values = [r for r in tw.parse_twister_results(tmp) if r.get("instance")]
    assert "conversions/ms.to.cyc" in [v["instance"] for v in values]
    assert {v["function"] for v in values} == {"sem_init_validity"}


# ---------------------------------------------------------------------------
# fold_parameterized_results
# ---------------------------------------------------------------------------


def test_values_attach_to_their_aggregate():
    results, unmatched = tw.fold_parameterized_results(
        tw.parse_twister_results(XML), _spec(), _statuses()
    )
    assert unmatched == []
    assert [r["twister_id"] for r in results] == [
        "kernel.semaphore.semaphore.sem_count_get",
        AGGREGATE,
    ]
    agg = results[1]
    assert len(agg["values"]) == 9
    assert agg["status"] == "failed"
    assert agg["reason"] == "9 values: 8 passed, 1 failed"
    # twister.json says `blocked`, which disagrees with the values: kept visible.
    assert agg["twister_status"] == "blocked"


def test_without_twister_json_the_xml_status_is_the_reference():
    results, _ = tw.fold_parameterized_results(tw.parse_twister_results(XML))
    agg = next(r for r in results if r["twister_id"] == AGGREGATE)
    assert agg["status"] == "failed"
    assert agg["twister_status"] == ""  # the XML's `failed` agrees


def test_the_verdict_comes_from_the_values():
    agg = _result(status="failed")
    results, _ = tw.fold_parameterized_results([agg, _value("v/0"), _value("v/1")])
    assert results == [agg]
    assert agg["status"] == "passed" and agg["reason"] == ""
    assert agg["twister_status"] == "failed"


@pytest.mark.parametrize(
    "statuses, verdict",
    [
        (["skipped", "skipped"], "skipped"),
        (["passed", "skipped"], "passed"),
        (["passed", "error"], "error"),
        (["error", "failed"], "failed"),
    ],
)
def test_verdict_rules(statuses, verdict):
    agg = _result()
    values = [_value(f"v/{i}", s) for i, s in enumerate(statuses)]
    tw.fold_parameterized_results([agg, *values])
    assert agg["status"] == verdict


def test_a_run_without_aggregate_takes_the_suite_of_another_runs_aggregate():
    results, unmatched = tw.fold_parameterized_results([
        _result(platform="a", suite="suite_x"),
        _value("v/0", platform="a"),
        _value("v/0", platform="b", status="failed"),
    ])
    assert unmatched == []
    b = next(r for r in results if r["platform"] == "b")
    assert (b["suite"], b["function"], b["status"]) == ("suite_x", "fn", "failed")
    assert len(b["values"]) == 1


def test_a_run_without_any_aggregate_takes_a_unique_spec_case():
    spec = SpecLookup([{"id": "T-1", "suite": "suite_y", "test_function": "test_fn"}])
    results, unmatched = tw.fold_parameterized_results([_value("v/0")], spec)
    assert unmatched == []
    assert [(r["suite"], r["function"]) for r in results] == [("suite_y", "fn")]


def test_unattachable_values_are_reported_once_per_function():
    spec = SpecLookup([
        {"id": "T-1", "suite": "a", "test_function": "test_fn"},
        {"id": "T-2", "suite": "b", "test_function": "test_fn"},
    ])
    results, unmatched = tw.fold_parameterized_results(
        [_value("v/0"), _value("v/1"), _value("v/0", platform="q")], spec
    )
    assert results == []
    assert unmatched == ["fn"]


def test_results_without_values_are_unchanged():
    plain = [_result(), _result(function="other")]
    assert tw.fold_parameterized_results(plain) == (plain, [])


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_result_need_lists_only_the_values_that_did_not_pass():
    results, _ = tw.fold_parameterized_results(tw.parse_twister_results(XML), None, _statuses())
    agg = next(r for r in results if r["twister_id"] == AGGREGATE)
    rst = rb.build_result_rst(agg, "TSPEC-SEM-001", "tests/kernel/semaphore/semaphore")
    assert ":status: failed" in rst
    assert "9 values: 8 passed, 1 failed." in rst
    assert "Twister reported the test as ``blocked``." in rst
    assert "cases/8" in rst and "-22 != 0" in rst
    assert "cases/0" not in rst


def test_reason_markup_is_escaped():
    assert rb._rst_text("a *b* `c` |d| x_y") == r"a \*b\* \`c\` \|d\| x\_y"


# ---------------------------------------------------------------------------
# Directive
# ---------------------------------------------------------------------------


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport-param"))
def test_report_page_shows_the_failed_value(app, warning):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "TR-mps2-an385-kernel-semaphore-TSPEC-SEM-001" in html
    assert "9 values: 8 passed, 1 failed" in html
    assert "cases/8" in html and "Assertion failed" in html
    assert "blocked" in html
    assert "cases/3" not in html
    # Recognised values are not "missing from the spec".
    assert "not in spec needs.json" not in warning.getvalue()
    assert "parameterized test" not in warning.getvalue()
