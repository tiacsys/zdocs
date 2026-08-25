# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Stage-1 ``xref`` builder for the two-stage documentation build.

Cross-referenced documents form a dependency cycle: each doc's HTML needs the
*indexes* (``objects.inv`` / ``needs.json`` / Doxygen tag files) of the docs it
links to. Those indexes depend only on a doc's own content, so the build is
split in two:

  * stage 1 — every doc emits just its index (this builder), no HTML;
  * stage 2 — every doc builds HTML with all indexes present, so cross
    references resolve.

This builder subclasses Sphinx's ``dummy`` builder: it reads/parses the whole
project (populating the environment) but writes no HTML. In ``finish()`` it
dumps ``objects.inv`` for intersphinx. ``needs.json`` is handled separately by
sphinx-needs itself: when ``needs_build_json = True`` its ``build-finished``
hook writes ``needs.json`` into the same output directory regardless of the
active builder — so a sphinx-needs doc gets both artifacts from one xref build.

Stage 2 uses a SEPARATE doctree cache (``-d``) and parses for itself, once every
peer index exists. Sharing one cache is what this build system used to do, and it
was wrong: a role that resolves at parse time — ``:external+<inv>:`` is one — was
resolved during stage 1 against inventories that did not exist yet, and stage 2,
reusing that parse, wrote the empty result out. See the doctree comment in
``zdocs/cmake/sphinx.cmake``.
"""

from __future__ import annotations

import os

from sphinx.builders.dummy import DummyBuilder
from sphinx.util.inventory import InventoryFile


class XrefBuilder(DummyBuilder):
    name = "xref"
    epilog = "Cross-reference index written to %(outdir)s."

    def get_target_uri(self, docname, typ=None):
        # Inventory URIs must match what the html builder would emit, so links
        # resolved against this inventory in stage 2 point at the real pages.
        return docname + ".html"

    def finish(self):
        InventoryFile.dump(os.path.join(self.outdir, "objects.inv"), self.env, self)


#: Warnings that are guaranteed during stage 1 and mean nothing there.
#:
#: `intersphinx.external` is emitted by IntersphinxRole once per reference whose
#: inventory is not loaded. At stage 1 that is every cross-document reference in
#: the project, because the inventories ARE this stage's output — no build order
#: could have produced them first, and clearing the mapping below guarantees the
#: role finds nothing even where a stale one happens to exist on disk.
#:
#: Suppressed only for the `xref` builder. Stage 2 keeps the warning, and there
#: it is a real signal: an inventory missing once every document has published
#: one means a reference to a document that does not exist.
#: `needs.link_outgoing` and `needs.link_ref` fire for every reference to a need
#: defined in ANOTHER document. Those arrive via `needs_external_needs`, whose
#: entries docrefs gates on the target's needs.json existing when conf.py is
#: evaluated — on a cold stage 1 none of them do, because that file is this
#: stage's own output. The links are recorded in the export regardless (the field
#: holds the id, resolved or not), so stage 1's deliverable is unaffected.
#:
#: Stage 2 keeps both, and there a genuinely unknown id — a typo, a deleted
#: need — is reported normally.
_EXPECTED_STAGE_ONE_WARNINGS = [
    "intersphinx.external",
    "needs.link_outgoing",
    "needs.link_ref",
]


def _quieten_xref_stage(app):
    """Stage 1 only needs to emit *this* document's own objects.inv/needs.json
    — cross-document references get resolved anyway (and discarded, since
    write_doc() above is a no-op), but that's wasted work, not something this
    stage depends on. sphinx.ext.intersphinx's own builder-inited handler
    (load_mappings, default priority 500) eagerly fetches EVERY sibling's
    objects.inv regardless of whether this doc's content references it at
    all — none of those siblings exist yet at stage 1, so that's the
    "missing objects.inv" warning firing once per sibling per doc. Clearing
    intersphinx_mapping here (priority 100, so this runs before
    load_mappings on the same event) skips that fetch entirely.

    Stage 2 is unaffected: BuildEnvironment.get_and_resolve_doctree() always
    re-resolves a fresh copy of each doctree per builder invocation (see
    Builder._write_serial -> _write_docname), so it does its own independent
    resolution pass against the by-then-complete sibling inventories,
    regardless of what stage 1 did or didn't manage to resolve.

    SIDE EFFECT, worth knowing before touching this: ``intersphinx_mapping`` is
    declared with ``rebuild='env'``, so emptying it here makes stage 2 — which
    sees it populated again — count as a config change and re-read every
    document. That happens to prevent D10 by itself, independently of the split
    doctree caches in ``cmake/sphinx.cmake``; disabling both is what it takes to
    reproduce the defect. This function is still only an optimisation and must
    not be treated as the fix: the caches are.
    """
    if app.builder.name != "xref":
        return

    app.config.intersphinx_mapping = {}

    # Silence the warnings that clearing the mapping guarantees. Sphinx's
    # WarningSuppressor reads app.config.suppress_warnings at EMIT time, so
    # extending it here (builder-inited) applies to the whole run — verified
    # against sphinx.util.logging rather than assumed, since a config read once
    # at startup would have made this silently do nothing.
    #
    # Extends rather than replaces: a consumer may have its own suppressions and
    # the engine has no business dropping them.
    app.config.suppress_warnings = [
        *app.config.suppress_warnings,
        *_EXPECTED_STAGE_ONE_WARNINGS,
    ]


def setup(app):
    app.add_builder(XrefBuilder)
    app.connect("builder-inited", _quieten_xref_stage, priority=100)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
