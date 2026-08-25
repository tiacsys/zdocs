# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Sphinx documentation build helper (reusable CMake module).
# Relies on add_doc_target from common.cmake, so include(common) first.

#[==[.rst:
sphinx.cmake
=============

Drives Sphinx for one document via :cmake:command:`add_sphinx_target`: a
two-stage build (a ``xref``-builder cross-reference index pass, then one pass
per requested builder), the sphinx-git ``.git`` pointer for the copied source
tree, and the builder-first deploy layout (``deploy/<builder>/<doc>/``).
#]==]

find_program(SPHINXBUILD sphinx-build)
if(NOT SPHINXBUILD)
  message(
    FATAL_ERROR
    "zdocs: the 'sphinx-build' command was not found. Install the documentation "
    "requirements (see zdocs/sphinx/requirements-doc.txt)."
  )
endif()
find_program(SPHINXAUTOBUILD sphinx-autobuild)
find_program(LATEXMK latexmk)
find_package(Git)

set(
  ZDOCS_LATEXOPTS
  "-interaction=nonstopmode -halt-on-error"
  CACHE STRING
  "Options passed to the LaTeX engine by latexmk"
)

set(ZDOCS_SPHINXOPTS "-q -j auto" CACHE STRING "Default Sphinx options")
set(ZDOCS_SPHINXOPTS_EXTRA "" CACHE STRING "Extra Sphinx options (added to the defaults)")
set(ZDOCS_DOC_TAG "development" CACHE STRING "Sphinx tag describing the release stage")
set(
  ZDOCS_DOC_BASE_URL
  ""
  CACHE STRING
  "Base URL the deploy tree is served under (overrides documents.yaml base_url)"
)
set(
  ZDOCS_TWISTER_OUT
  ""
  CACHE STRING
  "Directory holding twister's own output (twister.json, twister_report.xml, per-scenario handler.log) for the testreport/twisterinfo directives"
)
separate_arguments(ZDOCS_SPHINXOPTS)
separate_arguments(ZDOCS_SPHINXOPTS_EXTRA)

#-------------------------------------------------------------------------------
# sphinx-git support
#
# The Sphinx docs are built from RST that the `external_content` extension copies
# into <build>/<doc>/src, which is not itself a git repository. The sphinx-git
# extension resolves history via
#   Repo(env.srcdir, search_parent_directories=True)
# and, because it always passes an explicit path, GitPython IGNORES the GIT_DIR
# environment variable (`epath = path or os.getenv("GIT_DIR")`). An env var
# therefore cannot help; instead we drop a `.git` gitfile pointer that redirects
# to the origin repository's git dir.
#
# The pointer is written to <build>/<doc>/.git — the PARENT of the Sphinx srcdir,
# not srcdir itself: external_content deletes any file under srcdir it did not
# copy (its cleanup glob matches dotfiles too).
#
function(write_sphinx_gitdir_pointer src_dir out_dir)
  if(NOT Git_FOUND)
    return()
  endif()
  execute_process(
    COMMAND ${GIT_EXECUTABLE} -C ${src_dir} rev-parse --absolute-git-dir
    OUTPUT_VARIABLE git_dir
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE git_res
    ERROR_QUIET
  )
  if(NOT git_res EQUAL 0 OR git_dir STREQUAL "")
    message(STATUS "sphinx-git: '${src_dir}' is not in a git repo; skipping .git pointer")
    return()
  endif()
  file(WRITE "${out_dir}/.git" "gitdir: ${git_dir}\n")
endfunction()

