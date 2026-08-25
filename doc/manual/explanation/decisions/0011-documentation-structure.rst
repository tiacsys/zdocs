0011. Documentation structure: Diátaxis, arc42-lite, and two documents
=======================================================================

Status
------

Accepted.

Context
-------

Splitting the engine payload out of ``doc/``
(:doc:`0010-payload-split-by-tool`) left the engine with an empty folder and no
documentation of its own. What existed was a working set of session notes and
design notes — accurate, detailed, and organised by the order in which the
engine was built rather than by anything a reader needs.

Two questions had to be answered together. What structure should the prose
have; and should the engine's own documentation be built by the engine.

Decision
--------

**Structure: Diátaxis at the top level.** ``tutorials/``, ``howto/``,
``reference/`` and ``explanation/``, each with its own index, every page
assigned to a quadrant before it is written. Inside ``explanation/``, the
architecture record is an **arc42-lite** page set — introduction, context,
solution strategy, building blocks, cross-cutting concepts — with C4-style
diagrams generated from source rather than drawn. Rationale and history live in
ADRs; architecture pages state current facts only.

**Topology: two documents, and the engine builds them itself.** A ``manual``
carrying the Diátaxis tree, and an ``api`` document carrying generated
reference — autodoc over every Python module, and CMake reference extracted
from the ``.cmake`` sources themselves. They are declared in a
``documents.yaml`` registry and built through ``add_docs_from_registry()``,
exactly as any consumer's set is.

The split between them is by **kind of reference, not by subject**: the
consumer contract, the registry schema, the directives an author writes and the
command-line tools are task-facing reference and belong to the manual;
signatures and module-level documentation are implementation reference and
belong to the API document. Nothing is written in both.

Consequences
------------

- **The engine is now its own consumer** The sample trees
  are built by no suite and have gone stale twice; this docset has an
  acceptance test that configures and builds it, so a change that breaks the
  public surface breaks a test rather than rotting quietly.
- Any awkwardness in using zdocs through its public surface is now felt
  first-hand and is a finding, not something to work around by reaching into
  the engine.
- CMake reference is extracted from bracket comments in the sources, so it
  cannot drift from the code the way a hand-maintained command list would. The
  cost is a build dependency on a CMake domain extension, and one wrinkle: the
  Sphinx source tree is a *copy*, so the ``.cmake`` files have to be copied
  into it — which the engine's own external-content mechanism does.
- The quality gate is the engine's own cross-reference check plus clean
  stage-two logs, rather than treating Sphinx warnings as errors. The two-stage
  build produces warnings in stage one by design.
- Cross-document links are absolute URLs under the registry's base URL, so
  browsing the built tree from the filesystem shows broken manual-to-API links.
  That is engine behaviour and applies to any consumer's set.
