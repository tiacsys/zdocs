# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

# zdocs Manual — thin conf.py shim (F1).
#
# ZDOCS_CONF_DIR is exported into every sphinx-build (sphinx.cmake:212) and
# equals <engine>/sphinx; every consumer conf.py in this repository opens the
# same way, deriving the engine root from it rather than __file__ arithmetic,
# which is fragile under external_content's source copy.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="zdocs Manual",
    extensions=[
        # sphinx.ext.graphviz: the architecture pages
        # (explanation/architecture/) render C4-style diagrams with
        # `.. graphviz::` directives. Consumer extension only (D5 does not
        # forbid it — it changes no theme).
        "sphinx.ext.graphviz",
        # The manual's own reference pages carry `:external+zdocs-api:cmake:
        # command:` roles into the api document. Sphinx's external/intersphinx
        # role resolution needs the "cmake" DOMAIN registered in THIS app too
        # (not just in the api document being referenced) or it warns "domain
        # for external cross-reference not found: 'cmake'" — measured: this
        # extension registers no directives of its own here (this document
        # has no .cmake sources to extract), it only makes the domain exist so
        # the role parses and resolves against the api document's inventory.
        "sphinxcontrib.moderncmakedomain",
    ],
)

graphviz_output_format = "svg"
