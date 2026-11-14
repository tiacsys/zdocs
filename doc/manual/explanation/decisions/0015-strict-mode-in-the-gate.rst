0015. Strict mode reports in the doc-check gate
===============================================

Status
------

Proposed, 2026-11-14.

Context
-------

By default a Sphinx warning does not fail a zdocs build: a dangling need
link, a sphinx-needs schema violation (even one of severity ``violation``)
and an unresolved reference all pass, and ``doc-check`` reads HTML links, not
needs links. Consumers that want these to fail added
``-DZDOCS_SPHINXOPTS_EXTRA="-W;--keep-going"``.

With ``-W`` each failing ``sphinx-build`` fails its target, and Ninja (or
Make) stops at the first failed target. Every document imports the needs of
its peers, so a dangling link in one document also warns in each document
that imports it (``needs.external_link_outgoing``). The first target to fail
is then often an innocent document, and the one with the broken link never
reports. Consumers worked around it with ``cmake --build … -- -k 0``, which
CMake cannot set from the configure step and which differs per build tool.

The documentation guidelines already name the gate: ``doc-check`` plus a
clean stage-2 build log, not ``sphinx-build -W``, because stage 1 has
warnings that mean nothing there.

Decision
--------

A cache option ``ZDOCS_STRICT`` (default ``OFF``). When on:

- Sphinx runs as before, without ``-W``: a warning does not fail the target,
  so every document is built, whatever the build tool and its options.
- ``add_doc_check`` runs ``doccheck.py --strict``. That reads the stage-2
  warning file (``sphinx-build -w``) of every Sphinx build of the set and
  reports every warning and error as a finding, prefixed with the document
  and builder. The gate fails once, at the end, and names every document
  with a warning.
- Stage-1 warning files are not read. Stage 2 parses every document again,
  so a real warning shows there too.
- Findings go through ``doc_check_accepted:`` like the other checks; the
  build directory is cut from them so the text is the same on every host.
- ``ZDOCS_STRICT`` without an ``add_doc_check()`` call is a configure error:
  strict mode would otherwise do nothing.

Consequences
------------

- One switch for a strict build, with no ``-W`` and no ``-k 0``. A
  ``-W`` in ``ZDOCS_SPHINXOPTS_EXTRA`` still works as before.
- A single document target (``<doc>-html``) built alone does not fail on its
  warnings; only the gate does (``all-docs``, ``doc-check``). The warnings
  are still printed by Sphinx.
- Like ``-W``, the gate sees the warnings of the documents the last build
  read again. An incremental build that reads nothing again reports nothing;
  CI builds from scratch.
- A dangling link is still reported once per importing document; the
  document that holds it is now always among them.
- Schema violations are read from the warning file, not from sphinx-needs'
  ``schema_violations.json``.
