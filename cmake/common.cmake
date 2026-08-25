# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Common documentation build helpers (reusable CMake module).
# Shared by sphinx.cmake and doxygen.cmake — include(common) first.

#[==[.rst:
common.cmake
=============

Shared helpers used by every other zdocs CMake module: ``add_doc_target``
(the internal ``<name>``/``<name>-nodeps`` target-pair helper),
:cmake:command:`zdocs_resolve_docdir` (the ``DOCDIR`` resolution rule
``add_sphinx_target``/``add_doxygen_target`` share), the build-stage aggregate
targets (``doc-tags``, ``doc-index``, ``all-docs``, ``clean-docs``) every
document factory contributes to, and :cmake:command:`add_doc_check`, the
cross-reference integrity gate.
#]==]

# Create a custom doc target.
#
# This function has the same signature as `add_custom_target()`
#
# The function will create two targets for the doc build system.
# - Target 1 named: `<name>`
# - Target 2 named: `<name>-nodeps`
#
# Both targets will produce same result, but target 2 must have no dependencies.
# This is useful to, e.g. re-run the Sphinx build without dependencies such as
# devicetree generator.
#
function(add_doc_target name)
  add_custom_target(${name} ${ARGN})
  add_custom_target(${name}-nodeps ${ARGN})
  message(STATUS "Created doc target: ${name} and ${name}-nodeps")
endfunction()

#-------------------------------------------------------------------------------
# Shared DOCDIR resolution for add_sphinx_target / add_doxygen_target.
#
# DOCDIR decouples a document's source-content folder from its target name.
# Without it (docdir empty), the result is exactly ${caller_dir}/${default_subdir}
# — the pre-DOCDIR default, unchanged, so a consumer that never passes DOCDIR
# sees no behaviour change at all.
#
# With it, DOCDIR is resolved against ${caller_dir}, which each factory passes
# its own CMAKE_CURRENT_LIST_DIR — the CALLER's directory, not the engine's
# (see the "engine paths vs consumer paths" rule: DOCDIR is a consumer path,
# so it is never resolved against CMAKE_CURRENT_FUNCTION_LIST_DIR). An absolute
# DOCDIR is used as-is.
#
# IS_ABSOLUTE is checked explicitly rather than always pasting
# "${caller_dir}/${docdir}" together: on POSIX the doubled slash an absolute
# DOCDIR would produce still resolves, but that is an accident of this
# platform, not a guarantee, and the same string would look absurd the moment
# it is echoed back in a FATAL_ERROR naming the resolved path.
#
# Tested with STREQUAL "" rather than the shorter `if(docdir)`, which asks
# whether the value is TRUE, not whether it was given. CMake reads "0", "OFF",
# "NO", "FALSE" and anything ending in "-NOTFOUND" as false, so the short form
# silently falls back to the default for a folder literally named `off` — and,
# far more plausibly, for `DOCDIR ${MY_DOCS}` where MY_DOCS came back from a
# failed find_path as `MY_DOCS-NOTFOUND`. That would build the wrong document
# and say nothing, which is the failure mode this engine keeps being bitten by.
#[==[.rst:
.. cmake:command:: zdocs_resolve_docdir

  .. code-block:: cmake

    zdocs_resolve_docdir(<out_var> <caller_dir> <docdir> <default_subdir>)

  Shared ``DOCDIR`` resolution for :cmake:command:`add_sphinx_target` and
  :cmake:command:`add_doxygen_target`. Sets ``<out_var>`` in the caller's scope
  (``PARENT_SCOPE``) to:

  - ``<caller_dir>/<default_subdir>`` when ``<docdir>`` is the empty string —
    the pre-``DOCDIR`` default, so a caller that never passes one sees no
    behaviour change.
  - ``<docdir>`` itself, unchanged, when it is already absolute
    (``IS_ABSOLUTE``).
  - ``<caller_dir>/<docdir>`` otherwise.

  Tested with ``STREQUAL ""`` rather than ``if(docdir)``, deliberately: CMake
  reads ``"0"``, ``"OFF"``, ``"NO"``, ``"FALSE"`` and anything ending in
  ``-NOTFOUND`` as false, so the short form would silently fall back to the
  default for a folder literally named ``off``, or for a ``docdir`` that came
  back from a failed ``find_path`` as ``..-NOTFOUND``.
