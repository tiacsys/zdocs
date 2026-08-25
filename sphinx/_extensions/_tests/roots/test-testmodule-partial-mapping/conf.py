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
# PARTIAL mapping (brief §3 decision 5, §4): only the "case" role is
# overridden here; "procedure" is deliberately left unset in
# testmodule_need_types below and must fall back to the engine default
# "test_procedure" -- which is exactly why needs_types still declares
# "test_procedure" verbatim while "case" is renamed to "tc_item". The link
# role "verifies" is likewise left unset and must keep defaulting to
# "verifies".
needs_types = [
    dict(directive="tc_item",        title="Test Case",      prefix="TCASE_",
         color="#E2EFDA", style="node"),
    dict(directive="test_procedure", title="Test Procedure", prefix="TPROC_",
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
    "verifies": {"description": "verifies", "incoming": "verified by", "outgoing": "verifies"},
}
needs_build_json = True
suppress_warnings = ["needs.link_outgoing", "config.cache"]

testmodule_xml_dir = str(_FIXTURES / "doxygen")

testspec_doxygen_url = "testspec"
api_doxygen_url = "api"

# Only "case" is overridden; "procedure" is intentionally absent so the
# fallback-to-default rule (decision 5) can be pinned.
testmodule_need_types = {"case": "tc_item"}
