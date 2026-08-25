# Copyright (c) 2026 almedso GmbH
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""``:qmsdoc:`` role — reference a ``kind: external`` registry document
(e.g. a QMS SOP) from content.

    :qmsdoc:`sop-swdp`
    :qmsdoc:`SOP-SWDP <sop-swdp>`

Standard ``:ref:``/``:external+prefix:ref:`` roles can't resolve these:
they have no local label (``:ref:``) and are deliberately excluded from
``intersphinx_mapping`` (``:external+prefix:ref:`` — no ``objects.inv`` to
fetch; see documents.yaml's own field docs and ``check_external_urls``).
This role instead looks the target up directly in documents.yaml (via
``scripts/docrefs.py``'s ``external_doc()``), which is exactly what the
registry already has: a title and a fixed remote-url:, no build/probing needed.

Renders as a real hyperlink for HTML; plain text for every other builder
(there's no useful notion of a live web link in, say, a PDF). The role itself
always emits a ``nodes.reference`` — deciding per-builder cannot happen at
parse/role time, because the stage-2 ``html`` and ``latex`` builders of one
document share a doctree cache (``-d ${DOCS_DOCTREE_DIR}``), so whichever ran
first would freeze the node type for the other. Instead the reference is tagged
(``qmsdoc_external``) and converted to plain text per-build in a
``doctree-resolved`` handler, mirroring doc_control.py's signature_section.

(That reasoning used to cite the stage-1/stage-2 caches, which have been
separate since the D10 fix. The html/latex pair still share one, so the
conclusion stands and only the reason needed correcting.)
"""

import os
import re

import docrefs
from docutils import nodes
from sphinx.util.docutils import SphinxRole

# The registry arrives in the environment, like everywhere else in zdocs.
#
# It used to be `Path(__file__).parents[1] / "documents.yaml"` — the registry
# sitting next to the extension, which was true only while this file lived in
# the consuming repository. In the engine that path is zdocs' own doc/ directory,
# which has no registry and never will.
_REGISTRY = os.environ.get("ZDOCS_REGISTRY") or None

_EXPLICIT_TITLE_RE = re.compile(r"^(?P<title>.+?)\s*<(?P<target>[^<>]+)>$")


def _split_title(text):
    """``"Title <target>"`` -> ``(title, target)``; plain ``"target"`` ->
    ``(None, target)`` (caller falls back to the registry's own title).
    """
    text = text.strip()
    m = _EXPLICIT_TITLE_RE.match(text)
    if m:
        return m.group("title").strip(), m.group("target").strip()
    return None, text


class QmsDocRole(SphinxRole):
    def run(self):
        title, target = _split_title(self.text)

        resolved = docrefs.external_doc(target, registry=_REGISTRY)
        if resolved is None:
            msg = self.inliner.reporter.error(
                f"qmsdoc: {target!r} is not a 'kind: external' document in documents.yaml",
                line=self.lineno,
            )
            problematic = self.inliner.problematic(self.rawtext, self.rawtext, msg)
            return [problematic], [msg]

        registry_title, url = resolved
        node = nodes.reference(self.rawtext, title or registry_title, refuri=url)
        node["qmsdoc_external"] = True
        return [node], []


def _plain_text_for_non_html(app, doctree, docname):
    if app.builder.format == "html":
        return
    for node in list(doctree.findall(nodes.reference)):
        if node.get("qmsdoc_external"):
            node.replace_self(nodes.Text(node.astext()))


def setup(app):
    app.add_role("qmsdoc", QmsDocRole())
    app.connect("doctree-resolved", _plain_text_for_non_html)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
