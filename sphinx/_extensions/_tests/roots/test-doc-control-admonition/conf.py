# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Placement root 2 of 3 (brief decision 7): the directive is preceded by a
``.. todo::`` block, not a heading. Today's (defective) Title for this shape
is "Todo" -- the admonition's own generated title node, which
``doctree.next_node(nodes.title)`` finds before anything else in the tree.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

extensions = ["sphinx.ext.todo", "doc_control"]
master_doc = "index"
exclude_patterns = ["_build"]

# Same project/id as the other two placement roots (brief decision 7: "all
# three set the same project and the same zdocs_doc_id"). Shares no
# substring (>=3 chars) with "Todo" or with any heading in the other roots'
# index.rst -- verified in test_doc_control.py.
project = "Meridian Assurance Manual"
zdocs_doc_id = "meridian-qms"
