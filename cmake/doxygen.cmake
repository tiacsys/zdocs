# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Doxygen documentation build helper (reusable CMake module).
# Relies on add_doc_target from common.cmake, so include(common) first.

#[==[.rst:
doxygen.cmake
==============

Drives Doxygen for one document via :cmake:command:`add_doxygen_target`: the
generated-doxyfile overlay pattern (a consumer ``Doxyfile.in`` is expanded,
then the engine-owned keys — ``HTML_OUTPUT``, ``GENERATE_TAGFILE``,
``GENERATE_XML``, the theme, cross-document TAGFILES, path stripping — are
appended so Doxygen's "last value of a repeated key wins" rule makes them
authoritative), the two-stage tag-file build, and the builder-first deploy
layout (``deploy/html/<id>/``, ``deploy/xml/<id>/``) — both keyed on the
document's registry id, verbatim.
#]==]

# The engine owns its own tool discovery.
#
# This used to be the consumer's job, by accident rather than design — it worked
# only because the first consumer happened to call find_package(Doxygen) in its
# own CMakeLists. A project that did not got an EMPTY ${DOXYGEN_EXECUTABLE},
# which turned the build command into "<nothing> widget.stage1.doxyfile" and
# failed with:
#
#   gmake[2]: ./widget.stage1.doxyfile: Permission denied
#
# — the shell trying to execute the doxyfile. Nothing in that points at a missing
# Doxygen. Requiring it here makes the failure say what it is, at configure time.
find_package(Doxygen REQUIRED)

#-------------------------------------------------------------------------------
# Doxygen (standalone)
#
# add_doxygen_target(<name>
#                    [REGISTRY <documents.yaml>]
#                    [DOXYFILE_IN <path>]
#                    [DOCDIR <dir>])
#
# REGISTRY is optional: when given, the inter-doxygen TAGFILES are generated
# from that central registry (documents.yaml, via docrefs.py) and CMake is set
# to re-run when it changes. When omitted, the registry is not parsed at all and
# the document is built with no cross-document tag links.
#
# DOCDIR is optional and relocates only where the sources (Doxyfile.in,
# mainpage.md, groups.dox, ...) are READ from. Resolved relative to the
# CALLER's directory (or used as-is if given absolute). Omit it and nothing
# changes: the folder is <caller dir>/<name>/, exactly as before this
# argument existed. Every other path this function computes — the deploy
# folder deploy/html/<name>/, the doxyfile output name, the target names —
# stays keyed on <name>, never on DOCDIR. <name> IS the registry id, taken
# verbatim: this function synthesises no prefix and strips none.
#
# DOXYFILE_IN is optional and defaults to Doxyfile.in inside the (possibly
# DOCDIR-relocated) source folder above — an explicit DOXYFILE_IN always wins,
# since it names an exact file rather than a folder to look inside. Point it at
# a template owned by ANOTHER project to document that project's API from its
# own doxyfile — e.g. Zephyr's ${ZEPHYR_BASE}/doc/zephyr.doxyfile.in, which
# already declares the INPUT set, the CONFIG_* PREDEFINED list and the @alias
# vocabulary for the whole tree, and keeps them current as the tree moves.
# Vendoring a copy instead means it silently rots. Such a template is
# configured with the same variables as a local one, so it must express its
# paths through the same @VARS@ (@DOXY_OUT@ is the one that matters); anything
# it sets that this module also sets is overridden, because this module's
# settings are APPENDED to the generated doxyfile.
#[==[.rst:
.. cmake:command:: add_doxygen_target

  .. code-block:: cmake

    add_doxygen_target(<name>
                        [REGISTRY <documents.yaml>]
                        [DOXYFILE_IN <path>]
                        [DOCDIR <dir>])

  Declares one Doxygen document named ``<name>``, taken verbatim — ``<name>``
  IS the document's registry id; a consumer that wants it to carry a ``dox-``
  prefix (or any other convention) writes that into the id itself and gets it
  back unchanged in the source folder, the deploy paths and every target
  name. Requires ``find_package(Doxygen REQUIRED)``, which this module runs
  itself.

  ``REGISTRY``
     Path to ``documents.yaml``. When given, this document's inter-doxygen
     ``TAGFILES`` and its project-scoped ``doxygen_xml:`` opt-in are derived
     from it; omitted, no cross-document tag links and XML stays off.

  ``DOXYFILE_IN``
     Template to configure (``@ONLY``). Defaults to ``Doxyfile.in`` inside the
     (possibly ``DOCDIR``-relocated) source folder; pass an explicit path to
     document this project from another project's own template (e.g.
     Zephyr's ``zephyr.doxyfile.in``).

  ``DOCDIR``
     Relocates only where the sources (``Doxyfile.in``, ``mainpage.md``, ...)
     are read from; the deploy folder (``deploy/html/<name>/``) and every
     target name stay keyed on ``<name>``. See
     :cmake:command:`zdocs_resolve_docdir`.
