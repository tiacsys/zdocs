# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

extensions = ["sphinx_needs", "need_cards"]
master_doc = "index"
exclude_patterns = ["_build"]
suppress_warnings = ["config.cache"]

needs_types = [
    dict(directive="req",  title="Requirement", prefix="REQ_",  color="#FDEBD0", style="node"),
    dict(directive="spec", title="Test Case",   prefix="SPEC_", color="",        style="node"),
]
