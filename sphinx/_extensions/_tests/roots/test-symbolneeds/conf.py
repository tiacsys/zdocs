# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

extensions = ["sphinx_needs", "symbol_needs"]
master_doc = "index"
exclude_patterns = ["_build"]

# The consumer's vocabulary: a requirement type, and the engine's
# `implementation` role under its default name `impl`.
needs_types = [
    dict(directive="req",  title="Requirement",    prefix="REQ_",  color="#FDEBD0", style="node"),
    dict(directive="impl", title="Implementation", prefix="IMPL_", color="#E2EFDA", style="node"),
]
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"
needs_links = {
    "satisfies": {"description": "satisfies", "incoming": "satisfied by", "outgoing": "satisfies"},
}
needs_build_json = True
suppress_warnings = ["config.cache"]

# Real Doxygen 1.16.1 output (fixtures/doxygen-symbols/Doxyfile).
symbolneeds_xml_dir = str(_FIXTURES / "doxygen-symbols")
symbolneeds_doxygen_url = "api"