#]==]
function(add_doxygen_target name)
  cmake_parse_arguments(ARGS "" "REGISTRY;DOXYFILE_IN;DOCDIR" "" ${ARGN})

  set(DOXY_DOC ${name})
  set(DOXY_OUT ${CMAKE_CURRENT_BINARY_DIR}/deploy/html/${DOXY_DOC})
  make_directory(${DOXY_OUT})

  # Per-document source folder (mirrors the sphinx layout): holds Doxyfile.in
  # plus this doc's own mainpage.md / groups.dox, referenced as @DOXY_SRC_DIR@.
  # Shared assets (footer, cross-doc-nav, shared groups) stay under @DOC_BASE@.
  #
  # DOCDIR only ever changes DOXY_SRC_DIR (where content is read from); DOC_BASE
  # below stays the caller's own directory regardless, and DOXY_OUT above was
  # already computed from name alone — see the function-header comment.
  zdocs_resolve_docdir(DOXY_SRC_DIR "${CMAKE_CURRENT_LIST_DIR}" "${ARGS_DOCDIR}" "${DOXY_DOC}")
  if(ARGS_DOXYFILE_IN)
    set(DOXYFILE_IN ${ARGS_DOXYFILE_IN})
  else()
    set(DOXYFILE_IN ${DOXY_SRC_DIR}/Doxyfile.in)
  endif()
  if(NOT EXISTS ${DOXYFILE_IN})
    message(FATAL_ERROR "add_doxygen_target(${name}): doxyfile template not found: ${DOXYFILE_IN}")
  endif()
  set(DOXYFILE_OUT ${CMAKE_CURRENT_BINARY_DIR}/${DOXY_DOC}.doxyfile)
  set(DOC_BASE ${CMAKE_CURRENT_LIST_DIR})

  # Inter-doxygen TAGFILES. Only computed when a REGISTRY is provided; docrefs.py
  # parses it so this stays out of CMake. Without a registry the doc has no
  # cross-document tag links. Injected into the generated doxyfile further down
  # (NOT substituted into Doxyfile.in — see the TAGFILES block below).
  set(DOXY_TAGFILES "")
  if(ARGS_REGISTRY)
    execute_process(
      COMMAND
        ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../scripts/docrefs.py tagfiles
        ${DOXY_DOC} ${CMAKE_CURRENT_BINARY_DIR}/deploy --registry ${ARGS_REGISTRY}
      OUTPUT_VARIABLE DOXY_TAGFILES
      OUTPUT_STRIP_TRAILING_WHITESPACE
      RESULT_VARIABLE tagfiles_res
    )

    if(NOT tagfiles_res EQUAL 0)
      message(
        FATAL_ERROR
        "add_doxygen_target(${name}): could not derive TAGFILES from "
        "${ARGS_REGISTRY} (docrefs.py exited ${tagfiles_res}). Continuing would "
        "silently produce a document with no cross-document links."
      )
    endif()
    # Regenerate this doxyfile when the registry changes.
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${ARGS_REGISTRY})
  endif()

  set(DOXY_XML_ENABLED FALSE)
  if(ARGS_REGISTRY)
    execute_process(
      COMMAND
        ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../scripts/docrefs.py xml-enabled
        --registry ${ARGS_REGISTRY}
      OUTPUT_VARIABLE DOXY_XML_ENABLED
      OUTPUT_STRIP_TRAILING_WHITESPACE
      RESULT_VARIABLE xml_enabled_res
    )
    if(NOT xml_enabled_res EQUAL 0)
      message(
        FATAL_ERROR
        "add_doxygen_target(${name}): could not determine the doxygen_xml: "
        "opt-in from ${ARGS_REGISTRY} (docrefs.py xml-enabled exited "
        "${xml_enabled_res})."
      )
    endif()
  endif()

  set(DOXY_XML_OUT ${CMAKE_CURRENT_BINARY_DIR}/deploy/xml/${DOXY_DOC})
  if(DOXY_XML_ENABLED)
    make_directory(${DOXY_XML_OUT})
  endif()

  configure_file(${DOXYFILE_IN} ${DOXYFILE_OUT} @ONLY)

  file(
    APPEND ${DOXYFILE_OUT}
    "\n# --- HTML_OUTPUT / GENERATE_TAGFILE (appended by zdocs/cmake/doxygen.cmake) ---\n"
    "HTML_OUTPUT            = .\n"
    "GENERATE_TAGFILE       =\n"
  )

  if(DOXY_XML_ENABLED)
    file(
      APPEND ${DOXYFILE_OUT}
      "\n# --- GENERATE_XML / XML_OUTPUT (appended by zdocs/cmake/doxygen.cmake) ---\n"
      "GENERATE_XML           = YES\n"
      "XML_OUTPUT             = ${DOXY_XML_OUT}\n"
    )
  else()
    file(
      APPEND ${DOXYFILE_OUT}
      "\n# --- GENERATE_XML (appended by zdocs/cmake/doxygen.cmake) ---\n"
      "GENERATE_XML           = NO\n"
    )
  endif()

  # -- Inter-doxygen TAGFILES (registry-driven): let this doc resolve symbols
  # documented in the other doxygen docs (e.g. testspec -> api). Appended to the
  # GENERATED doxyfile rather than substituted into each Doxyfile.in.
  if(DOXY_TAGFILES)
    file(
      APPEND ${DOXYFILE_OUT}
      "\n# --- inter-doxygen TAGFILES (appended by cmake/doxygen.cmake) ---\n"
      "TAGFILES              += ${DOXY_TAGFILES}\n"
      "EXTERNAL_GROUPS        = NO\n"
    )
  endif()

  # -- Strip the build host's absolute paths from file and directory names.
  #
  # Two variables, because doxygen renders paths through two independent ones and
  # fixing only the first leaves the leak visible in the HTML:
  #   STRIP_FROM_PATH      file and directory compound names — the tag files.
  #   STRIP_FROM_INC_PATH  the `#include <...>` lines shown on class and file
  #                        pages.
  #

  set(_zdocs_inc_roots "")
  foreach(inc_root ${ZDOCS_DOXYGEN_INC_ROOTS})
    string(APPEND _zdocs_inc_roots "${inc_root} ")
  endforeach()
  file(
    APPEND ${DOXYFILE_OUT}
    "\n# --- path stripping (appended by zdocs/cmake/doxygen.cmake) ---\n"
    "STRIP_FROM_PATH       += ${ZDOCS_PROJECT_BASE} ${ZDOCS_WEST_TOPDIR}\n"
    "STRIP_FROM_INC_PATH   += ${_zdocs_inc_roots}${ZDOCS_PROJECT_BASE} ${ZDOCS_WEST_TOPDIR}\n"
  )

  # Shared location of the vendored doxygen-awesome theme and cross-doc-nav
  # assets. Used by both the (unconditional) theme block below and the
  # (registry-gated) cross-doc-nav block further down.
  #
  set(DOC_DOXYGEN_DIR ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../doxygen)

  # -- doxygen-awesome theme. Applies to every doxygen doc, so append
  # unconditionally. Must come BEFORE the cross-doc-nav block so the stylesheet
  # order is: awesome -> sidebar-only -> sidebar-only-darkmode -> the consumer's
  # own overrides -> cross-doc-nav.css (loaded last, its overrides win).
  #
  file(
    APPEND ${DOXYFILE_OUT}
    "\n# --- doxygen-awesome theme (appended by zdocs/cmake/doxygen.cmake) ---\n"
    "GENERATE_TREEVIEW      = YES\n"
    "HTML_COLORSTYLE        = LIGHT\n"
    "HTML_STYLESHEET        =\n"
    "HTML_EXTRA_STYLESHEET  =\n"
    "HTML_EXTRA_FILES       =\n"
    "HTML_HEADER            = ${DOC_DOXYGEN_DIR}/doxygen-header.html\n"
    "HTML_EXTRA_STYLESHEET += ${DOC_DOXYGEN_DIR}/doxygen-awesome.css \\\n"
    "                         ${DOC_DOXYGEN_DIR}/doxygen-awesome-sidebar-only.css \\\n"
    "                         ${DOC_DOXYGEN_DIR}/doxygen-awesome-sidebar-only-darkmode-toggle.css\n"
    "HTML_EXTRA_FILES      += ${DOC_DOXYGEN_DIR}/doxygen-awesome-darkmode-toggle.js\n"
    # zdocs' own rules, for markup our header emits that the vendored theme does
    # not know about (the #projectversion row). Engine-owned, so it loads BEFORE
    # the consumer's stylesheets and can be overridden by them. It is not
    # optional: without it the header's own elements are unstyled, and the
    # version was previously rendered twice for every consumer that did not
    # happen to ship a rule hiding the duplicate.
    "HTML_EXTRA_STYLESHEET += ${DOC_DOXYGEN_DIR}/zdocs-doxygen.css\n"
  )

  # -- Consumer branding. Optional, and the ONLY place a project's identity
  # enters a rendered page.
  #
  #   set(ZDOCS_DOXYGEN_EXTRA_CSS ${CMAKE_CURRENT_LIST_DIR}/_doxygen/my-brand.css)
  #   set(ZDOCS_PROJECT_LOGO      ${CMAKE_CURRENT_LIST_DIR}/_static/my-logo.svg)
  #
  # Appended AFTER the theme so a consumer's rules win, and before cross-doc-nav
  # so the navigation widget still overrides both.
  if(ZDOCS_PROJECT_LOGO)
    file(APPEND ${DOXYFILE_OUT} "PROJECT_LOGO           = ${ZDOCS_PROJECT_LOGO}\n")
  endif()
  foreach(extra_css ${ZDOCS_DOXYGEN_EXTRA_CSS})
    file(APPEND ${DOXYFILE_OUT} "HTML_EXTRA_STYLESHEET += ${extra_css}\n")
  endforeach()

  if(ARGS_REGISTRY)
    # Per-doc dir (nav content differs per doc — each excludes itself). The file
    # is named cross-doc-nav-links.js because HTML_EXTRA_FILES copies into html/
    # by basename, and the footer references $relpath^cross-doc-nav-links.js.
    set(DOXY_NAV_DIR ${CMAKE_CURRENT_BINARY_DIR}/${DOXY_DOC}.doxygen-nav)
    make_directory(${DOXY_NAV_DIR})
    execute_process(
      COMMAND
        ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../scripts/docrefs.py navlinks
        ${DOXY_DOC} --registry ${ARGS_REGISTRY}
      OUTPUT_FILE ${DOXY_NAV_DIR}/cross-doc-nav-links.js
      RESULT_VARIABLE nav_res
    )
    if(NOT nav_res EQUAL 0)
      message(WARNING "cross-doc nav: navlinks generation failed for ${DOXY_DOC}")
    endif()
    file(
      APPEND ${DOXYFILE_OUT}
      "\n# --- cross-document navigation (appended by cmake/doxygen.cmake) ---\n"
      "HTML_FOOTER            = ${DOC_DOXYGEN_DIR}/doxygen-footer.html\n"
      "HTML_EXTRA_STYLESHEET += ${DOC_DOXYGEN_DIR}/cross-doc-nav.css\n"
      "HTML_EXTRA_FILES      += ${DOXY_NAV_DIR}/cross-doc-nav-links.js ${DOC_DOXYGEN_DIR}/cross-doc-nav.js\n"
    )
  endif()

  # -- Stage 1: produce this doc's tag file so other doxygen docs (TAGFILES)
  # and Sphinx (doxylink) can link into it, plus the XML that a `testmodule`
  # directive parses at Sphinx PARSE time. It clears its own TAGFILES because it
  # must not depend on other docs' not-yet-built tags; stage 2 then rebuilds
  # with cross links.
  #
  set(DOXYFILE_STAGE1 ${CMAKE_CURRENT_BINARY_DIR}/${DOXY_DOC}.stage1.doxyfile)
  file(
    WRITE ${DOXYFILE_STAGE1}
    "@INCLUDE = ${DOXYFILE_OUT}\n"
    "TAGFILES =\n"
    "GENERATE_TAGFILE = ${DOXY_OUT}/doxygen.tag\n"
    "GENERATE_HTML = NO\n"
    "GENERATE_LATEX = NO\n"
    "GENERATE_MAN = NO\n"
    "GENERATE_RTF = NO\n"
    "GENERATE_DOCBOOK = NO\n"
  )

  # Doxygen is invoked through run_doxygen.cmake (a `cmake -P` wrapper) so a
  # git-derived PROJECT_NUMBER (the visible version) is recomputed at BUILD time
  # on every run. The wrapper writes an @INCLUDE
  # overlay next to the given doxyfile that overrides PROJECT_NUMBER. Only when a
  # REGISTRY is available (it carries version_scope/version_project); otherwise
  # doxygen is invoked directly with no version override.
  set(DOX_VERSION_WRAPPER ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/run_doxygen.cmake)
  set(DOCREFS_PY ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../scripts/docrefs.py)
  if(ARGS_REGISTRY)
    set(
      DOX_STAGE1_CMD
      ${CMAKE_COMMAND}
      -DPYTHON=${PYTHON_EXECUTABLE}
      -DDOCREFS=${DOCREFS_PY}
      -DREGISTRY=${ARGS_REGISTRY}
      -DDOC_ID=${DOXY_DOC}
      -DREPO_ROOT=${ZDOCS_PROJECT_BASE}
      -DWEST=${ZDOCS_WEST_TOPDIR}
      -DDOXYGEN=${DOXYGEN_EXECUTABLE}
      -DDOXYFILE=${DOXYFILE_STAGE1}
      -P
      ${DOX_VERSION_WRAPPER}
    )
    set(
      DOX_STAGE2_CMD
      ${CMAKE_COMMAND}
      -DPYTHON=${PYTHON_EXECUTABLE}
      -DDOCREFS=${DOCREFS_PY}
      -DREGISTRY=${ARGS_REGISTRY}
      -DDOC_ID=${DOXY_DOC}
      -DREPO_ROOT=${ZDOCS_PROJECT_BASE}
      -DWEST=${ZDOCS_WEST_TOPDIR}
      -DDOXYGEN=${DOXYGEN_EXECUTABLE}
      -DDOXYFILE=${DOXYFILE_OUT}
      -P
      ${DOX_VERSION_WRAPPER}
    )
  else()
    set(DOX_STAGE1_CMD ${DOXYGEN_EXECUTABLE} ${DOXYFILE_STAGE1})
    set(DOX_STAGE2_CMD ${DOXYGEN_EXECUTABLE} ${DOXYFILE_OUT})
  endif()

  add_custom_target(
    ${DOXY_DOC}-tag
    COMMAND ${DOX_STAGE1_CMD}
    COMMENT "Doxygen tag (stage 1) for ${DOXY_DOC}..."
  )
  # doc-tags (stage 0) additionally gates every Sphinx stage-1 index build, so a
  # doxylink role or a testmodule directive always parses with this tag file (and
  # XML) present — see the doc-tags comment in common.cmake.
  add_dependencies(doc-tags ${DOXY_DOC}-tag)
  add_dependencies(doc-index ${DOXY_DOC}-tag)

  add_doc_target(${DOXY_DOC} COMMAND ${DOX_STAGE2_CMD} COMMENT "Running Doxygen for ${DOXY_DOC}...")

  # Stage 2 waits for all stage-1 tags so TAGFILES cross references resolve.
  add_dependencies(${DOXY_DOC} doc-index)

  # The (cross-linked) doxygen deliverable joins the full 'all-docs' build.
  add_dependencies(all-docs ${DOXY_DOC})

  set_target_properties(${DOXY_DOC} PROPERTIES ADDITIONAL_CLEAN_FILES "${DOXY_OUT};${DOXY_XML_OUT}")

  # Per-document clean: remove the deploy output(s) and the generated
  # doxyfiles.
  #
  add_custom_target(
    ${DOXY_DOC}-clean
    COMMAND
      ${CMAKE_COMMAND} -E rm -rf ${DOXY_OUT} ${DOXY_XML_OUT} ${DOXYFILE_OUT} ${DOXYFILE_STAGE1}
    COMMENT "Cleaning doxygen ${DOXY_DOC}..."
  )
  add_dependencies(clean-docs ${DOXY_DOC}-clean)
endfunction()
