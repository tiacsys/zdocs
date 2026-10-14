# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

extensions = ["sphinx_needs", "pdf_tables"]
master_doc = "index"
exclude_patterns = ["_build"]
suppress_warnings = ["config.cache"]
latex_documents = [("index", "tables.tex", "Tables", "zdocs", "howto")]

needs_types = [
    dict(directive="req", title="Requirement", prefix="REQ_", color="#FDEBD0", style="node"),
]
_field = {"schema": {"type": "string"}, "nullable": True}
needs_fields = {name: dict(_field) for name in ("platform", "scenario", "module", "reason")}
needs_id_regex = r"^[A-Z0-9_-]{5,}"
