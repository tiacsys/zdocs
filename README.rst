zdocs
=====

zdocs is a documentation engine shipped as a `Zephyr module
<https://docs.zephyrproject.org/latest/develop/modules.html>`_. A project
declares its documents in one registry file (``documents.yaml``), sets a
handful of ``ZDOCS_*`` CMake variables, and gets a build that drives Sphinx
and Doxygen together, resolves cross-references between every document in the
set in both directions, and produces a ``deploy/`` tree that is published by
copying one folder.

**Pre-release**: the registry schema and the ``ZDOCS_*`` contract may still
change without a deprecation period.

What it does
------------

- **Two toolchains, one set.** Sphinx and Doxygen documents are peers: they
  share a navigation sidebar, cross-reference each other in both directions,
  and resolve version numbers by the same rules.
- **Circular cross-references resolve**, via a two-stage build — every
  document's index is produced before anything is rendered against it.
- **One declaration per document.** Build targets, intersphinx mappings, tag
  file lists, navigation and needs imports are all derived from the registry.
- **Remote documents are first-class**: an upstream Sphinx or Doxygen site can
  be cross-referenced without being built locally.
- **Requirements and tests.** sphinx-needs traceability, test specifications
  rendered from annotated ztest sources, and test reports correlated from
  Twister output — under the project's own vocabulary, not the engine's.
- **Publishable and checkable.** Output is organised by builder, and an
  integrity gate fails a build whose cross-references have silently degraded to
  plain text.

Taking zdocs as a consumer
--------------------------

Add it to your `west manifest
<https://docs.zephyrproject.org/latest/develop/west/manifest.html>`_ as a
project, or point ``EXTRA_ZEPHYR_MODULES`` at a local checkout, then in your
own ``doc/CMakeLists.txt``::

    find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE} .. COMPONENTS doc)

    set(ZDOCS_PROJECT_BASE ${CMAKE_CURRENT_LIST_DIR}/..)   # your repo's root

    list(APPEND CMAKE_MODULE_PATH ${ZEPHYR_ZDOCS_MODULE_DIR}/cmake)
    include(zdocs)

    add_docs_from_registry(REGISTRY ${CMAKE_CURRENT_LIST_DIR}/documents.yaml)
    add_doc_check(REGISTRY ${CMAKE_CURRENT_LIST_DIR}/documents.yaml)

``EXTRA_ZEPHYR_MODULES``, not ``EXTRA_MODULES`` — the latter is silently
ignored by the Zephyr module system.

Repository layout
-----------------

===============  ==============================================================
``cmake/``       the consumer-facing CMake surface, and the document factories
``scripts/``     the registry reader, the integrity gate, the ``docctl`` tool
``sphinx/``      Sphinx payload: shared configuration, extensions, templates
``doxygen/``     Doxygen payload: theme, header/footer, cross-document nav
``doc/``         zdocs' own documentation — a consumer of zdocs itself
===============  ==============================================================

Building zdocs' own documentation
---------------------------------

This repository's own documentation set lives in ``doc/`` and is built through
the exact same public surface — a real consumer, not a fixture::

    $ pip install -r doc/requirements.txt
    $ cmake -S doc -B <build> -DEXTRA_ZEPHYR_MODULES=$PWD
    $ cmake --build <build>

The output lands at ``<build>/deploy/html/manual/index.html`` (task-facing:
tutorials, how-to guides, reference and explanation, organised by Diátaxis) and
``<build>/deploy/html/api/index.html`` (generated Python and CMake
implementation reference). Start at the manual; see
``doc/manual/howto/build-these-docs.rst`` for the full recipe, including the
non-Python ``dot`` (Graphviz) dependency the architecture diagrams need.

Tests
-----

Two suites, in two repositories. The engine's own unit suite covers the
pure-Python extensions and runs in about a second::

    $ python3 -m pytest sphinx/_extensions/_tests -q

The acceptance suite lives in a separate project that consumes zdocs the way a
real one does, builds real documentation with real tools, and asserts on
rendered output.

Out of scope here
-----------------

This file is the front door — what zdocs is, how to take it, where its docs
live. It does not restate the manual.
