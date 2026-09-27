# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Build-time gate over a Doxygen warning log.
#
# Invoked as `cmake -P check_doxygen_warnings.cmake` right after stage 2's
# Doxygen run, from the same custom target in doxygen.cmake.
#
# Required -D arguments:
#   DOC_ID    registry id of the document, for the messages
#   LOGFILE   the WARN_LOGFILE stage 2 wrote
#   PATTERNS  ;-separated regular expressions; a log line matching any of them
#             fails the build. Empty: the log is echoed and nothing fails.

#[==[.rst:
check_doxygen_warnings.cmake
============================

Internal ``cmake -P`` gate run after :cmake:command:`add_doxygen_target`'s
stage-2 Doxygen build. Stage 2 writes its warnings to a log file instead of the
console; this script echoes that log, so the console shows what it always did,
then fails the target if any line matches one of
``ZDOCS_DOXYGEN_WARN_FAIL_PATTERNS``.

Stage 2 only, deliberately. Stage 1 runs with ``TAGFILES`` cleared, so every
reference into a peer document — including every ``\verifies`` and
``\satisfies`` against another project's ``\requirement`` — warns there
falsely; stage 1 is therefore silenced and never gated.

The gate exists because the Doxygen XML cannot tell a real requirement link
from a typo: Doxygen synthesizes ``<requirement refid="requirement_<UID>">``
from the UID string whether or not any ``\requirement`` defines it. Its warning
is the only signal.
#]==]

foreach(var DOC_ID LOGFILE)
  if(NOT DEFINED ${var})
    message(FATAL_ERROR "check_doxygen_warnings.cmake: missing required -D${var}")
  endif()
endforeach()

# Doxygen writes the log even when there is nothing to say; a missing one means
# it never ran this configuration, and doxygen's own failure is reported by
# whichever command ran it.
if(NOT EXISTS ${LOGFILE})
  return()
endif()

file(READ ${LOGFILE} log)
if(NOT log STREQUAL "")
  # To stderr, like doxygen itself; NOTICE adds no prefix and no call stack.
  string(REGEX REPLACE "\n$" "" log "${log}")
  message(NOTICE "${log}")
endif()

if("${PATTERNS}" STREQUAL "")
  return()
endif()

string(REPLACE ";" "|" regex "${PATTERNS}")
file(STRINGS ${LOGFILE} hits REGEX "${regex}")
if(hits)
  list(LENGTH hits count)
  list(JOIN hits "\n  " listing)
  message(
    FATAL_ERROR
    "${DOC_ID}: ${count} Doxygen warning(s) match ZDOCS_DOXYGEN_WARN_FAIL_PATTERNS:\n"
    "  ${listing}\n"
    "Full log: ${LOGFILE}"
  )
endif()
