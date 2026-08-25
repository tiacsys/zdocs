# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# zdocs — documentation engine for Zephyr projects. Single entry point.
#
# A consumer needs exactly two lines:
#
#   list(APPEND CMAKE_MODULE_PATH ${ZEPHYR_ZDOCS_MODULE_DIR}/cmake)
#   include(zdocs)
#
# and then calls the document factories (add_sphinx_target, add_doxygen_target)
# that this file brings in.
#
# Why an explicit include rather than "it works because the module is loaded":
# consumers enter the doc build directly (cmake -S doc) via
# `find_package(Zephyr COMPONENTS doc)`, which is a reduced flow — a module's own
# CMakeLists.txt is not reliably executed there. Relying on that would work in a
# full application build and mysteriously not in a doc build. One include, no
# side-effect magic.

#[==[.rst:
zdocs.cmake
============

Single entry point. A consumer includes this after adding
``${ZEPHYR_ZDOCS_MODULE_DIR}/cmake`` to ``CMAKE_MODULE_PATH``; it in turn
``include()``s ``common``, ``doxygen``, ``sphinx`` and ``registry``, which is
what brings :cmake:command:`add_sphinx_target`, :cmake:command:`add_doxygen_target`,
:cmake:command:`add_docs_from_registry` and :cmake:command:`add_doc_check` into
scope. Requires ``ZDOCS_PROJECT_BASE`` to already be set; see the consumer
configuration block below for every other ``ZDOCS_*`` variable it reads.
#]==]

include_guard(GLOBAL)

# Bumped when the interface a consumer sees changes (factory signatures, the
# registry schema, required variables) — not for internal edits. Consumers can
# gate on it;
set(ZDOCS_VERSION "0.1.0-dev")

set(ZDOCS_CMAKE_DIR ${CMAKE_CURRENT_LIST_DIR})
set(ZDOCS_BASE ${CMAKE_CURRENT_LIST_DIR}/..)
set(ZDOCS_SCRIPTS_DIR ${ZDOCS_BASE}/scripts)

# So the modules below can include() each other by bare name regardless of how
# the consumer arranged its own CMAKE_MODULE_PATH.
list(APPEND CMAKE_MODULE_PATH ${ZDOCS_CMAKE_DIR})

# -- Consumer configuration ---------------------------------------------------
#
# The whole project-specific surface, in one place. Set these before the factory
# calls. Everything here was previously hardcoded to the engine's first consumer.
#
#   ZDOCS_PROJECT_BASE       (required) the consuming repository's root. Paths
#                            under it are stripped from Doxygen output so the
#                            artifacts do not carry the build host's layout.
#   ZDOCS_WEST_TOPDIR        (optional) west workspace root — the broader
#                            fallback for sources in sibling projects.
#   ZDOCS_DOXYGEN_INC_ROOTS  (optional) the project's -I roots, so `#include`
#                            lines render as the compiler sees them. NOT assumed
#                            to be <base>/include: that is a layout convention,
#                            and a project keeping headers elsewhere got nothing
#                            from the old hardcoded value.
#   ZDOCS_PROJECT_LOGO       (optional) logo for Doxygen pages.
#   ZDOCS_DOXYGEN_EXTRA_CSS  (optional) brand stylesheets, appended after the
#                            theme so they win.
#   ZDOCS_DOC_BASE_URL       (optional) base URL the deploy tree is served under,
#                            used for absolute cross-document need links.
#   ZDOCS_SPHINX_EXTRA_ENV   (optional) extra VAR=value entries passed to every
#                            sphinx-build, for a consumer whose conf.py needs
#                            something the engine knows nothing about.
if(NOT DEFINED ZDOCS_PROJECT_BASE)
  message(
    FATAL_ERROR
    "zdocs: set ZDOCS_PROJECT_BASE to the consuming repository's root before "
    "include(zdocs). Without it, Doxygen output carries absolute build-host "
    "paths and the artifacts differ between machines."
  )
endif()

include(common)
include(doxygen)
include(sphinx)
include(registry)
