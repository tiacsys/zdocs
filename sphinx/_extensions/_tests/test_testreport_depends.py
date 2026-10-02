# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""testreport: did a result's build meet its case's depends_on, and why was it skipped.

``depends_met`` is evaluated against the build's own ``.config``, which twister
keeps beside each build; ``skip_class`` sorts each skipped result into
config / platform / build-only / unexplained. Fixture: fixtures/twister-depends,
one module on two platforms, the feature symbol set on qemu_x86 only.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import rst_builders as rb
import test_module as tm
import twister_reader as tw
from conftest import FIXTURES

_ROOTS = Path(__file__).parent / "roots"
DATA = FIXTURES / "twister-depends"
QEMU_CFG = DATA / "qemu_x86/zephyr_gnu/tests/kernel/demo/kernel.demo/zephyr/.config"
MPS2_CFG = DATA / "mps2_an385/zephyr_gnu/tests/kernel/demo/kernel.demo/zephyr/.config"


# ---------------------------------------------------------------------------
# .config
# ---------------------------------------------------------------------------


def test_read_kconfig_takes_every_value_and_skips_not_set(tmp_path):
    cfg = tmp_path / ".config"
    cfg.write_text(
        "#\n# CONFIG_OFF is not set\nCONFIG_Y=y\nCONFIG_M=m\nCONFIG_N=0\n"
        'CONFIG_S=""\nCONFIG_HEX=0x10\n  CONFIG_INDENTED=y\n'
    )
    assert tw.read_kconfig(cfg) == {"CONFIG_Y", "CONFIG_M", "CONFIG_N", "CONFIG_S", "CONFIG_HEX"}


def test_find_build_config_in_the_path_layout():
    path = tw.find_build_config(
        DATA, "mps2/an385", "zephyr/gnu", "tests/kernel/demo", "kernel.demo"
    )
    assert path == MPS2_CFG


def test_find_build_config_keeps_only_after_last_pardir(tmp_path):
    cfg = tmp_path / "p/zephyr_gnu/acme/tests/x/acme.x/zephyr/.config"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("CONFIG_A=y\n")
    assert tw.find_build_config(tmp_path, "p", "zephyr/gnu", "../acme/tests/x", "acme.x") == cfg


def test_find_build_config_detailed_test_id_layout(tmp_path):
    cfg = tmp_path / "p/zephyr_gnu/acme.x/zephyr/.config"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("CONFIG_A=y\n")
    assert tw.find_build_config(tmp_path, "p", "zephyr/gnu", "tests/x", "acme.x") == cfg


def test_find_build_config_takes_no_other_scenarios_config():
    # find_handler_log falls back to a single other run directory; this must not.
    assert tw.find_build_config(DATA, "qemu_x86", "zephyr/gnu", "tests/kernel/demo",
                                "kernel.demo.missing") is None


# ---------------------------------------------------------------------------
# The condition grammar
# ---------------------------------------------------------------------------

SYMBOLS = {"CONFIG_A", "CONFIG_B"}


@pytest.mark.parametrize(
    "condition, expected",
    [
        ("CONFIG_A", True),
        ("CONFIG_C", False),
        ("!CONFIG_A", False),
        ("defined(CONFIG_A)", True),
        ("defined CONFIG_C", False),
        ("!defined(CONFIG_C)", True),
        ("defined(CONFIG_A) && !defined(CONFIG_B)", False),
        ("CONFIG_C || CONFIG_A && !CONFIG_C", True),  # && binds tighter
        ("(CONFIG_C || CONFIG_A) && !CONFIG_B", False),
        ("!(CONFIG_C || CONFIG_B)", False),
        ("  CONFIG_A&&CONFIG_B ", True),
    ],
)
def test_evaluate_condition(condition, expected):
    assert tw.evaluate_condition(condition, SYMBOLS) is expected


@pytest.mark.parametrize(
    "condition",
    [
        "IS_ENABLED(CONFIG_A)",
        "Z_MUTEX_PI_ENABLED",
        "CONFIG_MP_MAX_NUM_CPUS > 1",
        "CONFIG_A == 0",
        "defined(TICK_IRQ)",
        "(CONFIG_A",
        "CONFIG_A CONFIG_B",
        "CONFIG_A &&",
        "",
    ],
)
def test_unparseable_conditions_raise(condition):
    with pytest.raises(tw.UnparseableCondition):
        tw.evaluate_condition(condition, SYMBOLS)


