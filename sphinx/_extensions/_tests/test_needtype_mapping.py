# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Unit-level tests for the configurable need-type / link-type role->name
mapping (zdocs step 26).

STATUS: RED BY DESIGN. `testmodule_need_types` / `testmodule_need_links`
(and the corresponding builder parameter, see below) do NOT exist yet. These
tests pin the mapping's expected behaviour ahead of the implementation
(phase 3) per zdocs-brief-step26-needtype-mapping.md §2-§4. They must fail
only because the feature is missing -- not for any other reason. Do not
edit rst_builders.py or test_module.py to make these pass; that is phase
3's job.

Parameter contract phase 3 must match
--------------------------------------
A single dict, threaded through as a new keyword argument named
`need_names`, on every function that emits a need-type or link-field
literal:

    rst_builders.build_need_rst(info, suite_name, module_path="",
                                 suite_title="", need_names=None)
    rst_builders.build_procedure_need_rst(memberdef, proc_compound_id,
                                 proc_group_name, testspec_html_dir,
                                 api_html_dir, need_names=None)
    rst_builders.build_result_rst(r, spec_id, test_module, req_ids=None,
                                 need_names=None)
    test_module._build_summary_table_rst(grouped, spec_lookup,
                                 need_names=None)

One dict (not two) because build_need_rst and build_result_rst each emit
BOTH a need-type literal and link-field literals from the same function
(brief §3 decision 1), so splitting the parameter in two would only add
bookkeeping for no benefit. Keys are the engine's fixed roles: "case",
"procedure", "result" (need types) and "verifies", "result_of", "covers"
(links) -- the same key space as testmodule_need_types/testmodule_need_links
combined. `need_names=None`, an empty dict, or a dict missing some keys
must all fall back to today's literal defaults for the missing roles
(brief §3 decision 5).
"""
import xml.etree.ElementTree as ET

import rst_builders as rb
import test_module as tm

# Override names chosen to share NO substring with the engine defaults
# ("test_case", "test_procedure", "test_result", "verifies", "result_of",
# "covers"), so an implementation that merely appends/prefixes the default
# cannot pass these tests by accident (brief §4).
TYPES_FULL = {"case": "tc_item", "procedure": "qual_step", "result": "outcome_rec"}
LINKS_FULL = {"verifies": "endorses", "result_of": "produced_by", "covers": "addresses"}
NAMES_FULL = {**TYPES_FULL, **LINKS_FULL}


def _base_info(**kwargs):
    defaults = {
        "name": "test_queue_put",
        "brief": "Test queue put operation.",
        "detail_lines": [],
        "test_id": "TSPEC-QUEUE-API-001",
        "req_ids": ["zep-srs-20-1"],
        "status": "active",
        "source_file": "test_queue.c (line 42)",
        "doxygen_url": "/testspec/html/group.html#abc",
        "see_rst": "",
        "body_sections": [],
    }
    defaults.update(kwargs)
    return defaults


def _base_result(**kwargs):
    defaults = {
        "platform": "qemu_cortex_m3/ti_lm3s6965",
        "scenario": "kernel.queue",
        "suite": "kernel.queue",
        "function": "queue_put",
        "twister_id": "kernel.queue.kernel.queue.test_queue_put",
        "time": "0.123",
        "status": "passed",
        "reason": "",
    }
    defaults.update(kwargs)
    return defaults


def _spec_lookup_single():
    return {
        "test_queue_put": {
            "id": "TSPEC-QUEUE-API-001",
            "test_module": "tests/kernel/queue",
            "suite": "kernel.queue",
            "suite_title": "",
            "req_ids": [],
        },
    }


# ---------------------------------------------------------------------------
# emit site: rst_builders.py:54 — `.. test_case:: {title}`
# ---------------------------------------------------------------------------

def test_build_need_rst_honours_case_type_mapping():
    rst = rb.build_need_rst(_base_info(), "kernel.queue", need_names=NAMES_FULL)
    assert rst.startswith(".. tc_item:: queue put")
    assert ".. test_case::" not in rst


# ---------------------------------------------------------------------------
# emit site: rst_builders.py:64 — `:verifies: {req_ids}`
# ---------------------------------------------------------------------------

def test_build_need_rst_honours_verifies_link_mapping():
    rst = rb.build_need_rst(
        _base_info(req_ids=["zep-srs-20-1"]), "kernel.queue", need_names=NAMES_FULL
    )
    assert ":endorses: zep-srs-20-1" in rst
    assert ":verifies:" not in rst


# ---------------------------------------------------------------------------
# emit site: rst_builders.py:136 — `.. test_procedure:: {title}`
# ---------------------------------------------------------------------------

def test_build_procedure_need_rst_honours_procedure_type_mapping():
    memberdef = ET.fromstring(
        "<memberdef kind='function' id='group__queue__procedures_1b001'>"
        "<name>setup_queue</name>"
        "<briefdescription><para>Set up queue.</para></briefdescription>"
        "<detaileddescription></detaileddescription>"
        "<location file='helpers.c' line='10' bodyfile='helpers.c' bodystart='10'/>"
        "</memberdef>"
    )
    rst = rb.build_procedure_need_rst(
        memberdef, "group__queue__procedures", "queue_procedures",
        "/testspec/html", "/api/html", need_names=NAMES_FULL,
    )
    assert rst.startswith(".. qual_step::")
    assert ".. test_procedure::" not in rst


# ---------------------------------------------------------------------------
# emit site: rst_builders.py:169 — `.. test_result:: {title}`
# ---------------------------------------------------------------------------

def test_build_result_rst_honours_result_type_mapping():
    rst = rb.build_result_rst(
        _base_result(), "TSPEC-QUEUE-API-001", "tests/kernel/queue",
        need_names=NAMES_FULL,
    )
    assert rst.startswith(".. outcome_rec:: queue put")
    assert ".. test_result::" not in rst


# ---------------------------------------------------------------------------
# emit site: rst_builders.py:180 — `:result_of: {spec_id}`
# ---------------------------------------------------------------------------

def test_build_result_rst_honours_result_of_link_mapping():
    rst = rb.build_result_rst(
        _base_result(), "TSPEC-QUEUE-API-001", "tests/kernel/queue",
        need_names=NAMES_FULL,
    )
    assert ":produced_by: TSPEC-QUEUE-API-001" in rst
    assert ":result_of:" not in rst


# ---------------------------------------------------------------------------
# emit site: rst_builders.py:183 — `:covers: {req_ids}`
# ---------------------------------------------------------------------------

def test_build_result_rst_honours_covers_link_mapping():
    rst = rb.build_result_rst(
        _base_result(), "TSPEC-QUEUE-API-001", "tests/kernel/queue",
        req_ids=["zep-srs-20-1"], need_names=NAMES_FULL,
    )
    assert ":addresses: zep-srs-20-1" in rst
    assert ":covers:" not in rst


# ---------------------------------------------------------------------------
# emit site: test_module.py:187/189 — needtable `:filter:`
# (`type == "test_result"`, single- and multi-module variants)
# ---------------------------------------------------------------------------

def test_summary_table_filter_honours_result_type_mapping_single_module():
    grouped = {("s", "queue_put"): [_base_result()]}
    lines = tm._build_summary_table_rst(grouped, _spec_lookup_single(), need_names=NAMES_FULL)
    assert any(
        'type == "outcome_rec" and test_module == "tests/kernel/queue"' in line for line in lines
    )
    assert not any('test_result' in line for line in lines)


def test_summary_table_filter_honours_result_type_mapping_multi_module():
    lookup = {
        "test_a": {"id": "A", "test_module": "mod_a", "suite": "s",
                   "suite_title": "", "req_ids": []},
        "test_b": {"id": "B", "test_module": "mod_b", "suite": "s",
                   "suite_title": "", "req_ids": []},
    }
    grouped = {
        ("s", "a"): [_base_result(function="a")],
        ("s", "b"): [_base_result(function="b")],
    }
    lines = tm._build_summary_table_rst(grouped, lookup, need_names=NAMES_FULL)
    assert any('type == "outcome_rec"' in line and "test_module" not in line for line in lines)
    assert not any('type == "test_result"' in line for line in lines)


# ---------------------------------------------------------------------------
# emit site: test_module.py:197 — needtable `:columns:` (contains `result_of`)
# ---------------------------------------------------------------------------

def test_summary_table_columns_honours_result_of_link_mapping():
    grouped = {("s", "queue_put"): [_base_result()]}
    lines = tm._build_summary_table_rst(grouped, _spec_lookup_single(), need_names=NAMES_FULL)
    text = "\n".join(lines)
    columns_line = next(line for line in lines if line.strip().startswith(":columns:"))
    assert "produced_by" in columns_line
    assert "result_of" not in columns_line
    assert "produced_by" in text


# ---------------------------------------------------------------------------
# Partial mapping (brief §3 decision 5 / §4): override ONE role, all others
# must fall back to the engine default.
# ---------------------------------------------------------------------------

def test_build_need_rst_partial_mapping_only_case_overridden():
    rst = rb.build_need_rst(
        _base_info(req_ids=["zep-srs-20-1"]), "kernel.queue",
        need_names={"case": "tc_item"},
    )
    assert rst.startswith(".. tc_item:: queue put")
    # "verifies" role left unset -> must still default
    assert ":verifies: zep-srs-20-1" in rst


def test_build_result_rst_partial_mapping_only_covers_overridden():
    rst = rb.build_result_rst(
        _base_result(), "TSPEC-QUEUE-API-001", "tests/kernel/queue",
        req_ids=["zep-srs-20-1"], need_names={"covers": "addresses"},
    )
    assert ":addresses: zep-srs-20-1" in rst
    # "result" and "result_of" roles left unset -> must still default
    assert rst.startswith(".. test_result:: queue put")
    assert ":result_of: TSPEC-QUEUE-API-001" in rst


def test_summary_table_partial_mapping_only_result_of_overridden():
    grouped = {("s", "queue_put"): [_base_result()]}
    lines = tm._build_summary_table_rst(
        grouped, _spec_lookup_single(), need_names={"result_of": "produced_by"}
    )
    text = "\n".join(lines)
    assert "produced_by" in text
    # "result" role left unset -> filter must still default
    assert any('type == "test_result"' in line for line in lines)
