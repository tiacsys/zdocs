# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""testreport ``:path:`` — select a module's results by its test directory.

Upstream scenario names do not follow module directories. tests/kernel/timer/
timer_api runs as ``kernel.timer``, which prefix-matches ``kernel.timer.error_case``
from tests/kernel/timer/timer_error_case, so ``:module: kernel.timer`` put the
error-case results on the timer_api page too; the second page then failed with
"A need with ID ... already exists". The fixture reproduces exactly that pair.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
import test_module as tm
import twister_reader as tw
from conftest import FIXTURES
from docutils import nodes

_ROOTS = Path(__file__).parent / "roots"
DATA = FIXTURES / "twister-path"
XML = DATA / "twister_report.xml"

API = "tests/kernel/timer/timer_api"
ERR = "tests/kernel/timer/timer_error_case"


def _paths():
    return tw.testsuite_paths(tw.load_twister_meta(DATA / "twister.json"))


def _scenarios(results):
    return sorted(r["scenario"] for r in results)


# ---------------------------------------------------------------------------
# twister_reader
# ---------------------------------------------------------------------------


def test_scenario_prefix_takes_the_colliding_module_too():
    # The defect, pinned: the prefix of timer_api's scenario selects both modules.
    results = tw.parse_twister_results(XML, module_filter="kernel.timer")
    assert _scenarios(results) == ["kernel.timer", "kernel.timer.error_case"]


def test_path_selects_only_its_own_module():
    paths = _paths()
    api = tw.parse_twister_results(XML, path_filter=API, suite_paths=paths)
    err = tw.parse_twister_results(XML, path_filter=ERR, suite_paths=paths)
    assert _scenarios(api) == ["kernel.timer"]
    assert _scenarios(err) == ["kernel.timer.error_case"]


@pytest.mark.parametrize("spelling", [ERR + "/", "./" + ERR, ERR.replace("/", "\\")])
def test_path_is_normalised(spelling):
    results = tw.parse_twister_results(XML, path_filter=spelling, suite_paths=_paths())
    assert _scenarios(results) == ["kernel.timer.error_case"]


def test_path_is_matched_exactly_not_as_a_prefix():
    results = tw.parse_twister_results(XML, path_filter="tests/kernel/timer", suite_paths=_paths())
    assert results == []


def test_module_and_path_together_must_both_match():
    paths = _paths()
    both = tw.parse_twister_results(
        XML, module_filter="kernel.timer", path_filter=API, suite_paths=paths
    )
    assert _scenarios(both) == ["kernel.timer"]
    none = tw.parse_twister_results(
        XML, module_filter="kernel.timer.error_case", path_filter=API, suite_paths=paths
    )
    assert none == []


def test_a_run_missing_from_twister_json_is_not_selected_by_path():
    results = tw.parse_twister_results(XML, path_filter=API, suite_paths={})
    assert results == []


# ---------------------------------------------------------------------------
# Execution logs follow the same selection
# ---------------------------------------------------------------------------


def test_exec_logs_follow_the_path():
    api = "\n".join(tm._build_exec_logs_rst(str(DATA), None, API))
    assert "kernel.timer — mps2/an385" in api
    assert "kernel.timer.error_case" not in api
    # Control: the scenario prefix alone lists the other module's log as well.
    prefix = "\n".join(tm._build_exec_logs_rst(str(DATA), "kernel.timer"))
    assert "kernel.timer.error_case" in prefix


# ---------------------------------------------------------------------------
# Directive: soft-fail without twister.json
# ---------------------------------------------------------------------------


def test_path_without_twister_json_soft_fails(tmp_path, monkeypatch):
    (tmp_path / "twister_report.xml").write_text(XML.read_text())
    warnings = []
    monkeypatch.setattr(tm.logger, "warning", lambda msg, *a, **k: warnings.append(msg))
    noted = []
    env = SimpleNamespace(
        app=SimpleNamespace(config=SimpleNamespace(
            testspec_needs_json=str(DATA / "needs.json"),
            twister_output_dir=str(tmp_path),
        )),
        docname="index",
        note_dependency=noted.append,
    )
    directive = tm.TestReportDirective.__new__(tm.TestReportDirective)
    directive.arguments = ["twister_report.xml"]
    directive.options = {"path": API}
    directive.state = SimpleNamespace(document=SimpleNamespace(settings=SimpleNamespace(env=env)))

    result = directive.run()

    assert len(result) == 1 and isinstance(result[0], nodes.paragraph)
    text = result[0].astext()
    assert "twister.json not found" in text and ":path:" in text
    assert str(tmp_path) not in text  # published node: no host path
    assert any("twister.json" in w for w in warnings)
    # Tracked, so the report is re-read once twister.json appears.
    assert str(tmp_path / "twister.json") in noted


# ---------------------------------------------------------------------------
# Directive: two pages, each with only its own results
# ---------------------------------------------------------------------------


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport-path"))
def test_each_page_gets_only_its_own_results(app, warning):
    app.build()
    out = Path(app.outdir)
    api = (out / "timer_api.html").read_text()
    err = (out / "timer_error_case.html").read_text()
    assert "TR-mps2-an385-kernel-timer-TSPEC-TA-001" in api
    assert "TSPEC-TE-001" not in api
    assert "TR-mps2-an385-kernel-timer-error-case-TSPEC-TE-001" in err
    assert "TSPEC-TA-001" not in err
    assert "already exists" not in warning.getvalue()
