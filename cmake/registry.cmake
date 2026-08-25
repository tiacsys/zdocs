# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Registry-driven document declarations (reusable CMake module).
#
# add_docs_from_registry() dispatches into both add_sphinx_target
# (sphinx.cmake) and add_doxygen_target (doxygen.cmake), so it is included
# AFTER both in zdocs.cmake.

#[==[.rst:
registry.cmake
===============

:cmake:command:`add_docs_from_registry` reads ``documents.yaml`` (via
``docrefs.py manifest``) and dispatches one :cmake:command:`add_sphinx_target`
or :cmake:command:`add_doxygen_target` call per document, so a consumer's
``CMakeLists.txt`` never hand-writes one factory call per document. It also
creates the per-``(group, builder)`` aggregate targets
(``<group>-<builder>``/``<group>-<builder>-nodeps``) documented on
:cmake:command:`add_docs_from_registry` itself.
#]==]

#-------------------------------------------------------------------------------
# zdocs_group_track(group builder dep_target nodep_target)
#
# A macro, not a function: it runs in add_docs_from_registry's own variable
# scope (no PARENT_SCOPE dance needed) so `list(APPEND ...)` on the
# dynamically-named per-pair list variables, and on the running set of
# distinct pairs, is visible to the caller directly — the same "list-variable
# names built via set()/list(APPEND)".
#
# `_zdocs_group_pairs` is the DISTINCT set of "<group>|<builder>" strings seen
# so far (checked with IN_LIST, not appended unconditionally, so the later
# pass creates each aggregate target exactly once); the two
# `_zdocs_group_{deps,nodeps}_<group>_<builder>` lists accumulate every
# contributing document's own target name, appended unconditionally (a
# document's own target name is never a duplicate contribution).
macro(zdocs_group_track group builder dep_target nodep_target)
  set(_zdocs_group_pair "${group}|${builder}")
  if(NOT _zdocs_group_pair IN_LIST _zdocs_group_pairs)
    list(APPEND _zdocs_group_pairs "${_zdocs_group_pair}")
  endif()
  list(APPEND _zdocs_group_deps_${group}_${builder} "${dep_target}")
  list(APPEND _zdocs_group_nodeps_${group}_${builder} "${nodep_target}")
endmacro()

