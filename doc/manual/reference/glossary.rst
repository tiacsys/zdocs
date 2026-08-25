Glossary
========

Terms used throughout this documentation, defined once here. Where a term
carries nuance, this entry is the place that carries it: other pages use
``:term:`` and let the definition live in one location.

.. glossary::
   :sorted:

   document
      One unit of documentation with its own source folder, its own build
      target and its own entry in the :term:`registry` — a manual, an API
      reference, a test report. A document is either built by zdocs or
      declared as remote; either way it is navigable and, usually,
      cross-referenceable.

   document set
      Every document declared in one registry, built together. Cross-references
      resolve within a set; the set is what the :term:`deploy tree` contains
      and what is published as a unit.

   registry
      ``documents.yaml``: the single file declaring a document set. Build
      targets, cross-reference wiring and navigation are all derived from it,
      and it is the only place a document is declared. See
      :doc:`registry-schema`.

   kind
      What sort of document a registry entry describes, and therefore how it is
      built and cross-referenced: ``sphinx``, ``doxygen``, or one of the three
      remote kinds that produce no local build.

   group
      A named section of the navigation sidebar. Every document belongs to
      exactly one, and groups are declared in the registry alongside the
      documents.

   prefix
      A document's cross-reference namespace, unique within a set. Sphinx peers
      reference it as ``:external+<prefix>:``; Doxygen symbols are reached
      through a role of the same name.

   builder
      A Sphinx output format a document is built in — ``html``, ``latex``. A
      document declares the builders it supports; each one gets its own build
      target and its own folder in the deploy tree.

   stage one
      The first of the two build passes. Produces only cross-reference indexes
      — an :term:`objects.inv` per Sphinx document, a :term:`tag file` per
      Doxygen document — and publishes nothing. Cross-document references are
      expected to be unresolvable here.

   stage two
      The second build pass. Rebuilds every document with the complete set of
      indexes available and produces the published output. A warning here means
      something real; a warning in stage one usually does not.

   deploy tree
      The build's published output, organised by builder:
      ``deploy/<builder>/<document>/``. Publishing a set is a directory sync of
      ``deploy/html/``. See :doc:`../explanation/deploy-layout`.

   base URL
      The URL the deploy tree is published under. Cross-document Sphinx links
      are absolute under it, so it is baked into every rendered page at build
      time — including PDFs, which leave the tree.

   objects.inv
      Sphinx's machine-readable index of everything a document defines. Any
      Sphinx site publishes one, which is what makes both local peers and
      remote sites cross-referenceable.

   tag file
      Doxygen's equivalent of :term:`objects.inv`. zdocs names every tag file
      it generates ``doxygen.tag``; a remote site's may be called anything, and
      is declared explicitly.

   intersphinx
      Sphinx's mechanism for resolving references into another Sphinx
      document's :term:`objects.inv`. zdocs derives one mapping entry per peer
      from the registry.

   doxylink
      The mechanism for referencing a Doxygen-documented symbol from a Sphinx
      page, resolved through the target document's :term:`tag file`.

   need
      A sphinx-needs object: a requirement, a specification, a test case, a
      result — anything typed, identified and linkable. Needs are exported per
      document and imported by peers, which is how traceability spans a set.

   need type
      The name of a class of :term:`need`. These names belong to the consuming
      project's methodology, not to zdocs: the engine works in roles and
      resolves each to the project's own name. See
      :doc:`../explanation/decisions/0009-need-type-role-mapping`.

   controlled document
      A document carrying a formal header — owner, classification, approval
      dates, version — and a transition history, managed with the ``docctl``
      tool. See :doc:`cli`.

   twister
      Zephyr's test runner. Its output directory is an input to the test-report
      directives; a build with no results present renders a "not found" node
      rather than failing.

   ztest
      Zephyr's C test framework. Annotated ztest sources are the origin of the
      whole test-documentation chain — see
      :doc:`../explanation/testmodule-and-twister`.

   consumer
      A project that uses zdocs to build its documentation. Everything a
      consumer supplies enters through the ``ZDOCS_*`` variables, the registry,
      or its own document sources.

   engine payload
      The files zdocs hands to Sphinx and Doxygen when it runs them —
      configuration, extensions, templates, theme. Split by tool into
      ``sphinx/`` and ``doxygen/``, distinct from ``doc/``, which is zdocs'
      own documentation.
