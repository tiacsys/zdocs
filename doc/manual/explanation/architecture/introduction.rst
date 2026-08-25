Introduction and goals
======================

zdocs is a **documentation engine shipped as a Zephyr module**. A consuming
project declares its documents in one registry file, sets a handful of
variables, and gets a build that drives Sphinx and Doxygen together, resolves
cross-references between every document in the set in both directions, and
produces a deploy tree that can be published by copying one folder.

What it is for
--------------

The problem zdocs exists to solve is not "render a document". Both toolchains
already do that. It is everything around a *set* of documents:

- A Sphinx document must be able to reference a symbol documented by a Doxygen
  document, and a Doxygen page must be able to link back into the prose.
- Two Sphinx documents must be able to reference each other's sections and
  each other's requirements, which means each has to be built before the other
  can resolve against it — in both directions.
- Every document needs the same navigation, the same branding and the same
  version-resolution rules, without each one restating them.
- The result has to be publishable as a directory, and checkable: a set whose
  cross-references have silently degraded to plain text looks completely
  normal.

Quality goals
-------------

In priority order, and each of them has cost the project something to learn:

**Correct cross-references, or a loud failure.**
   The engine's worst failure mode is not a broken build; it is a
   complete-looking documentation set with dead links, produced with a clean
   exit. Machinery that produces that is worse than machinery that stops.

**A consumer's vocabulary is the consumer's.**
   Document ids, group names, need types, link names, prefixes, classification
   vocabulary and version scopes belong to the project, not to the engine. The
   engine ships defaults, never constants — see
   :doc:`../decisions/0009-need-type-role-mapping`.

**Declared once.**
   Anything derivable from the registry is derived from it, rather than
   restated by a consumer in CMake — see
   :doc:`../decisions/0004-registry-as-single-source-of-truth`.

**Tested the way it is used.**
   The primary test layer builds real documentation with real tools and asserts
   on rendered output, because every defect this engine has had was an
   interaction between parts that were individually correct.

Stakeholders
------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Who
     - What they need from zdocs
   * - Document author
     - Directives and roles that resolve; a build that says what is wrong.
   * - Project integrator
     - One registry file and a short list of variables; no engine internals.
   * - Firmware developer
     - Annotated C turning into rendered API and test documentation without
       hand-written duplicates.
   * - Quality/QMS owner
     - Controlled-document headers, requirement traceability, and evidence that
       a published set's references are intact.
   * - Engine maintainer
     - A test suite that fails when a consumer would have been broken.
