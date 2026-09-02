# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Placement root 3 of 3 (brief decision 7): nothing at all precedes the
directive -- no heading, no admonition. Today's (defective) Title for this
shape is the literal string "<no title>", since
``doctree.next_node(nodes.title)`` finds no title node at all.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

extensions = ["doc_control"]
master_doc = "index"
exclude_patterns = ["_build"]

# Same project/id as the other two placement roots (brief decision 7).
project = "Meridian Assurance Manual"
zdocs_doc_id = "meridian-qms"
