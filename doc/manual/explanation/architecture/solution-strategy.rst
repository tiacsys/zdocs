Solution strategy
=================

Five decisions shape everything else about zdocs. Each is stated here as the
approach taken; the reasoning lives in the linked ADRs.

Consumed as a Zephyr module, by name
------------------------------------

The engine is reached through Zephyr's module system —
``ZEPHYR_ZDOCS_MODULE_DIR`` on the module path, then ``include(zdocs)`` — so no
consumer writes a path into the engine and the same engine serves any number of
projects. Everything the engine needs from the project arrives through the
``ZDOCS_*`` variables. See
:doc:`../decisions/0001-zephyr-module-seam`.

One registry, derived everywhere
--------------------------------

``documents.yaml`` describes the set once: every document's kind, group,
cross-reference prefix, source folder, builders and feature opt-ins. Build
targets, intersphinx mappings, Doxygen tag file lists, navigation entries,
needs imports and group aggregates are all *derived* from it. A consumer
declares a document in exactly one place. See
:doc:`../decisions/0004-registry-as-single-source-of-truth`.

Everything is built twice
-------------------------

Cross-references between documents are circular by nature: A cannot resolve
against B's index until B has produced one, and vice versa. Rather than
ordering documents — which cannot work for a cycle — the engine builds the
whole set in two stages. Stage one produces every document's index; stage two
rebuilds everything against the complete set. See :doc:`crosscutting`.

Two toolchains, one presentation
--------------------------------

Sphinx and Doxygen documents are peers. They share a navigation sidebar
computed from the same registry, the same version-resolution rules and the same
branding hooks, and they cross-reference each other in both directions —
doxylink from Sphinx into Doxygen symbols, tag files and a navigation widget
from Doxygen back into the prose.

The engine takes ownership of the small number of tool settings this requires,
overriding a consumer's own values for those keys, and leaves every other
setting to the consumer.

The test suite is a consumer
----------------------------

The engine's primary tests are a separate project that consumes zdocs the way a
real one does, builds real documentation, and asserts on rendered output. The
engine additionally carries a fast unit suite for its pure-Python parts. See
:doc:`../decisions/0002-acceptance-tests-in-a-consumer-repo` and
:doc:`../decisions/0003-engine-unit-suite`.
