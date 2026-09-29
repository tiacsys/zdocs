0012. Cross-document links in the HTML tree are relative
=========================================================

Status
------

Accepted, 2026-09-29. Supersedes the "absolute URLs under the base URL"
consequence of :doc:`0011-documentation-structure`.

Context
-------

Every cross-document Sphinx link — the sidebar navigation, intersphinx
references, doxylink roles and imported needs — was an absolute URL under the
registry's ``base_url``. A deploy tree therefore only worked when served at
exactly that URL: a local preview was pinned to one host and port, a branch
deploy needed a rebuild with an override, and a tree opened from ``file://``
had dead Sphinx links. Doxygen's links were relative all along.

Decision
--------

Output built into ``deploy/html/`` links its locally built peers by path
relative to its own HTML root. Each consumer of that path resolves it for the
referencing page: intersphinx and sphinx-needs against the document's depth,
doxylink against the source file's, the sidebar template via
``content_root``. ``base_url`` still applies to every other output — a PDF,
the ``html-live`` preview — which has no sibling tree to be relative to.
Remote documents keep their absolute ``remote-url``.

Consequences
------------

- ``deploy/html/`` can be served from any host, port or subdirectory, or
  browsed from the filesystem, without a rebuild.
- A PDF still bakes ``base_url`` in, so a registry's ``base_url`` should name
  the published site rather than a local preview.
- ``needflow`` graphs render an imported need with a relative URL as an
  unlinked node: sphinx-needs only links external needs whose URL has a scheme.
