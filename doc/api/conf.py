# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

# zdocs API Reference — conf.py shim (F1) plus autodoc (D4) and the CMake
# domain (D3), extracted from the engine's own sources.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

ENGINE_ROOT = Path(os.environ["ZDOCS_CONF_DIR"]).resolve().parent

sys.path.insert(0, str(ENGINE_ROOT / "sphinx" / "_extensions"))
sys.path.insert(0, str(ENGINE_ROOT / "scripts"))

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="zdocs API Reference",
    extensions=[
        "sphinx.ext.autodoc",
        "sphinx.ext.napoleon",
        "sphinx.ext.viewcode",
        "sphinxcontrib.moderncmakedomain",
    ],
)

external_content_contents.append((ENGINE_ROOT, "cmake/*.cmake"))

autodoc_member_order = "bysource"
