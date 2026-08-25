# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Build-time doxygen wrapper: compute a git-derived version and run doxygen.
#
# Invoked as `cmake -P run_doxygen.cmake` from a custom target in doxygen.cmake,
# so the version is recomputed on every build (drift-safe) rather than baked in
# at configure time.
#
# Required -D arguments:
#   PYTHON    python interpreter
#   DOCREFS   path to scripts/docrefs.py
#   REGISTRY  path to documents.yaml
#   DOC_ID    registry id of this document, taken verbatim (e.g. widget, or
#             dox-api for a consumer that chooses to write the prefix itself)
#   REPO_ROOT the consumer project's git root (for version_scope)
#   WEST      west workspace topdir (for version_project)
#   DOXYGEN   doxygen executable
#   DOXYFILE  the base doxyfile to build (an @INCLUDE overlay is written next
#             to it that overrides PROJECT_NUMBER with the computed version)

#[==[.rst:
run_doxygen.cmake
==================

Internal ``cmake -P`` wrapper invoked by :cmake:command:`add_doxygen_target`'s
two doxygen custom targets (stage 1's tag build and stage 2's full build), so
that the git-derived ``PROJECT_NUMBER`` is recomputed at BUILD time on every
run rather than baked in at configure time. Computes the version via
``docrefs.py version``, writes a thin ``@INCLUDE`` overlay next to the given
doxyfile that overrides ``PROJECT_NUMBER``, then runs Doxygen on the overlay.
No public commands — its whole interface is the ``-D`` arguments above,
exercised only through :cmake:command:`add_doxygen_target`.
#]==]

foreach(
  var
  PYTHON
  DOCREFS
  REGISTRY
  DOC_ID
  REPO_ROOT
  WEST
  DOXYGEN
  DOXYFILE
)
  if(NOT DEFINED ${var})
    message(FATAL_ERROR "run_doxygen.cmake: missing required -D${var}")
  endif()
endforeach()

# 1. Compute the version via the shared docrefs `version` CLI.
execute_process(
  COMMAND
    ${PYTHON} ${DOCREFS} version ${DOC_ID} --registry ${REGISTRY} --repo-root ${REPO_ROOT} --west
    ${WEST}
  OUTPUT_VARIABLE VER
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE ver_res
)
if(NOT ver_res EQUAL 0 OR VER STREQUAL "")
  set(VER "v0.0-dev")
endif()

# 2. Write a thin overlay doxyfile that includes the base and overrides the
#    visible version (overrides the base PROJECT_NUMBER regardless of its value).
set(OVERLAY "${DOXYFILE}.version")
file(WRITE ${OVERLAY} "@INCLUDE = ${DOXYFILE}\n" "PROJECT_NUMBER = \"${VER}\"\n")

# 3. Run doxygen on the overlay.
execute_process(COMMAND ${DOXYGEN} ${OVERLAY} RESULT_VARIABLE dox_res)
if(NOT dox_res EQUAL 0)
  message(FATAL_ERROR "run_doxygen.cmake: doxygen failed for ${DOC_ID} (version ${VER})")
endif()
