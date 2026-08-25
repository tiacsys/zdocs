# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# Point the testcase.yaml lookup at a directory that has none, so
# build_scenario_table() returns [] and these roots stay focused on the
# directive itself. This used to set ZEPHYR_BASE: step 27 removed that
# fallback from test_module.py (the engine now supplies testmodule_root
# from ZDOCS_PROJECT_BASE), which left the env line inert but
# authoritative-looking -- the exact trap step 24a cleaned up elsewhere.
testmodule_root = str(_FIXTURES)

extensions = ["sphinx_needs", "test_module"]
master_doc = "index"
exclude_patterns = ["_build"]

# --- zdocs step 26 (does not exist yet) ---------------------------------
# A consumer adopting the new role->name mapping renames the sphinx-needs
# types/links it declares to its own QMS vocabulary, and tells the engine
# about the rename via testmodule_need_types / testmodule_need_links below.
# Overrides share no substring with the engine defaults ("test_case",
# "test_procedure", "verifies") so a broken implementation that merely
# appends/prefixes the default cannot pass these tests by accident.
needs_types = [
    dict(directive="tc_item",   title="Test Case",      prefix="TCASE_",
         color="#E2EFDA", style="node"),
    dict(directive="qual_step", title="Test Procedure", prefix="TPROC_",
         color="#D6E4F7", style="node"),
]
_str_field = {"schema": {"type": "string"}, "nullable": True}
needs_fields = {
    "test_function": {**_str_field},
    "test_module":   {**_str_field},
    "suite":         {**_str_field},
    "suite_title":   {**_str_field},
}
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"
needs_links = {
    "endorses": {"description": "endorses", "incoming": "endorsed by", "outgoing": "endorses"},
}
needs_build_json = True
suppress_warnings = ["needs.link_outgoing", "config.cache"]

testmodule_xml_dir = str(_FIXTURES / "doxygen")

testspec_doxygen_url = "testspec"
api_doxygen_url = "api"

# The feature under test. NOT YET REGISTERED via app.add_config_value, so
# Sphinx accepts these as inert conf.py attributes and test_module.py never
# reads them: the directive keeps emitting the OLD literal
# `.. test_case::` / `.. test_procedure::` / `:verifies:`, which the
# needs_types/needs_links above no longer declare -> docutils rejects the
# emitted directives as unknown.
testmodule_need_types = {"case": "tc_item", "procedure": "qual_step"}
testmodule_need_links = {"verifies": "endorses"}
