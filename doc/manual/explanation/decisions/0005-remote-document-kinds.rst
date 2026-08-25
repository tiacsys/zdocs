0005. Remote documents are three kinds, not one
================================================

Status
------

Accepted.

Context
-------

A documentation set almost always references material it does not build: an
upstream project's manual, a vendor's API reference, a corporate document
living behind another URL entirely.

An upstream Sphinx site publishes ``objects.inv``; an upstream
Doxygen site publishes a tag file. Both are exactly what the engine already
consumes between two *locally built* documents. Treating a remote peer as an
opaque URL throws away cross-referencing that costs almost nothing to keep.

Sphinx and Doxygen are not symmetric here, which is what shaped the decision.
Sphinx's own intersphinx extension fetches a remote ``objects.inv`` over HTTP
itself — mature, cached, retrying, entirely Sphinx's machinery. Doxygen has no
equivalent capability at all: a tag file must be a local file.

Decision
--------

Three kinds, whitelisted and independently validated:

``external``
   No index, no cross-referencing. A named link under the set's external base
   URL, reachable through the ``:qmsdoc:`` role.

``sphinx-external``
   A remote Sphinx site. The engine adds it to ``intersphinx_mapping``; Sphinx
   fetches ``objects.inv`` itself at build time. Requires ``remote-url:``.

``doxygen-external``
   A remote Doxygen site. The **engine** downloads the tag file, at build time,
   in the same stage local tag files are produced, and wires it into doxylink
   and ``TAGFILES`` with the remote site as its location base. Requires
   ``remote-url:`` **and** ``remote-tagfile:`` — two separate, separately
   validated fields, because Doxygen tag-file names are not standardised the
   way ``objects.inv`` is and one cannot be derived from the other.

Consequences
------------

- A remote peer is fetched fresh on every build, with no caching. That matches
  how the engine already recomputes tag files and navigation links, and it
  makes a stale local copy impossible.
- Because the download is wired into the same stage-1 gate every local document
  already depends on, no per-consumer wiring is needed: existing documents pick
  up the dependency for free.
