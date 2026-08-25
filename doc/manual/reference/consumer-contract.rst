The ``ZDOCS_*`` contract
========================

Every value a :term:`consumer` hands to the engine is a ``ZDOCS_``-prefixed
CMake variable. They fall into three groups, and the group matters: where and
how you set one determines whether it is even possible to override later.

- **Required, set before** ``include(zdocs)``.
- **Optional, set before** ``include(zdocs)`` — plain ``set()`` calls in your
  ``CMakeLists.txt``, read once when a document factory runs.
- **Cache options**, declared by the engine itself with ``CACHE STRING`` and
  meant to be overridden with ``-D`` on the ``cmake`` command line (or left at
  their default).

A document's ``conf.py`` never reads any of these directly. It is handed a
separate, smaller set of environment variables by ``add_sphinx_target``,
covered at the end of this page.

Required, before ``include(zdocs)``
------------------------------------

``ZDOCS_PROJECT_BASE``
   The consuming repository's root. Doxygen strips this prefix (and
   ``ZDOCS_WEST_TOPDIR``, if set) from every recorded path, so rendered output
   does not carry the build host's directory layout. Missing this is a
   configure-time ``FATAL_ERROR`` — raised twice, once by ``include(zdocs)``
   itself and again, independently, the first time
   :external+zdocs-api:cmake:command:`add_sphinx_target <command:add_sphinx_target>` runs, so the message
   still names the right cause even if a project reaches the second check
   through some path that skipped the first.

Optional, before ``include(zdocs)``
-------------------------------------

Plain variables, read once per document factory call. Passing ``-D`` for one
of these on the command line has no effect if your own ``CMakeLists.txt`` also
calls ``set()`` on it (a plain variable set in your list file shadows a cache
entry of the same name) — these are meant to be computed from your own project
layout, not toggled from outside it.

``ZDOCS_WEST_TOPDIR``
   The west workspace root, for sources that live in a sibling project rather
   than under ``ZDOCS_PROJECT_BASE`` itself. Also stripped from Doxygen output.

``ZDOCS_DOXYGEN_INC_ROOTS``
   Your project's own ``-I`` roots, so a rendered ``#include <widget.h>`` line
   matches what the compiler actually sees. Doxygen strips the *longest*
   matching prefix, so an entry here always wins over the
   ``ZDOCS_PROJECT_BASE``/``ZDOCS_WEST_TOPDIR`` fallback the engine appends
   unconditionally. There is no default derived from your layout (not even
   ``<project>/include``): a project keeping headers elsewhere gets nothing
   from a guess, so the engine does not guess.

``ZDOCS_PROJECT_LOGO``
   Path to an image, set as Doxygen's ``PROJECT_LOGO``. The only place your
   project's identity enters a Doxygen page.

``ZDOCS_DOXYGEN_EXTRA_CSS``
   A list of stylesheet paths, appended to Doxygen's
   ``HTML_EXTRA_STYLESHEET`` after the engine's own theme — so your rules win.

``ZDOCS_SPHINX_EXTRA_ENV``
   A list of ``VAR=value`` strings, spliced verbatim into every
   ``sphinx-build`` invocation's environment, for a ``conf.py`` that needs
   something the engine's own contract does not carry.

``ZDOCS_NEEDS_CONFIG``
   Path to a sphinx-needs ``needs_config.toml`` (need types, links and custom
   fields — see :doc:`registry-schema`'s ``needs:`` field and
   :doc:`directives-and-roles`). Every ``sphinx-build`` this document's
   ``add_sphinx_target`` launches gets it in the environment, and
   :external+zdocs-api:py:func:`zdocs_conf.configure` falls back to it whenever
   a document's own ``conf.py`` passes no ``needs_config=`` argument — which is
   the common case, since the methodology is normally project-scoped, not
   per-document (every document in a set is handed an import of every other's
   needs, so they all have to agree on what a need type means).

   This variable is real and load-bearing — every sample and fixture in this
   repository that uses sphinx-needs sets it — but it is not mentioned
   alongside the others in ``cmake/zdocs.cmake``'s own "Consumer configuration"
   comment block, which is an omission in the engine's own documentation, not
   in this page.

Cache options (``-D`` at configure time)
------------------------------------------

Declared with ``CACHE STRING`` in ``cmake/sphinx.cmake``, so they show up in
``CMakeCache.txt`` and in ``cmake -L``, and are the intended override surface
from outside your ``CMakeLists.txt``.

``ZDOCS_SPHINXOPTS``
   Default ``"-q -j auto"``. Passed to every ``sphinx-build`` invocation,
   stage 1 and stage 2 alike.

