# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Build-time download wrapper for a `kind: doxygen-external` document's
# `remote-tagfile:` — invoked as `cmake -P download_external_tag.cmake` from
# an `<id>-tag` custom target in registry.cmake, mirroring how
# run_doxygen.cmake is invoked as a `cmake -P` wrapper for the identical
# reason: the fetch must happen at BUILD time (recomputed/refetched fresh on
# every run), not baked in as a configure-time side effect of reading the
# registry.
#
# Required -D arguments:
#   URL   the remote-tagfile: url to download (may be file:// in tests)
#   DEST  local destination path (always named doxygen.tag by convention,
#         regardless of the remote's own filename — see docrefs.py's
#         tagfiles()/load() for why)

#[==[.rst:
download_external_tag.cmake
=============================

Internal ``cmake -P`` wrapper, invoked as the ``COMMAND`` of an
``<id>-tag`` custom target created by :cmake:command:`add_docs_from_registry`
for a ``kind: doxygen-external`` document. Downloads ``-DURL=<remote-tagfile>``
to ``-DDEST=<local path>`` (``file(DOWNLOAD ...)``) at BUILD time, so the fetch
is refreshed on every run rather than baked in as a configure-time side
effect. No public commands — the two ``-D`` arguments above are its whole
interface, exercised only through the registry dispatcher.
#]==]

foreach(var URL DEST)
  if(NOT DEFINED ${var})
    message(FATAL_ERROR "download_external_tag.cmake: missing required -D${var}")
  endif()
endforeach()

get_filename_component(_dest_dir "${DEST}" DIRECTORY)
file(MAKE_DIRECTORY "${_dest_dir}")

file(DOWNLOAD "${URL}" "${DEST}" STATUS _status LOG _log)

list(GET _status 0 _status_code)
list(GET _status 1 _status_message)
if(NOT _status_code EQUAL 0)
  # Fail loudly, never trust the exit code alone: surface the ACTUAL
  # curl/libcurl error text (and the download log), not just "download
  # failed" — a silent/generic failure here would leave a stale or missing
  # doxygen.tag and only surface as a confusing doxylink resolution failure
  # much later, far from the real cause.
  message(
    FATAL_ERROR
    "download_external_tag.cmake: failed to download '${URL}' to "
    "'${DEST}': ${_status_message} (status ${_status_code})\n${_log}"
  )
endif()
