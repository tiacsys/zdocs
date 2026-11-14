0017. A document can name the documents whose needs it imports
===============================================================

Status
------

Proposed, 2026-11-14.

Context
-------

Every document of a set imports the needs of every peer with a ``needs:``
block (``needs_external_needs``). That is simple and shows every incoming link
everywhere, but:

- A downstream set that builds upstream documents through ``doc_dir:`` must
  list every indirect upstream document too, else the upstream documents get
  dangling links — and nothing says which ones are needed.
- Each needs warning repeats once per importing document. Under a strict
  build each of them fails, and most are in documents that only import the
  broken need.
- An upstream document built downstream shows the downstream documents'
  incoming links, so it differs from the upstream's own build.

Decision
--------

An optional ``imports:`` list per ``kind: sphinx`` document. Without it,
nothing changes: the document imports every peer's needs.

With it, the document imports the needs of the listed documents and,
transitively, of the documents those list in their own ``imports:``. An
imported need keeps its links, and they resolve only if their targets are
imported too, so a document lists only its direct upstream documents.

A listed document without ``imports:`` adds only itself. Taking "without a
list" as "every peer" here would make one unlisted upstream document undo the
narrowing for all its importers.

The key is validated at configure time: each id exists, publishes needs, is
in the link graph (``crossref``) and is not the document itself.

Only the needs import changes. Intersphinx, doxylink, Doxygen ``TAGFILES``
and the navigation stay all-to-all.

Consequences
------------

- A downstream document lists its direct upstream documents; their own
  upstream documents come along if those carry ``imports:``.
- The imported set decides the incoming links a document shows. An upstream
  document with ``imports: []`` shows no links from downstream documents:
  the same as in its own repository's build, without the impact view.
- An imported document whose needs link into a document that is not
  imported warns ``needs.external_link_outgoing`` in the importer. The fix is
  in the registry: list the document, or give the imported one ``imports:``.
- The documents to import still have to be built in the same set. Reading the
  ``imports:`` of an upstream repository's own registry, so a downstream set
  need not list (and build) the indirect upstream documents at all, is not
  part of this decision.