``ZDOCS_SPHINXOPTS_EXTRA``
   Default empty. Appended after ``ZDOCS_SPHINXOPTS``, for options you want to
   add without restating the defaults.

``ZDOCS_DOC_TAG``
   Default ``"development"``. Passed as a Sphinx tag (``-t``) on every build,
   for ``.. only:: tag`` blocks and the like.

``ZDOCS_DOC_BASE_URL``
   Default empty, meaning "use the registry's own ``base_url:``"
   (:doc:`registry-schema`). Set this to serve the same deploy tree from a
   different host than the registry assumes; :term:`base URL` is baked into
   every cross-document Sphinx link at build time, so changing it later means
   rebuilding.

``ZDOCS_TWISTER_OUT``
   Default empty. Directory holding a :term:`twister` run's own output
   (``twister.json``, ``twister_report.xml``, per-scenario ``handler.log``),
   read by the ``testreport``/``twisterinfo`` directives — see
   :doc:`../explanation/testmodule-and-twister`.

   Its wiring has a subtlety worth stating precisely, because the naive
   assumption (that an unset cache variable simply forwards as an empty
   string) is wrong. ``cmake/sphinx.cmake`` appends
   ``ZDOCS_TWISTER_OUT=<value>`` to the ``sphinx-build`` environment **only
   when the cache variable is non-empty**:

   .. code-block:: cmake

      if(NOT ZDOCS_TWISTER_OUT STREQUAL "")
        list(APPEND SPHINX_ENV ZDOCS_TWISTER_OUT=${ZDOCS_TWISTER_OUT})
      endif()

   Every other entry in that environment list is unconditional, including ones
   that default empty — ``cmake -E env VAR=`` sets ``VAR`` to an empty string
   for the child process, which would permanently clobber a value the
   *invoking* environment had set for that one ``cmake --build`` run. Leaving
   this one entry conditional is what lets a build tree configured with no
   ``-D`` at all still honour a per-invocation
   ``ZDOCS_TWISTER_OUT=... cmake --build ...`` override: with nothing appended
   by CMake, ``zdocs_conf.py`` falls through to reading the variable straight
   from the ambient environment at build time
   (``os.environ.get("ZDOCS_TWISTER_OUT", "")``), which is where the override
   actually reaches it. Set it via ``-D`` and every build applies it
   unconditionally instead, overriding any runtime environment.

   Leaving it unset entirely is a supported, ordinary state, not a degraded
   one: the two directives that read it render a short "not found" node and
   the build still succeeds — a documentation build legitimately outrunning
   its test run is normal.

``ZDOCS_LATEXOPTS``
   Default ``"-interaction=nonstopmode -halt-on-error"``. Passed to ``xelatex``
   through the ``latexmk``-generated ``latexmkrc``. Changing this is rarely
   useful; it exists mainly so the default is visible and overridable rather
   than buried in a generated file. Only read when a document declares the
   ``latex`` builder.

What a document's ``conf.py`` receives
------------------------------------------

These are not set by you. ``add_sphinx_target`` (:doc:`registry-schema` covers
what triggers it) computes them from the arguments above and the registry, and
passes them as plain environment variables to every ``sphinx-build`` it
launches. A ``conf.py`` shim reads them indirectly, by calling
:external+zdocs-api:py:func:`zdocs_conf.configure`; nothing below is meant to
be read with a bare ``os.environ[...]`` in your own code, except
``ZDOCS_CONF_DIR``, which every shim needs before it can even import
``zdocs_conf``:

.. code-block:: python

   import os, sys
   sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])
   from zdocs_conf import configure

``ZDOCS_CONF_DIR``
   Where the engine's own ``sphinx/`` directory lives — zdocs is a separate
   repository, checked out wherever the Zephyr module system put it, so no
   relative path from your tree can reach it.

``ZDOCS_DOC_ID``
   This document's registry key.

``ZDOCS_REGISTRY``
   Path to ``documents.yaml``, or empty for a standalone document with no
   cross-references — a supported configuration, not a degraded one.

``ZDOCS_DOC_BUILD_DIR``, ``ZDOCS_DOC_DEPLOY_DIR``
   The build tree and the ``deploy/`` tree.

``ZDOCS_PROJECT_BASE``, ``ZDOCS_WEST_TOPDIR``, ``ZDOCS_DOC_BASE_URL``, ``ZDOCS_NEEDS_CONFIG``
   Forwarded straight from the variables of the same name above.

``LATEX_DOC``, ``OUTPUT_DIR``
   Build-mechanics values (the ``.tex`` filename the ``latex`` builder must
   produce; the per-build output directory) that ``docrefs.py`` also reads
   directly, via :external+zdocs-api:py:func:`docrefs.build_root`.
