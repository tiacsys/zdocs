0004. The registry is the single source of truth for document declarations
===========================================================================

Status
------

Accepted.

Context
-------

The engine has central registry — ``documents.yaml`` — describing
every document in a set: its kind, its group, its cross-reference prefix, the
base URL the set is published under. Everything that computes a cross-document
link reads it: intersphinx mappings, Doxygen ``TAGFILES``, the navigation
sidebar shared by both toolchains, the needs imports.

But the consuming project *also* declared every document a second time, by
hand, in its ``doc/CMakeLists.txt`` — one ``add_sphinx_target()`` or
``add_doxygen_target()`` call per document, restating the kind and the source
folder the registry already knew. Two sources of the same truth, kept in step
by nobody, in a codebase whose recurring defect is a value computed correctly
in one place and never wired into the other.

Decision
--------

One call replaces all of them:

.. code-block:: cmake

   add_docs_from_registry(REGISTRY ${DOC_REGISTRY})

``add_docs_from_registry()`` asks the registry for a manifest of every
document, and dispatches per entry: an ``external`` kind produces no build
target at all, a ``doxygen`` kind goes to the Doxygen factory, everything else
to the Sphinx factory. A Sphinx entry with no ``builders:`` list is a fatal
error naming the document, not a silently skipped one.

The registry is consequently the place where a document is **declared**, and
per-document sub-blocks are how a document **opts in** to engine features: a
``needs:`` block makes it publish and import sphinx-needs data, a
``testmodule:`` block is the sole trigger that loads the test-specification
extension for it.

Consequences
------------

- Adding a document is a registry entry plus a source folder. Nothing else
  changes — see :doc:`../../howto/add-a-document`.
- Per-group aggregate build targets fall straight out of the same loop, because
  the dispatcher already knows every document's group and builders. A group and
  builder pair with no contributors simply gets no target, with no special case
  needed.
- The factories remain public and callable by hand, because a document with a
  requirement the registry has no field for still has to be expressible.
