# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Placement root 1 of 3 (brief decision 7): the directive sits under the
document's OWN heading. Today's (defective) Title for this shape is that
heading's text, "Falcon Bay Notes" -- not the configured project.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

extensions = ["doc_control"]
master_doc = "index"
exclude_patterns = ["_build"]

# Deliberately shares no substring (>=3 chars) with any heading in index.rst
# (brief §4 rule 5) -- verified in test_doc_control.py -- so an
# implementation that still reads the doctree's title node cannot pass by
# accident.
project = "Meridian Assurance Manual"
zdocs_doc_id = "meridian-qms"
