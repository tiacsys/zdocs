# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

extensions = ["sphinx_needs", "test_module"]
master_doc = "index"
exclude_patterns = ["_build"]

# --- zdocs step 26 (does not exist yet) -----------------------------------
# A consumer renames the sphinx-needs "result" type and its "result_of" /
# "covers" links to its own vocabulary and tells the engine via
# testmodule_need_types / testmodule_need_links below. "test_case" is left
# as-is: it is only referenced here (via needs_external_needs) to resolve
# the external test_case ids the test_result needs link back to; it is not
# emitted by this directive and is out of this test's scope.
needs_types = [
    dict(directive="outcome_rec", title="Test Result", prefix="TRESULT_",
         color="#FCE4D6", style="node"),
    dict(directive="test_case",   title="Test Case",   prefix="TCASE_",
         color="#E2EFDA", style="node"),
]
_str_field = {"schema": {"type": "string"}, "nullable": True}
needs_fields = {
    "platform":       {**_str_field},
    "scenario":       {**_str_field},
    "twister_id":     {**_str_field},
    "execution_time": {**_str_field},
    "reason":         {**_str_field},
    "test_function":  {**_str_field},
    "test_module":    {**_str_field},
    "suite":          {**_str_field},
    "suite_title":    {**_str_field},
}
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"
needs_links = {
    "produced_by": {"description": "produced by", "incoming": "produces",
                    "outgoing": "produced by"},
    "addresses":   {"description": "addresses",    "incoming": "addressed by",
                    "outgoing": "addresses"},
    "verifies":    {"description": "verifies",     "incoming": "verified by",
                    "outgoing": "verifies"},
}
needs_external_needs = [{
    "json_path": str(_FIXTURES / "needs" / "needs.json"),
    "base_url": "http://localhost/",
    "version": "1.0",
}]
twister_output_dir = str(_FIXTURES / "twister")
testspec_doxygen_url = "testspec"
api_doxygen_url = "api"
needs_build_json = True
suppress_warnings = ["needs.link_outgoing", "needs.external_link_outgoing", "config.cache"]

# The feature under test. NOT YET REGISTERED via app.add_config_value, so
# Sphinx accepts these as inert conf.py attributes and test_module.py never
# reads them: the directive keeps emitting the OLD literal
# `.. test_result::` / `:result_of:` / `:covers:`, which the
# needs_types/needs_links above no longer declare -> docutils rejects the
# emitted directive as unknown, and the needtable's own :filter:/:columns:
# (built by _build_summary_table_rst) still query "test_result"/"result_of"
# literally, so even if the need existed it would be filtered out of the
# summary table -- the "green build, empty table" defect decision 2 warns
# about.
testmodule_need_types = {"result": "outcome_rec"}
testmodule_need_links = {"result_of": "produced_by", "covers": "addresses"}