#-------------------------------------------------------------------------------
# Sphinx
#
# add_sphinx_target(<doc_name>
#                   BUILDERS <b1> [<b2> ...]
#                   [REGISTRY <documents.yaml>]
#                   [TAGS <t1> [<t2> ...]]
#                   [DEPENDS <doc1> [<doc2> ...]]
#                   [DOCDIR <dir>])
#
# The document's sources live in <caller's dir>/<doc_name>/ and its conf.py is
# read from there; the folder name IS the document name, and the registry key,
# UNLESS DOCDIR says otherwise (see below) — but the target names, deploy path
# and registry key always stay keyed on <doc_name> regardless of DOCDIR.
#
# DOCDIR is optional and relocates only where the sources are READ from. It is
# resolved relative to the CALLER's directory (or used as-is if given
# absolute), so a consumer can group content by topic (`qms/audits`) instead of
# by document name. Omit it and nothing changes: the folder is
# <caller's dir>/<doc_name>/, exactly as before this argument existed.
#
# REGISTRY is optional and mirrors add_doxygen_target: when given, its path is
# handed to conf.py in the environment, and zdocs_conf derives this document's
# intersphinx mapping, external needs and version scope from it. Without it the
# document builds standalone with no cross-document links.
#
# DEPENDS names other documents this one actually cross-references. It orders the
# stage-1 index builds. A missing peer index during stage 1 only warns and
# self-heals in stage 2 (every stage-2 target depends on the doc-index
# aggregate), so this is about reducing transient warnings on a from-scratch
# parallel build, not about correctness. Every edge should be a real content
# dependency — do not add one "just in case".
#[==[.rst:
.. cmake:command:: add_sphinx_target

  .. code-block:: cmake

    add_sphinx_target(<doc_name>
                       BUILDERS <b1> [<b2> ...]
                       [REGISTRY <documents.yaml>]
                       [TAGS <t1> [<t2> ...]]
                       [DEPENDS <doc1> [<doc2> ...]]
                       [DOCDIR <dir>])

  Declares one Sphinx document. ``<doc_name>`` is both the target-name stem
  (``<doc_name>-<builder>``, ``<doc_name>-<builder>-nodeps``, ``<doc_name>-index``)
  and the registry key; its sources live in ``<caller dir>/<doc_name>/`` unless
  ``DOCDIR`` relocates only where they are read from.

  ``BUILDERS`` (required, non-empty)
     Sphinx builders to run, e.g. ``html`` or ``html latex``. Only the
     ``html`` builder's target joins ``all-docs``.

  ``REGISTRY``
     Path to ``documents.yaml``. When given, this document's intersphinx
     mapping, external needs and version scope are derived from it; omitted,
     the document builds standalone with no cross-document links.

  ``TAGS``
     Extra Sphinx tags (``-t``), appended after ``ZDOCS_DOC_TAG``.

  ``DEPENDS``
     Other document ids this one actually cross-references, ordering the
     stage-1 index builds to reduce transient warnings on a from-scratch
     parallel build.

  ``DOCDIR``
     Relocates where the sources are read from (resolved against the
     caller's directory, or used as-is if absolute); everything else — target
     names, deploy path, registry key — stays keyed on ``<doc_name>``. See
     :cmake:command:`zdocs_resolve_docdir`.
#]==]
function(add_sphinx_target doc_name)
  cmake_parse_arguments(ARGS "" "REGISTRY;DOCDIR" "BUILDERS;TAGS;DEPENDS" ${ARGN})

  if(NOT ARGS_BUILDERS)
    message(FATAL_ERROR "add_sphinx_target(${doc_name}) requires a BUILDERS argument.")
  endif()

  if(NOT DEFINED ZDOCS_PROJECT_BASE)
    message(FATAL_ERROR "zdocs: ZDOCS_PROJECT_BASE must be set before add_sphinx_target().")
  endif()

  # Consumer-owned paths use CMAKE_CURRENT_LIST_DIR (the CALLER's directory);
  # anything zdocs ships uses CMAKE_CURRENT_FUNCTION_LIST_DIR. See doxygen.cmake.
  #
  # DOCDIR only ever changes DOCS_CFG_DIR (where the content is READ from).
  # Everything below this line — DOC_OUT_DIR, the deploy path, the target
  # names — stays keyed on doc_name; see the function-header comment.
  set(DOC_OUT_DIR ${CMAKE_CURRENT_BINARY_DIR}/${doc_name})
  zdocs_resolve_docdir(DOCS_CFG_DIR "${CMAKE_CURRENT_LIST_DIR}" "${ARGS_DOCDIR}" "${doc_name}")
  set(DOCS_BUILD_DIR ${DOC_OUT_DIR}/build)
  set(DOCS_SRC_DIR ${DOC_OUT_DIR}/src) # generated (external_content)
  set(DOCS_DOCTREE_DIR ${DOC_OUT_DIR}/doctrees)

  if(NOT EXISTS ${DOCS_CFG_DIR}/conf.py)
    message(
      FATAL_ERROR
      "add_sphinx_target(${doc_name}): no conf.py at ${DOCS_CFG_DIR}. By "
      "default the Sphinx sources live at <caller dir>/${doc_name}/; pass "
      "DOCDIR <dir> to point this document at a different folder."
    )
  endif()

  # Stage 1 parses into its OWN doctree cache, separate from the stage-2 one.
  set(DOCS_INDEX_DOCTREE_DIR ${DOC_OUT_DIR}/doctrees-index)

  set(SPHINX_TAGS "${ZDOCS_DOC_TAG}")
  list(APPEND SPHINX_TAGS ${ARGS_TAGS})
  set(SPHINX_TAGS_ARGS "")
  foreach(tag ${SPHINX_TAGS})
    list(APPEND SPHINX_TAGS_ARGS "-t" "${tag}")
  endforeach()

  # Everything conf.py needs to know, handed over in the environment.
  #
  # ZDOCS_CONF_DIR is how a consumer's conf.py finds zdocs_conf. zdocs is a
  # separate repository, checked out wherever the Zephyr module system put it,
  # so no relative path from the consumer's tree can reach it.
  #
  # Note conf.py is read from the AUTHORED directory (`-c ${DOCS_CFG_DIR}`
  # below); only the RST is copied into ${DOCS_SRC_DIR}. A consumer's conf.py can
  # therefore use relative paths to its OWN files.
  set(
    SPHINX_ENV
    ZDOCS_CONF_DIR=${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../sphinx
    ZDOCS_DOC_BUILD_DIR=${CMAKE_CURRENT_BINARY_DIR}
    ZDOCS_DOC_DEPLOY_DIR=${CMAKE_CURRENT_BINARY_DIR}/deploy
    ZDOCS_PROJECT_BASE=${ZDOCS_PROJECT_BASE}
    ZDOCS_WEST_TOPDIR=${ZDOCS_WEST_TOPDIR}
    ZDOCS_DOC_ID=${doc_name}
    ZDOCS_REGISTRY=${ARGS_REGISTRY}
    ZDOCS_DOC_BASE_URL=${ZDOCS_DOC_BASE_URL}
    ZDOCS_NEEDS_CONFIG=${ZDOCS_NEEDS_CONFIG}
    ${ZDOCS_SPHINX_EXTRA_ENV}
  )
  if(NOT ZDOCS_TWISTER_OUT STREQUAL "")
    list(APPEND SPHINX_ENV ZDOCS_TWISTER_OUT=${ZDOCS_TWISTER_OUT})
  endif()

  if(ARGS_REGISTRY)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${ARGS_REGISTRY})
  endif()

  # sphinx-git: make the copied sources resolve to the origin repo's history.
  write_sphinx_gitdir_pointer(${DOCS_CFG_DIR} ${DOC_OUT_DIR})

  # -- Stage 1: cross-reference index only (objects.inv, and needs.json once
  # sphinx-needs is in play), no HTML. Written into the html deploy dir so stage
  # 2 and the other documents find it exactly where they look for it.
  set(index_out_dir ${CMAKE_CURRENT_BINARY_DIR}/deploy/html/${doc_name})
  add_custom_target(
    ${doc_name}-index
    COMMAND ${CMAKE_COMMAND} -E make_directory ${DOCS_SRC_DIR}
    COMMAND
      ${CMAKE_COMMAND} -E env ${SPHINX_ENV} OUTPUT_DIR=${index_out_dir} LATEX_DOC=${doc_name}.tex
      ${SPHINXBUILD} -b xref -c ${DOCS_CFG_DIR} -d ${DOCS_INDEX_DOCTREE_DIR} -w
      ${DOCS_BUILD_DIR}/xref.log ${SPHINX_TAGS_ARGS} ${ZDOCS_SPHINXOPTS} ${ZDOCS_SPHINXOPTS_EXTRA}
      ${DOCS_SRC_DIR} ${index_out_dir}
    USES_TERMINAL
    COMMENT "Sphinx xref index (stage 1) for ${doc_name}..."
  )
  # Wait for every Doxygen tag file (and XML) before PARSING: doxylink roles and
  # the testmodule directive resolve at parse time, and this stage's doctrees are
  # what stage 2 reuses. See the doc-tags comment in common.cmake.
  add_dependencies(${doc_name}-index doc-tags)
  add_dependencies(doc-index ${doc_name}-index)
  foreach(dep ${ARGS_DEPENDS})
    add_dependencies(${doc_name}-index ${dep}-index)
  endforeach()

  foreach(builder ${ARGS_BUILDERS})
    set(target_name ${doc_name}-${builder})
    if(builder STREQUAL "latex")
      set(builder_folder "pdf")
    else()
      set(builder_folder "${builder}")
    endif()
    set(builder_out_dir ${CMAKE_CURRENT_BINARY_DIR}/deploy/${builder_folder}/${doc_name})
    set(sphinx_executable ${SPHINXBUILD})
    set(extra_sphinx_args "")
    set(extra_commands "")

    # Stage-2 doctree cache, per output FORMAT rather than per builder.
    #
    # `html` and `html-live` share one: they render the same doctree and the
    # shared cache is what makes the autobuild loop fast. `latex` must NOT join
    # them, and the reason is D10's exactly:
    if(builder STREQUAL "latex")
      set(builder_doctree_dir ${DOC_OUT_DIR}/doctrees-latex)
    else()
      set(builder_doctree_dir ${DOCS_DOCTREE_DIR})
    endif()

    if(builder STREQUAL "html-live")
      if(NOT SPHINXAUTOBUILD)
        message(WARNING "sphinx-autobuild not found, skipping '${target_name}'.")
        continue()
      endif()
      set(sphinx_executable ${SPHINXAUTOBUILD})
      set(builder_arg html)
      set(extra_sphinx_args --watch ${DOCS_CFG_DIR} --ignore ${DOCS_BUILD_DIR})
    elseif(builder STREQUAL "latex")
      # The `latex` builder writes a .tex; latexmk turns it into the PDF that is
      # the actual deliverable.
      if(NOT LATEXMK)
        message(
          FATAL_ERROR
          "zdocs: add_sphinx_target(${doc_name}) requests the 'latex' builder "
          "but 'latexmk' was not found. Install a LaTeX toolchain (latexmk and "
          "xelatex, plus the packages zdocs' preamble loads), or drop 'latex' "
          "from this document's BUILDERS."
        )
      endif()
      set(builder_arg latex)
      # `latexmk` resolves the .tex, its own generated latexmkrc (which is what
      # selects xelatex) and every auxiliary file relative to the WORKING
      # DIRECTORY, so the chdir is load-bearing rather than tidiness.
      set(
        extra_commands
        COMMAND
        ${CMAKE_COMMAND}
        -E
        env
        "LATEXOPTS=${ZDOCS_LATEXOPTS}"
        ${CMAKE_COMMAND}
        -E
        chdir
        ${builder_out_dir}
        ${LATEXMK}
        -pdf
        ${doc_name}.tex
      )
    else()
      set(builder_arg ${builder})
    endif()

    add_doc_target(
      ${target_name}
      COMMAND
      ${CMAKE_COMMAND}
      -E
      make_directory
      ${DOCS_SRC_DIR}
      COMMAND
      ${CMAKE_COMMAND}
      -E
      env
      ${SPHINX_ENV}
      OUTPUT_DIR=${builder_out_dir}
      LATEX_DOC=${doc_name}.tex
      ${sphinx_executable}
      -b
      ${builder_arg}
      -c
      ${DOCS_CFG_DIR}
      -d
      ${builder_doctree_dir}
      -w
      ${DOCS_BUILD_DIR}/${builder}.log
      ${SPHINX_TAGS_ARGS}
      ${extra_sphinx_args}
      ${ZDOCS_SPHINXOPTS}
      ${ZDOCS_SPHINXOPTS_EXTRA}
      ${DOCS_SRC_DIR}
      ${builder_out_dir}
      ${extra_commands}
      USES_TERMINAL
      COMMENT
      "Running Sphinx ${builder} build for ${doc_name}..."
    )

    set_target_properties(
      ${target_name}
      ${target_name}-nodeps
      PROPERTIES ADDITIONAL_CLEAN_FILES "${DOCS_SRC_DIR};${builder_out_dir};${builder_doctree_dir}"
    )

    # Stage 2 waits for every document's stage-1 index so cross references
    # resolve. The -nodeps variant intentionally skips this for fast rebuilds.
    add_dependencies(${target_name} doc-index)

    # Only the html deliverable joins the full 'all-docs' build.
    if(builder STREQUAL "html")
      add_dependencies(all-docs ${target_name})
    endif()
  endforeach()

  # Per-document clean. Keeps ${DOC_OUT_DIR}/.git (the configure-time sphinx-git
  # pointer) so a rebuild works without reconfiguring.
  set(_zdocs_clean_deploy_dirs ${CMAKE_CURRENT_BINARY_DIR}/deploy/html/${doc_name})
  foreach(builder ${ARGS_BUILDERS})
    if(builder STREQUAL "latex")
      set(_zdocs_clean_folder "pdf")
    else()
      set(_zdocs_clean_folder "${builder}")
    endif()
    list(
      APPEND _zdocs_clean_deploy_dirs
      ${CMAKE_CURRENT_BINARY_DIR}/deploy/${_zdocs_clean_folder}/${doc_name}
    )
  endforeach()
  list(REMOVE_DUPLICATES _zdocs_clean_deploy_dirs)

  add_custom_target(
    ${doc_name}-clean
    COMMAND
      ${CMAKE_COMMAND} -E rm -rf ${DOCS_SRC_DIR} ${DOCS_DOCTREE_DIR} ${DOCS_INDEX_DOCTREE_DIR}
      ${DOC_OUT_DIR}/doctrees-latex ${DOCS_BUILD_DIR} ${_zdocs_clean_deploy_dirs}
    COMMENT "Cleaning document ${doc_name}..."
  )
  add_dependencies(clean-docs ${doc_name}-clean)
endfunction()
