Cross-cutting concepts
======================

Concerns that no single building block owns, and that every one of them has to
respect.

The two-stage build
-------------------

Cross-references between documents are circular: a Sphinx document resolves
``:external:`` references against a peer's ``objects.inv``, a Doxygen document
resolves against a peer's tag file, and each peer needs the same from the
other. No build order satisfies that.

So the engine builds everything twice.

**Stage one** produces indexes only. Every Sphinx document runs a dedicated
index builder; every Doxygen document produces its tag file. Nothing published
comes out of this stage, and cross-document references in it are *expected* to
be unresolvable — that is what stage one exists to fix.

**Stage two** rebuilds every document with the complete set of indexes
available, and produces the output that lands in the deploy tree.

Two consequences are worth internalising:

- **Roles resolve at parse time.** An intersphinx or doxylink reference is
  resolved while the document is being read, so a missing peer index bakes a
  dead node into the parsed document that no later stage repairs. This is why
  the stages must not share a parsed-document cache.
- **Stage-one warnings are normal; stage-two warnings are not.** The engine's
  own quality gate is a clean stage-two log, not warning-free builds
  throughout — treating stage one's warnings as errors would fail every correct
  build.

Caching, and how it lies
------------------------

Sphinx caches parsed documents and reuses them aggressively. Three separate
defects in this engine's history are the same shape — a cache answering for
work that was never redone:

- Stage one and stage two must have **separate** caches, or stage two reuses
  stage one's unresolved references.
- The ``html`` and ``latex`` builders must have separate caches, because a
  LaTeX-only include decides at *parse* time whether to pull its content in,
  and Sphinx re-resolves a cached document for a new builder without re-reading
  it. Sharing one cache lets whichever builder runs first decide for both — and
  in the normal order, that silently ships a PDF without its glossary.
- Sphinx invalidates its cache on changed sources and changed configuration but
  **not on changed extension code**, which is why the engine's unit suite wipes
  its build directories between tests
  (:doc:`../decisions/0003-engine-unit-suite`).

The generated doxyfile has four layers
--------------------------------------

Nothing in the file announces this, and everything about it rests on one
Doxygen property: **the last value of a repeated key wins**.

1. The consumer's ``Doxyfile.in`` is expanded first — which is what allows
   everything after it to override.
2. The engine appends its own settings in labelled blocks. Keys the engine owns
   outright are assigned; keys a consumer may legitimately extend are appended
   to. Order matters once: the theme must precede the navigation widget so the
   stylesheet cascade ends correctly.
3. Stage one adds a two-line overlay that includes the stage-two file and
   blanks the tag file list, so stage one does not depend on peers' unbuilt
   tags.
4. At build time, a wrapper writes one more overlay carrying the resolved
   version number and runs Doxygen on *that*.

The practical consequence for a consumer: **a line in your ``Doxyfile.in``
setting a key the engine owns is dead** — read, then discarded. It looks
authoritative and is not. The engine-owned keys are listed in
:doc:`../../reference/registry-schema`.

Paths must not leak into published pages
----------------------------------------

Rendered documentation is published; a build host's directory layout is not
supposed to be part of it. Include paths are stripped against the consumer's
declared roots, and the same discipline applies to anything the engine renders
into a page — including diagnostic nodes such as "test report not found",
which name the file rather than the absolute path. Logs are exempt: they are
not published artifacts, and a log that names the full path is the fastest way
to fix the problem.

Version resolution
------------------

A document's version comes from the *consuming* repository's git tags, scoped
per document, so two documents in one repository can carry independent version
lines. Both toolchains resolve it through the same code, so they cannot
disagree about the version of one repository, and the value reaches Doxygen at
build time rather than configure time.

Absolute URLs, and where they end up
------------------------------------

Cross-document **Sphinx** links are absolute URLs under the set's base URL,
while **Doxygen**'s are relative hops. A deploy tree opened from the filesystem
therefore has working Doxygen cross-links and broken Sphinx ones — expected,
not a defect.

It matters most for PDFs, which are the one artifact that leaves the deploy
tree. The base URL is baked in at build time, so a PDF built with a development
base URL points at a host that does not exist — permanently, in a document that
may already be signed.