def test_depends_met_values():
    assert tw.depends_met(["CONFIG_A", "!CONFIG_C"], SYMBOLS) == ("yes", [])
    assert tw.depends_met(["CONFIG_A", "CONFIG_C"], SYMBOLS) == ("no", [])
    assert tw.depends_met([], SYMBOLS) == ("n/a", [])
    assert tw.depends_met(["CONFIG_A"], None) == ("n/a", [])  # no .config


def test_depends_met_never_guesses_past_an_unparseable_condition():
    # CONFIG_C is false, but the whole cannot be judged from .config alone.
    assert tw.depends_met(["Z_LOCAL", "CONFIG_C"], SYMBOLS) == ("n/a", ["Z_LOCAL"])


def test_spec_lookup_reads_depends_on_as_conditions(tmp_path):
    lookup = tw.load_spec_lookup(DATA / "needs.json")
    assert lookup.find("demo_suite", "local_macro")["depends_on"] == [
        "Z_DEMO_LOCAL_MACRO", "CONFIG_DEMO_FEATURE",
    ]
    assert lookup.find("demo_suite", "plain")["depends_on"] == []
    needs = tmp_path / "needs.json"
    needs.write_text(json.dumps({"versions": {"1": {"needs": {"T1": {
        "type": "test_case", "test_function": "test_x", "depends_on": ["CONFIG_A", "CONFIG_B"],
    }}}}}))
    assert tw.load_spec_lookup(needs).find("", "x")["depends_on"] == ["CONFIG_A", "CONFIG_B"]


# ---------------------------------------------------------------------------
# skip_class
# ---------------------------------------------------------------------------


def _skipped(reason, **kw):
    return {"status": "skipped", "reason": reason, **kw}


@pytest.mark.parametrize(
    "result, met, expected",
    [
        (_skipped("ztest skip"), "no", "config"),
        (_skipped("ztest skip"), "yes", "unexplained"),
        (_skipped("ztest skip"), "n/a", "unexplained"),
        (_skipped("RAM overflow"), "no", "platform"),
        (_skipped("FLASH overflow"), "n/a", "platform"),
        (_skipped("Not in testsuite platform allow list"), "n/a", "platform"),
        (_skipped("built only"), "no", "build-only"),
        (_skipped("Test was built only"), "n/a", "build-only"),
        (_skipped("not supported"), "no", "unexplained"),
        ({"status": "passed", "reason": ""}, "no", None),
        ({"status": "failed", "reason": "boom"}, "no", None),
    ],
)
def test_skip_class(result, met, expected):
    assert tw.skip_class(result, met) == expected


def test_skip_class_of_a_parameterized_test_reads_its_values():
    values = [{"status": "skipped", "reason": "ztest skip"}] * 3
    result = _skipped("3 values: 3 skipped", values=values)
    assert tw.skip_class(result, "no") == "config"


# ---------------------------------------------------------------------------
# The directive's assessment, on the fixture run
# ---------------------------------------------------------------------------


def _assessed(note=None):
    meta = tw.load_twister_meta(DATA / "twister.json")
    results = tw.parse_twister_results(
        DATA / "twister_report.xml", path_filter="tests/kernel/demo",
        suite_paths=tw.testsuite_paths(meta),
    )
    lookup = tw.load_spec_lookup(DATA / "needs.json")
    bad = tm._assess_results(results, lookup, meta, DATA, note_input=note)
    return {(r["platform"], r["scenario"], r["function"]): r for r in results}, bad