#]==]
function(zdocs_resolve_docdir out_var caller_dir docdir default_subdir)
  if(NOT docdir STREQUAL "")
    if(IS_ABSOLUTE "${docdir}")
      set(${out_var} "${docdir}" PARENT_SCOPE)
    else()
      set(${out_var} "${caller_dir}/${docdir}" PARENT_SCOPE)
    endif()
  else()
    set(${out_var} "${caller_dir}/${default_subdir}" PARENT_SCOPE)
  endif()
endfunction()

#-------------------------------------------------------------------------------
# Aggregate targets that the add_sphinx_target / add_doxygen_target factories
# populate (via add_dependencies). They are created here — before those modules
# and any factory call — so the factories are self-contained: a consumer only
# needs to include(common) first.

# Stage-0 aggregate: every Doxygen document's tag file (and, as a side effect of
# the same full stage-1 doxygen run, its XML). Sphinx stage-1 index builds depend
# on this:
#   * the `doxylink` roles resolve at parse time and bake either a link or plain
#     text into the doctree, depending on whether the tag file existed when the
#     role was created (at builder-inited);
#   * the `testmodule` directive parses the testspec Doxygen XML outright.
add_custom_target(doc-tags)

# Stage-1 aggregate: every document's cross-reference index (Sphinx objects.inv
# / needs.json, Doxygen tag files). Each stage-2 (html/doxygen) target depends
# on this, so all indexes exist before any document is rendered and cross
# references resolve.
add_custom_target(doc-index)

# Stage-2 aggregate: builds the whole documentation set. Marked ALL so it is the
# default target (plain `make` / `cmake --build .` builds everything). Each
# add_sphinx_target (html builder) and add_doxygen_target appends itself, so
# this stays in sync automatically.
add_custom_target(all-docs ALL)

# Clean aggregate: remove every document's generated artifacts (see the *-clean
# targets appended by the factories). Does NOT touch configure-time state
# (e.g. the sphinx-git .git pointer), so a rebuild needs no reconfigure.
add_custom_target(clean-docs)

#-------------------------------------------------------------------------------
# Post-build integrity checks (scripts/doccheck.py).
#
# add_doc_check(REGISTRY <documents.yaml>)
#
# Wired as a POST_BUILD step of `all-docs`, so a full build FAILS on a broken
# cross-reference instead of publishing one. Also available on its own as the
# `doc-check` target, to re-check an existing deploy tree without rebuilding it.
#[==[.rst:
.. cmake:command:: add_doc_check

  .. code-block:: cmake

    add_doc_check(REGISTRY <documents.yaml>)

  Wires ``scripts/doccheck.py`` — the cross-reference integrity gate — as a
  standalone ``doc-check`` target AND as a ``POST_BUILD`` step of ``all-docs``,
  so an ordinary build already runs it. ``REGISTRY`` is the only argument, and
  is required; the checks read the built ``deploy/`` tree, which the engine
  locates itself.

  Catches the failure mode this engine is prone to: a cross-reference that
  breaks WITHOUT breaking the build — a removed document leaving a reference
  that quietly degrades to plain text, or a parse-time role whose peer
  inventory was not ready emitting nothing at all.
#]==]
function(add_doc_check)
  cmake_parse_arguments(ARGS "" "REGISTRY" "" ${ARGN})

  if(NOT ARGS_REGISTRY)
    message(FATAL_ERROR "add_doc_check() requires REGISTRY <documents.yaml>.")
  endif()

  set(
    doccheck_cmd
    ${PYTHON_EXECUTABLE}
    ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../scripts/doccheck.py
    --registry
    ${ARGS_REGISTRY}
    --deploy
    ${CMAKE_CURRENT_BINARY_DIR}/deploy
  )

  add_custom_target(
    doc-check
    COMMAND ${doccheck_cmd}
    COMMENT "Checking cross-document reference integrity..."
    USES_TERMINAL
  )
  add_custom_command(
    TARGET all-docs
    POST_BUILD
    COMMAND ${doccheck_cmd}
    COMMENT "Checking cross-document reference integrity..."
    USES_TERMINAL
  )
endfunction()
