# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# zdocs' own documentation set — a CONSUMER of the engine, exactly like any
# other project's doc/CMakeLists.txt (see samples/registry/CMakeLists.txt in
# the acceptance-test repo, which this file is modelled on).
#
cmake_minimum_required(VERSION 3.20.0)
project(zdocs-doc LANGUAGES)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE} .. COMPONENTS doc)

if(NOT DEFINED ZEPHYR_ZDOCS_MODULE_DIR)
  message(
    FATAL_ERROR
    "zdocs module not found. Pass it with:\n"
    "  -DEXTRA_ZEPHYR_MODULES=<path to tools/zdocs>\n"
    "NOTE: the variable is EXTRA_ZEPHYR_MODULES, not EXTRA_MODULES — the latter "
    "is silently ignored by the Zephyr module system."
  )
endif()
message(STATUS "zdocs module: ${ZEPHYR_ZDOCS_MODULE_DIR}")

#-------------------------------------------------------------------------------
# The one place this docset's build description differs from an ordinary
# consumer's: ZDOCS_PROJECT_BASE is the ENGINE's OWN root, because here the
# engine itself is the consuming repository (this docset documents zdocs, not
# a project that merely depends on it).
get_filename_component(ZDOCS_ENGINE_ROOT ${CMAKE_CURRENT_LIST_DIR}/.. ABSOLUTE)

execute_process(
  COMMAND west topdir
  OUTPUT_VARIABLE ZDOCS_DOC_WEST_TOPDIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE west_result
  ERROR_QUIET
)
if(NOT west_result EQUAL 0)
  message(FATAL_ERROR "not inside a west workspace (`west topdir` failed)")
endif()

set(ZDOCS_PROJECT_BASE ${ZDOCS_ENGINE_ROOT})
set(ZDOCS_WEST_TOPDIR ${ZDOCS_DOC_WEST_TOPDIR})
# No ZDOCS_DOXYGEN_INC_ROOTS: this docset declares no Doxygen document.

list(APPEND CMAKE_MODULE_PATH ${ZEPHYR_ZDOCS_MODULE_DIR}/cmake)
include(zdocs)

message(STATUS "zdocs version: ${ZDOCS_VERSION}")

set(DOC_REGISTRY ${CMAKE_CURRENT_LIST_DIR}/documents.yaml)

add_docs_from_registry(REGISTRY ${DOC_REGISTRY})
add_doc_check(REGISTRY ${DOC_REGISTRY})
