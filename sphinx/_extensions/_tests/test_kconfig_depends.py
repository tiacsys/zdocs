# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``@kconfig_depends{<condition>}`` -> the ``depends_on`` need field.

The alias is ``\\xrefitem kconfig_depends "Depends on" "Kconfig dependencies" \\1``.
fixtures/doxygen-kconfig is real Doxygen 1.16.1 output of kd.c: one condition;
two adjacent commands (one xrefsect, a <para> each); operators and parentheses;
a command inside a trailing list; two commands apart (two xrefsects); and an
escaped comma, which arrives as a plain one.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import doxygen_parser as dp
import needs_fields
import pytest
import rst_builders as rb
import test_module as tm
from conftest import FIXTURES

_ROOTS = Path(__file__).parent / "roots"
XML = FIXTURES / "doxygen-kconfig"
GROUP = "group__kd__suite"


def _member(name):
    root = ET.parse(XML / f"{GROUP}.xml").getroot()
    return next(md for md in root.iter("memberdef") if md.findtext("name") == name)


def _info(name):
    return dp.parse_memberdef(_member(name), GROUP, "testspec", "api")


# ---------------------------------------------------------------------------
# doxygen_parser
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "conditions"),
    [
        ("test_one", ["CONFIG_ASSERT"]),
        (
            "test_two",
            [
                "defined(CONFIG_HW_STACK_PROTECTION) && !defined(CONFIG_ARCH_POSIX)",
                "CONFIG_USERSPACE",
            ],
        ),
        ("test_three", ["(CONFIG_A && !CONFIG_B) || CONFIG_C"]),
        ("test_four", ["CONFIG_X"]),
        ("test_five", ["CONFIG_FIRST", "IS_ENABLED(CONFIG_A, CONFIG_B)"]),
        ("test_six", []),
    ],
)
def test_conditions_are_read_verbatim(name, conditions):
    label, found = dp.kconfig_depends(_member(name).find("detaileddescription"))
    assert found == conditions
    assert label == ("Depends on" if conditions else "")
    assert _info(name)["depends_on"] == conditions


def test_conditions_are_not_read_as_requirements_or_ids():
    one = _info("test_one")
    assert one["req_ids"] == ["REQ-1"]
    assert one["test_id"] == "TC-KD-001"
    assert _info("test_two")["req_ids"] == []
    assert _info("test_five")["test_id"] == "TC-KD-005"


def test_conditions_stay_out_of_the_prose():
    assert not any("CONFIG_" in line for line in _info("test_four")["detail_lines"])


def test_a_symbol_carries_its_conditions():
    root = ET.parse(FIXTURES / "doxygen-symbols" / "group__queue__apis.xml").getroot()
    md = next(m for m in root.iter("memberdef") if m.findtext("name") == "k_queue_append")
    info = dp.parse_symbol(md, "api")
    assert info["depends_on"] == [
        "CONFIG_ASSERT",
        "(CONFIG_USERSPACE && !CONFIG_NO_SYSCALLS) || CONFIG_TEST",
    ]
    assert info["depends_label"] == "Depends on"


# ---------------------------------------------------------------------------
# rst_builders
# ---------------------------------------------------------------------------


def test_test_case_need_with_the_field():
    rst = rb.build_need_rst(_info("test_two"), "kd_suite", depends_field=True)
    assert (
        "   :depends_on: defined(CONFIG_HW_STACK_PROTECTION) && "
        "!defined(CONFIG_ARCH_POSIX); CONFIG_USERSPACE"
    ) in rst
    assert "   **Depends on:** ``defined(CONFIG_HW_STACK_PROTECTION)" in rst


def test_test_case_need_without_the_field_still_says_so():
    rst = rb.build_need_rst(_info("test_one"), "kd_suite")
    assert ":depends_on:" not in rst
    assert "   **Depends on:** ``CONFIG_ASSERT``" in rst


def test_no_conditions_no_line():
    rst = rb.build_need_rst(_info("test_six"), "kd_suite", depends_field=True)
    assert "depends_on" not in rst and "Depends on" not in rst


def test_a_hand_built_info_without_the_keys_still_builds():
    info = {k: v for k, v in _info("test_one").items() if not k.startswith("depends")}
    assert "Depends on" not in rb.build_need_rst(info, "kd_suite", depends_field=True)


def test_suite_rst_asks_per_need():
    asked = []

    def decide(conditions, subject):
        asked.append(subject)
        return bool(conditions)

    lines = tm._build_suite_rst(GROUP, XML, "testspec", "api", "tests/kd", depends_field=decide)
    assert "   :depends_on: CONFIG_ASSERT" in lines
    assert asked[0] == "testmodule: kd_suite/test_one"
    assert sum(line.startswith("   :depends_on:") for line in lines) == 5


# ---------------------------------------------------------------------------
# needs_fields: set the field only where the consumer declared it
# ---------------------------------------------------------------------------


def _env(kind):
    field = SimpleNamespace(type=kind)
    schema = SimpleNamespace(get_extra_field=lambda name: field if kind else None)
    return SimpleNamespace(_needs_schema=schema)


def test_undeclared_field_is_not_set():
    assert needs_fields.depends_field(_env(None), ["CONFIG_A"], "x") is False
    # No sphinx-needs schema at all (a stand-in env): not set either.
    assert needs_fields.depends_field(SimpleNamespace(), ["CONFIG_A"], "x") is False


def test_string_field_is_set():
    assert needs_fields.depends_field(_env("string"), ["A || B", "F(A, B)"], "x") is True


def test_array_field_refuses_conditions_it_would_split(monkeypatch):
    warnings = []
    monkeypatch.setattr(needs_fields.logger, "warning", lambda msg, *a, **k: warnings.append(msg))
    assert needs_fields.depends_field(_env("array"), ["CONFIG_A", "CONFIG_B"], "x") is True
    assert needs_fields.depends_field(_env("array"), ["A || B"], "x: fn") is False
    assert len(warnings) == 1 and "x: fn" in warnings[0] and "string" in warnings[0]


# ---------------------------------------------------------------------------
# Directive: the field in needs.json when declared; no warning when not
# ---------------------------------------------------------------------------

_STRING_FIELD = {"depends_on": {"schema": {"type": "string"}, "nullable": True}}


@pytest.mark.sphinx(
    "html", srcdir=str(_ROOTS / "test-symbolneeds"), confoverrides={"needs_fields": _STRING_FIELD}
)
def test_declared_field_reaches_needs_json(app, warning):
    app.build()
    needs = json.loads((Path(app.outdir) / "needs.json").read_text())
    needs = needs["versions"][needs["current_version"]]["needs"]
    assert needs["IMPL-k_queue_append"]["depends_on"] == (
        "CONFIG_ASSERT; (CONFIG_USERSPACE && !CONFIG_NO_SYSCALLS) || CONFIG_TEST"
    )
    assert needs["IMPL-k_queue_init"]["depends_on"] is None
    assert "Unknown option" not in warning.getvalue()


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-symbolneeds"))
def test_undeclared_field_renders_without_warning(app, warning):
    app.build()
    html = (Path(app.outdir) / "api.html").read_text()
    assert "Depends on:" in html and "CONFIG_ASSERT" in html
    assert "Unknown option" not in warning.getvalue()