#-------------------------------------------------------------------------------
# add_docs_from_registry(REGISTRY <documents.yaml>)
#
# Declares every document in the registry as a CMake target, so a consumer's
# CMakeLists.txt does not have to hand-write one add_sphinx_target /
# add_doxygen_target call per document — the facts a factory call needs
# (kind, builders, doc_dir) already live in documents.yaml; this reads them
# back via `docrefs.py manifest` and dispatches per document:
#
#   kind: external          no CMake target of any kind — nothing to build.
#   kind: sphinx-external   likewise no CMake target of any kind — cross-
#                           referenced via a real intersphinx fetch at build
#                           time instead (see docrefs.py's own load()).
#   kind: doxygen-external  exactly ONE target, <id>-tag: downloads
#                           `remote-tagfile:` to deploy/html/<id>/doxygen.tag
#                           at BUILD time (via download_external_tag.cmake),
#                           gating doc-tags/doc-index like an internal
#                           doxygen document's own stage-1 tag target — no
#                           stage-2 target, no all-docs membership, no group
#                           aggregate contribution.
#   kind: doxygen       add_doxygen_target(<id> REGISTRY <REGISTRY>
#                                           [DOCDIR <resolved doc_dir>])
#   kind: sphinx         add_sphinx_target(<id> BUILDERS <builders...>
#   (or omitted)                            REGISTRY <REGISTRY>
#                                           [DOCDIR <resolved doc_dir>])
#                        — FATAL_ERROR, naming <id>, if `builders:` is empty
#                        or missing: never silently build a sphinx document
#                        with zero output formats (fail loudly at configure
#                        time, per this engine's own convention — see
#                        add_sphinx_target's identical BUILDERS check).
#   <group>-<builder>          depends on every qualifying document's own
#                               <id>-<builder> target.
#   <group>-<builder>-nodeps   the same, but against each document's
#                               <id>-<builder>-nodeps twin instead.
#
# A Doxygen document has no `builders:` at all, but counts as builder "html"
# for THIS aggregation only — its own target is named after its registry id
# exactly (<id>/<id>-nodeps), unrenamed. A (group, builder) pair with zero
# contributors gets no aggregate at all, rather than an empty
# add_custom_target(); kind: external and kind: sphinx-external documents
# contribute to none (they already produce no target of any kind — nothing
# extra to special-case).
#
# doc_dir resolution — the one deliberate difference from the DOCDIR argument
# taken directly by add_sphinx_target/add_doxygen_target: `doc_dir:` is
# resolved relative to the directory CONTAINING the registry file itself, not
# relative to whichever CMakeLists.txt calls add_docs_from_registry. Those
# two directories are usually the same one in practice, but are not the same
# thing, and do not have to coincide.
#
# add_sphinx_target/add_doxygen_target's own DOCDIR handling
# (zdocs_resolve_docdir, in common.cmake) resolves a RELATIVE DOCDIR against
# the CALLER's directory — which, called from here, would be
# add_docs_from_registry's own call site inside this file, not the
# consumer's. So a relative doc_dir is resolved HERE, against the registry's
# own directory, and handed down as an ABSOLUTE path — which makes
# zdocs_resolve_docdir's IS_ABSOLUTE check take the "use as-is" branch
# instead of re-resolving it (wrongly) against this file's directory. When
# doc_dir is absent, DOCDIR is omitted entirely so the callee's usual default
# (<caller dir>/<id>) applies.
#[==[.rst:
.. cmake:command:: add_docs_from_registry

  .. code-block:: cmake

    add_docs_from_registry(REGISTRY <documents.yaml>)

  Declares every document in ``REGISTRY`` as a CMake target, dispatched by
  ``kind``:

  - ``sphinx`` (or omitted) — :cmake:command:`add_sphinx_target`
    ``(<id> BUILDERS <builders...> REGISTRY <REGISTRY> [DOCDIR ...])``.
    A configure-time ``FATAL_ERROR`` naming the document if ``builders:`` is
    empty or missing.
  - ``doxygen`` — :cmake:command:`add_doxygen_target`
    ``(<id> REGISTRY <REGISTRY> [DOCDIR ...])``.
  - ``external`` / ``sphinx-external`` — no CMake target of any kind.
  - ``doxygen-external`` — exactly one target, ``<id>-tag``, that
    downloads ``remote-tagfile:`` at build time.

  Also creates, per distinct ``(group, builder)`` pair with at least one
  contributing document, two aggregate targets: ``<group>-<builder>``
  (depends on every contributor's own ``<id>-<builder>``) and
  ``<group>-<builder>-nodeps`` (the same, against each ``-nodeps`` twin). A
  Doxygen document counts as builder ``html`` for this aggregation only; its
  own target is named after its registry id, exactly.

  ``doc_dir:`` in the registry, when relative, is resolved against the
  directory containing ``REGISTRY`` itself — not against whichever
  ``CMakeLists.txt`` called this command.
#]==]
function(add_docs_from_registry)
  cmake_parse_arguments(ARGS "" "REGISTRY" "" ${ARGN})

  if(NOT ARGS_REGISTRY)
    message(FATAL_ERROR "add_docs_from_registry() requires REGISTRY <documents.yaml>.")
  endif()

  # doc_dir: is resolved against the registry's OWN directory — see the
  # function-header comment for why this differs from the caller-relative
  # DOCDIR the factories take directly.
  get_filename_component(_zdocs_registry_dir "${ARGS_REGISTRY}" DIRECTORY)

  execute_process(
    COMMAND
      ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../scripts/docrefs.py manifest
      --registry ${ARGS_REGISTRY}
    OUTPUT_VARIABLE _zdocs_manifest_json
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE _zdocs_manifest_err
    RESULT_VARIABLE _zdocs_manifest_res
  )
  if(NOT _zdocs_manifest_res EQUAL 0)
    message(
      FATAL_ERROR
      "add_docs_from_registry(): could not read the manifest from "
      "${ARGS_REGISTRY} (docrefs.py manifest exited ${_zdocs_manifest_res}):\n"
      "${_zdocs_manifest_err}"
    )
  endif()

  # Re-run configure whenever the registry changes. add_sphinx_target /
  # add_doxygen_target already do this per call, but a document skipped
  # entirely (kind: external) never reaches either factory, so relying on
  # their per-call bookkeeping alone would leave the whole-registry read
  # above unwatched whenever every changed field belongs to such a document.
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${ARGS_REGISTRY})

  string(JSON _zdocs_doc_count LENGTH "${_zdocs_manifest_json}")
  if(_zdocs_doc_count EQUAL 0)
    return()
  endif()

  math(EXPR _zdocs_doc_last "${_zdocs_doc_count} - 1")

  # Pass 1: validate every sphinx document's builders: BEFORE creating any
  # target at all.
  #
  foreach(_zdocs_i RANGE 0 ${_zdocs_doc_last})
    string(JSON _zdocs_entry GET "${_zdocs_manifest_json}" ${_zdocs_i})
    string(JSON _zdocs_kind GET "${_zdocs_entry}" "kind")
    if(
      NOT _zdocs_kind STREQUAL "external"
      AND NOT _zdocs_kind STREQUAL "doxygen"
      AND NOT _zdocs_kind STREQUAL "sphinx-external"
      AND NOT _zdocs_kind STREQUAL "doxygen-external"
    )
      string(JSON _zdocs_id GET "${_zdocs_entry}" "id")
      string(JSON _zdocs_builders_len LENGTH "${_zdocs_entry}" "builders")
      if(_zdocs_builders_len EQUAL 0)
        message(
          FATAL_ERROR
          "add_docs_from_registry(): document '${_zdocs_id}' is kind: sphinx "
          "(or omits kind:) but has no 'builders:' — a sphinx document must "
          "declare at least one Sphinx builder (e.g. 'builders: [html]') in "
          "${ARGS_REGISTRY}."
        )
      endif()
    endif()
  endforeach()

  # Pass 2: every entry is now known to carry what its kind requires — create
  # the actual targets, and (via zdocs_group_track()) accumulate the
  # per-(group, builder) dependency lists pass 3 below turns into aggregate
  # targets. Empty, not undefined, before the loop: zdocs_group_track()'s
  # IN_LIST check requires the variable to already exist as a (possibly
  # empty) list, not merely be unset.
  set(_zdocs_group_pairs "")
  foreach(_zdocs_i RANGE 0 ${_zdocs_doc_last})
    string(JSON _zdocs_entry GET "${_zdocs_manifest_json}" ${_zdocs_i})
    string(JSON _zdocs_id GET "${_zdocs_entry}" "id")
    string(JSON _zdocs_kind GET "${_zdocs_entry}" "kind")
    string(JSON _zdocs_doc_dir GET "${_zdocs_entry}" "doc_dir")

    set(_zdocs_docdir_args "")
    if(NOT _zdocs_doc_dir STREQUAL "")
      if(IS_ABSOLUTE "${_zdocs_doc_dir}")
        set(_zdocs_docdir_abs "${_zdocs_doc_dir}")
      else()
        set(_zdocs_docdir_abs "${_zdocs_registry_dir}/${_zdocs_doc_dir}")
      endif()
      set(_zdocs_docdir_args DOCDIR ${_zdocs_docdir_abs})
    endif()

    if(_zdocs_kind STREQUAL "external")
      # No CMake target of any kind — see the function-header comment.
    elseif(_zdocs_kind STREQUAL "sphinx-external")
      # Also no CMake target of any kind — a sphinx-external document is
      # cross-referenced via a real intersphinx fetch at build time (see
      # docrefs.py's own load()), never built locally, exactly like
      # kind: external above.
    elseif(_zdocs_kind STREQUAL "doxygen-external")
      # Unlike external/sphinx-external, this DOES get one CMake target: a
      # Doxygen tag file has to be fetched onto local disk ourselves (Doxygen,
      # unlike Sphinx's own intersphinx, cannot fetch anything over HTTP
      # itself), and that fetch must happen at BUILD time, not here at
      # configure time — this branch only DECLARES the target; the actual
      # `file(DOWNLOAD ...)` lives in download_external_tag.cmake, invoked as
      # its COMMAND, exactly the same "cmake -P wrapper" shape run_doxygen.cmake
      # already uses to defer doxygen's own version-dependent bits to build
      # time.
      #
      # The deploy path below is keyed on the raw registry id, with no
      # prefix synthesis — docrefs.py's own tagfiles()/load() compute this
      # kind's local path the identical way (`f"html/{doc_id}"`), and there
      # is no add_doxygen_target() call in this branch to reconcile it
      # against.
      string(JSON _zdocs_remote_tagfile GET "${_zdocs_entry}" "remote_tagfile")
      set(_zdocs_dox_ext_dest ${CMAKE_CURRENT_BINARY_DIR}/deploy/html/${_zdocs_id}/doxygen.tag)

      add_custom_target(
        ${_zdocs_id}-tag
        COMMAND
          ${CMAKE_COMMAND} -DURL=${_zdocs_remote_tagfile} -DDEST=${_zdocs_dox_ext_dest} -P
          ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/download_external_tag.cmake
        COMMENT "Downloading remote doxygen tag for ${_zdocs_id}..."
      )
      add_dependencies(doc-tags ${_zdocs_id}-tag)
      add_dependencies(doc-index ${_zdocs_id}-tag)
    elseif(_zdocs_kind STREQUAL "doxygen")
      add_doxygen_target(${_zdocs_id} REGISTRY ${ARGS_REGISTRY} ${_zdocs_docdir_args})

      string(JSON _zdocs_group GET "${_zdocs_entry}" "group")
      zdocs_group_track(${_zdocs_group} html ${_zdocs_id} ${_zdocs_id}-nodeps)
    else()
      string(JSON _zdocs_builders_len LENGTH "${_zdocs_entry}" "builders")
      set(_zdocs_builders "")
      math(EXPR _zdocs_builders_last "${_zdocs_builders_len} - 1")
      foreach(_zdocs_bi RANGE 0 ${_zdocs_builders_last})
        string(JSON _zdocs_builder GET "${_zdocs_entry}" "builders" ${_zdocs_bi})
        list(APPEND _zdocs_builders "${_zdocs_builder}")
      endforeach()

      add_sphinx_target(
        ${_zdocs_id}
        BUILDERS ${_zdocs_builders}
        REGISTRY ${ARGS_REGISTRY}
        ${_zdocs_docdir_args}
      )

      string(JSON _zdocs_group GET "${_zdocs_entry}" "group")
      foreach(_zdocs_builder ${_zdocs_builders})
        zdocs_group_track(
          ${_zdocs_group}
          ${_zdocs_builder}
          ${_zdocs_id}-${_zdocs_builder}
          ${_zdocs_id}-${_zdocs_builder}-nodeps
        )
      endforeach()

      string(JSON _zdocs_testmodule_dox_src GET "${_zdocs_entry}" "testmodule_doxygen_source")
      if(NOT _zdocs_testmodule_dox_src STREQUAL "")
        foreach(_zdocs_builder ${_zdocs_builders})
          add_dependencies(${_zdocs_id}-${_zdocs_builder} ${_zdocs_testmodule_dox_src})
        endforeach()
      endif()

      string(JSON _zdocs_testmodule_spec GET "${_zdocs_entry}" "testmodule_spec")
      if(NOT _zdocs_testmodule_spec STREQUAL "")
        add_dependencies(${_zdocs_id}-index ${_zdocs_testmodule_spec}-index)
      endif()
    endif()
  endforeach()

  # Pass 3: create the aggregate targets pass 2 discovered demand for — one
  # add_custom_target() pair per DISTINCT (group, builder) pair that ended up
  # with at least one contributor (see the function-header comment and
  # zdocs_group_track()'s own comment for why a pair with zero contributors
  # must get no target at all, not an empty one).
  foreach(_zdocs_pair ${_zdocs_group_pairs})
    string(REPLACE "|" ";" _zdocs_pair_parts "${_zdocs_pair}")
    list(GET _zdocs_pair_parts 0 _zdocs_pair_group)
    list(GET _zdocs_pair_parts 1 _zdocs_pair_builder)

    add_custom_target(${_zdocs_pair_group}-${_zdocs_pair_builder})
    add_dependencies(
      ${_zdocs_pair_group}-${_zdocs_pair_builder}
      ${_zdocs_group_deps_${_zdocs_pair_group}_${_zdocs_pair_builder}}
    )

    add_custom_target(${_zdocs_pair_group}-${_zdocs_pair_builder}-nodeps)
    add_dependencies(
      ${_zdocs_pair_group}-${_zdocs_pair_builder}-nodeps
      ${_zdocs_group_nodeps_${_zdocs_pair_group}_${_zdocs_pair_builder}}
    )
  endforeach()
endfunction()
