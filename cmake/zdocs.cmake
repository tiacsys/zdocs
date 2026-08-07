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

include_guard(GLOBAL)

# Bumped when the interface a consumer sees changes (factory signatures, the
# registry schema, required variables) — not for internal edits. Consumers can
# gate on it; the acceptance suite asserts it is non-empty, which is what proves
# this file was actually reached.
set(ZDOCS_VERSION "0.1.0-dev")

set(ZDOCS_CMAKE_DIR ${CMAKE_CURRENT_LIST_DIR})
set(ZDOCS_BASE ${CMAKE_CURRENT_LIST_DIR}/..)
set(ZDOCS_SCRIPTS_DIR ${ZDOCS_BASE}/scripts)
set(ZDOCS_DOC_DIR ${ZDOCS_BASE}/doc)

# So the modules below can include() each other by bare name regardless of how
# the consumer arranged its own CMAKE_MODULE_PATH.
list(APPEND CMAKE_MODULE_PATH ${ZDOCS_CMAKE_DIR})

# -- Engine modules -----------------------------------------------------------
#
# Migrated one step at a time; see zdocs-tests/README.md for the ladder. Each
# include() below is added by the step whose acceptance test needs it, never
# ahead of one — an engine module with no test exercising it is exactly the
# "documented but not wired in" state this extraction exists to get out of.
#
#   include(common)     # aggregates + add_doc_target
#   include(doxygen)    # add_doxygen_target        (step 1)
#   include(sphinx)     # add_sphinx_target         (step 5)