def test_assessment_of_every_result():
    results, _ = _assessed()
    got = {k: (r["depends_met"], r.get("skip_class")) for k, r in results.items()}
    assert got == {
        ("qemu_x86", "kernel.demo", "needs_feature"): ("yes", None),
        ("qemu_x86", "kernel.demo", "ran_anyway"): ("no", None),
        ("qemu_x86", "kernel.demo", "local_macro"): ("n/a", "unexplained"),
        ("qemu_x86", "kernel.demo", "plain"): ("n/a", None),
        ("qemu_x86", "kernel.demo.soak", "plain"): ("n/a", "build-only"),
        ("mps2/an385", "kernel.demo", "needs_feature"): ("no", "config"),
        ("mps2/an385", "kernel.demo", "ran_anyway"): ("yes", None),
        ("mps2/an385", "kernel.demo", "local_macro"): ("n/a", "unexplained"),
        ("mps2/an385", "kernel.demo.big", "plain"): ("n/a", "platform"),
    }


def test_assessment_reports_each_unparseable_condition_once_and_notes_configs():
    noted = []
    _, bad = _assessed(noted.append)
    assert bad == {("TSPEC-DEMO-002", "Z_DEMO_LOCAL_MACRO")}
    # Only builds of conditioned cases are read, each .config once.
    assert sorted(noted) == sorted([QEMU_CFG, MPS2_CFG])


def test_assessment_without_twister_json_is_not_applicable():
    results = tw.parse_twister_results(DATA / "twister_report.xml")
    tm._assess_results(results, tw.load_spec_lookup(DATA / "needs.json"), None, DATA)
    assert {r["depends_met"] for r in results} == {"n/a"}


# ---------------------------------------------------------------------------
# RST: the fields, by role
# ---------------------------------------------------------------------------

_RESULT = {
    "platform": "p", "scenario": "s", "function": "f", "twister_id": "s.f", "time": "0",
    "status": "skipped", "reason": "ztest skip", "depends_met": "no", "skip_class": "config",
}


def test_result_rst_sets_the_declared_fields_under_the_default_names():
    rst = rb.build_result_rst(_RESULT, "T-1", "m", fields={"depends_met", "skip_class"})
    assert "   :depends_met: no" in rst
    assert "   :skip_class: config" in rst


def test_result_rst_sets_no_undeclared_field():
    rst = rb.build_result_rst(_RESULT, "T-1", "m", fields={"skip_class"})
    assert "depends_met" not in rst
    assert rb.build_result_rst(_RESULT, "T-1", "m").count("config") == 0


def test_result_rst_uses_the_consumers_names():
    names = {"depends_met": "cond_held", "skip_class": "omission_kind"}
    rst = rb.build_result_rst(
        _RESULT, "T-1", "m", need_names=names, fields={"depends_met", "skip_class"}
    )
    assert "   :cond_held: no" in rst and "   :omission_kind: config" in rst
    assert "depends_met" not in rst and "skip_class" not in rst


def test_need_names_from_config_merges_the_field_mapping():
    config = SimpleNamespace(testreport_need_fields={"skip_class": "omission_kind"})
    names = tm._need_names_from_config(SimpleNamespace(config=config))
    assert rb._need_name(names, "skip_class") == "omission_kind"
    assert rb._need_name(names, "depends_met") == "depends_met"


# ---------------------------------------------------------------------------
# Directive: the fields reach needs.json, under the consumer's names
# ---------------------------------------------------------------------------


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport-depends"))
def test_directive_sets_the_fields_and_warns_about_the_unparseable(app, warning):
    app.build()
    data = json.loads((Path(app.outdir) / "needs.json").read_text())
    needs = next(iter(data["versions"].values()))["needs"]
    results = {n["id"]: n for n in needs.values() if n["type"] == "test_result"}
    config = results["TR-mps2-an385-kernel-demo-TSPEC-DEMO-001"]
    assert (config["cond_held"], config["omission_kind"]) == ("no", "config")
    ran = results["TR-qemu-x86-kernel-demo-TSPEC-DEMO-004"]
    assert ran["status"] == "passed" and ran["cond_held"] == "no"
    assert ran.get("omission_kind") in (None, "")
    assert results["TR-mps2-an385-kernel-demo-big-TSPEC-DEMO-003"]["omission_kind"] == "platform"
    log = warning.getvalue()
    assert "TSPEC-DEMO-002: depends_on condition 'Z_DEMO_LOCAL_MACRO'" in log
    assert log.count("depends_on condition") == 1
    assert "Unknown option" not in log
