The registry, and what it derives
=================================

``documents.yaml`` is a description of a documentation *set*: which documents
exist, what kind each is, how they group in navigation, what namespace each
owns, and where the set is published. It is the only file in which a document
is declared, and everything else about the build is computed from it.

This page follows what a single entry produces. The field-by-field reference is
:doc:`../reference/registry-schema`; the decision behind it is
:doc:`decisions/0004-registry-as-single-source-of-truth`.

One reader, two callers
-----------------------

``docrefs.py`` is the only code that parses the registry, and it serves two
very different callers:

- **CMake**, at configure time, asks for a manifest — a flat list of every
  document with its kind, group, source folder and builders — and dispatches
  one document factory per entry.
- **Every document's** ``conf.py``, at build time, asks for the wiring *this
  document* needs: the intersphinx mappings to its peers, the doxylink
  prefixes, the needs imports, the navigation groups.

Two callers in two languages reading one file is deliberate. The alternative —
CMake computing values and passing them into Sphinx — is what the engine used
to do, and it is how a set once ended up with a correct tag file list in CMake
and none of it reaching the tool that needed it.

What one entry produces
-----------------------

A single ``kind: sphinx`` entry with a ``builders: [html]`` list results in:

- a stage-one target that builds only this document's cross-reference index;
- a stage-two ``<id>-html`` target that produces the published output;
- a contribution to its group's aggregate target, ``<group>-html``;
- a clean target enumerating one path per builder;
- an entry in **every other document's** intersphinx mapping, under this
  document's prefix;
- a navigation entry, in this document's group, on every page of every
  document in the set — including the Doxygen ones;
- an absolute URL under the set's base URL, which is how the entry above and
  every cross-document link is addressed.

A ``kind: doxygen`` entry produces the same shape through the other toolchain:
a tag file instead of an inventory, doxylink instead of intersphinx.

Opt-in by sub-block
-------------------

Engine features that only some documents want are enabled by the *presence of a
sub-block*, not by a boolean:

``needs:``
   This document publishes sphinx-needs data, and imports every peer's.

``testmodule:``
   This document renders test specifications or test reports. The block is the
   sole trigger that loads the extension and supplies its paths — a document
   without one never loads it at all.

Presence-as-opt-in matters more than it looks. The negative case is
load-bearing and is tested: without a document that carries *no* block, a test
proving the block works would pass equally against an engine that loaded the
extension unconditionally for everyone.

Validation is a configure-time error
------------------------------------

An unknown ``kind``, a group that no ``groups:`` entry declares, a remote
document with no URL, an unknown key inside a sub-block: each is a fatal error
naming the document, before anything is built.

That strictness is a scar. An unrecognised ``kind`` string once fell through
every call site to "treat it as an ordinary local Sphinx document" — the exact
opposite of what every remote kind means — and produced a build that failed
much later, somewhere unrelated. A typo in a registry must not degrade into a
plausible-looking wrong build.
