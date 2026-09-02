# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Decision-3 fallback root: NO ``zdocs_doc_id`` is set at all -- the
standalone-extension path (no ``zdocs_conf``), which is exactly what every
root in this directory is. The directive itself sits in ``doc-control.rst``,
reached via a toctree from ``index.rst``, so its docname is "doc-control"
(mirroring the real fixture shape described in the brief §1) and the
fallback (``posixpath.basename(env.docname)``) must publish "doc-control".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

extensions = ["doc_control"]
master_doc = "index"
exclude_patterns = ["_build"]

# project is set (a document without SOME project would be an unrelated
# defect); zdocs_doc_id is deliberately absent.
project = "Meridian Assurance Manual"
