The registry schema
====================

``documents.yaml`` is the :term:`registry`. It is read and validated by
:external+zdocs-api:py:func:`docrefs.load` (per-document view, used by every
``conf.py``) and :external+zdocs-api:py:func:`docrefs.manifest` (whole-registry
view, used by :external+zdocs-api:cmake:command:`add_docs_from_registry <command:add_docs_from_registry>`) — both
built on the same validation pass, so a registry that CMake accepts is a
registry every document's ``conf.py`` also accepts. See :doc:`../explanation/the-registry`
for how the derived structures are used; this page is the field-by-field
contract.

An invalid registry is a configure-time ``ValueError``, naming the offending
document. Nothing described as "required" below degrades gracefully — a
missing field is a hard failure, not a silently empty result.

Top level
---------

``groups`` (required, non-empty)
   A list of :ref:`group entries <registry-groups>`. Every document must
   belong to one of the ids declared here.

``documents`` (required)
   A mapping of document id to :ref:`document entry <registry-documents>`.

``base_url``
   The set's :term:`base URL`. There is no validation requiring this key to be
   present: an absent ``base_url`` resolves to the empty string, which the
   engine then turns into a single ``"/"`` (``"".rstrip("/") + "/"``) — every
   cross-document Sphinx link in the build would then be an absolute URL
   rooted at ``/``. Treat this as effectively required. Overridable per build
   with ``-DZDOCS_DOC_BASE_URL=…`` (:doc:`consumer-contract`).

``external_base_url``
   Prefix for a ``remote-url:`` that has no scheme (see ``kind: external``
   below). Lets a whole externally-hosted document set move by editing one
   value. Overridable with the ``ZDOCS_DOC_EXTERNAL_BASE_URL`` environment
   variable.

``check_external_urls``
   Boolean (YAML truthy strings also accepted via the
   ``ZDOCS_DOC_CHECK_EXTERNAL_URLS`` environment override), default off. When
   on, every remote document's URL gets a best-effort HTTP ``HEAD`` at build
   time; a network error is reported as "not reachable", never as a build
   failure. Off by default because a build host may have no route to an
   internal-only site.

``xref_smoketest``
   Deploy-relative path (e.g. ``"html/runbook/xref-test.html"``) to a page
   ``doccheck`` scans for cross-reference bullets that rendered as plain text
   or empty — see :doc:`cli`. Optional; without it, ``doc-check`` simply skips
   that one check.

``doxygen_xml``
   Project-scoped boolean, default off. When true, **every** ``kind: doxygen``
   document in the registry generates XML into
   ``deploy/xml/<bare-name>/`` — not per document, and not influenced by what
   any individual ``Doxyfile.in`` says about ``GENERATE_XML`` (the engine
   forces it in both directions; see :ref:`registry-doxyfile-keys` below).
   Required for the ``testmodule`` directive, which parses that XML.

``docs_root``
   Default ``"docs"``. **Read only by** ``docctl.py``, to resolve a document's
   source directory as ``<registry dir>/<docs_root>/<group dir>/<document
   id>`` when locating its ``.. doc_control::`` block (:doc:`cli`). Neither
   ``docrefs.py`` nor any CMake module reads this key at all — it has no
   effect on where Sphinx or Doxygen look for a document's sources; that is
   entirely ``doc_dir:`` (below) and the ``add_sphinx_target``/
   ``add_doxygen_target`` ``DOCDIR`` convention. A docset that runs no
   ``docctl`` action can ignore this key.

.. _registry-groups:

Groups
------

Each entry in ``groups:``:

``id`` (required)
   Referenced by every document's ``group:``.

``title`` (required)
   The heading shown above this group's links in the navigation sidebar.

``mode``
   One of ``exclude_if_selected`` (default — a page never links to itself),
   ``single_doc_title_merge`` (same exclusion, but rendered merged into the
   caption for a group that always resolves to exactly one document), or
   ``always_keep`` (every document in the group is always listed, including
   the current page).

``display``
   One of ``disabled_collapsing`` (default — always fully shown, no
   expand/collapse control), ``collapsed_at_opening``,
   ``not_collapsed_at_opening``, or ``no-display`` (the group is never shown,
   regardless of how many links it has).

``dir``
   A subdirectory name, read only by ``docctl.py`` as the middle segment of
   the ``docs_root``-based path above. No sample or fixture in this repository
   sets it — every registry either omits it (empty middle segment) or does not
   use ``docctl`` at all, so this field's behaviour beyond the default is
   documented but unexercised.

.. _registry-documents:

Documents
---------

Each entry in ``documents:``, keyed by its id:

``group`` (required)
   Must name a declared group id.

``kind``
   One of ``sphinx`` (default), ``doxygen``, ``external``, ``sphinx-external``,
   ``doxygen-external`` — see :ref:`registry-kinds` below and
   :doc:`../explanation/remote-documents`.

``title``
   Shown in navigation and as the Sphinx project title (``html_title``). Falls
   back to the bare id if omitted.

``prefix``
   The document's cross-reference :term:`prefix`. Defaults to the id with
   ``-`` replaced by ``_``. **Not validated for uniqueness** — nothing in
   ``docrefs.py`` rejects two documents sharing a prefix; since
   ``intersphinx_mapping``/``doxylink`` are built by assigning into a plain
   dict keyed by prefix, a collision would silently make one document's
   mapping entry overwrite the other's, in registry order, with no diagnostic.
   Keep prefixes distinct by convention.

``builders``
   Required, non-empty, for a ``sphinx`` document (or one omitting ``kind:``
   entirely) — e.g. ``[html]`` or ``[html, latex]``. A ``sphinx`` entry with no
   ``builders:`` is a configure-time ``FATAL_ERROR`` naming the document,
   raised by :external+zdocs-api:cmake:command:`add_docs_from_registry <command:add_docs_from_registry>` before
   any target in the registry is created. Meaningless (and ignored) for every
   other kind.

``doc_dir``
   Relocates where this document's sources are read from, without changing its
   id, target names or deploy path. When set through
   :external+zdocs-api:cmake:command:`add_docs_from_registry <command:add_docs_from_registry>`, a *relative*
   ``doc_dir:`` is resolved against **the directory containing
   documents.yaml itself** — not against whichever ``CMakeLists.txt`` called
   ``add_docs_from_registry()``. Those two directories are usually the same
   one, but are not the same thing by definition.

``version_scope``
   A git-tag namespace (e.g. ``"widget"``, matched as ``<scope>/v*`` in the
   consuming repository, then stripped for display — ``widget/v2.3`` renders
   as ``v2.3``). Exercised throughout this repository's samples and fixtures.

``version_project``
   An alternative to ``version_scope``: a west project name, whose own tags are
   used instead (``west list --format {abspath} <project>`` then
   ``git describe`` in that path). No sample or fixture in this repository
   sets it; this path is implemented and read
   (:external+zdocs-api:py:func:`docrefs.resolve_version`) but unverified
   against a real registry here.

``path``
   Deploy-relative path override, defaulting to ``html/<id>``. No known
   registry entry in this repository sets it explicitly — every one relies on
   the default, which is also what the builder-first deploy layout
   (:doc:`../explanation/deploy-layout`) assumes everywhere else. Treat an
   explicit override as unverified.

``remote-url``
   Required for ``external``, ``sphinx-external`` and ``doxygen-external``.
   An absolute URL (has a scheme) is used as-is; a relative one is resolved
   against ``external_base_url``.

``remote-tagfile``
   Required for ``doxygen-external`` only, in addition to (never instead of)
   ``remote-url`` — the two are validated independently, since Doxygen tag
   file names are not standardised and one cannot be derived from the other.
   Downloaded at build time and stored locally as ``doxygen.tag``, whatever
   the remote file is actually called.

``needs``
   Opt-in sub-block; presence is what makes this document importable as
   external needs by every peer. Two shapes:

   .. code-block:: yaml

      needs:
        source: json     # this document already runs sphinx-needs

   .. code-block:: yaml

      needs:
        source: inventory   # synthesize needs from a plain objects.inv
        filter: "^DUTY_"    # regex on the label name; default matches all
        type: requirement   # need type stamped on every synthesized need
        status: approved
        version: "1.0"

   ``source: inventory`` is for a Sphinx document that publishes labels but
   runs no sphinx-needs of its own (e.g. a requirements tool that only emits
   an ``objects.inv``); the stub is regenerated whenever the inventory is
   newer than the last-generated one. A ``testmodule.spec:`` (below) must
   point at a document with
   ``source: json`` specifically — a ``source: inventory`` document is
   rejected at configure time as a ``spec:`` target, because ``testreport``
   correlates against ``needs.json``, and the synthesized stub is not that.

``testmodule``
   Opt-in sub-block (see :doc:`../explanation/testmodule-and-twister` and
   :doc:`directives-and-roles`); its presence is the sole trigger that loads
   the ``test_module`` extension for this document. Allowed keys, each
   optional individually but validated when present:

   ``doxygen_source``
      Id of a ``kind: doxygen`` document whose XML the ``testmodule`` directive
      parses. Must exist and must be ``kind: doxygen`` — otherwise a
      configure-time error naming this document, its field and the bad id.

   ``api_reference``
      Same existence/kind requirement as ``doxygen_source``, for where
      ``@see`` cross-references resolve.

   ``spec``
      Id of the sphinx document whose exported needs a ``testreport`` document
      correlates against. Must exist, and must carry ``needs: {source: json}``
      — a ``spec:`` pointing at a document with no needs export, or a
      ``source: inventory`` one, is a configure-time error.

   An unknown key anywhere in this block (a typo like ``doxygen_src``) is
   itself a configure-time error naming the allowed set, rather than being
   silently ignored — silently ignoring it would degrade to "no XML parsed"
   with no diagnostic at all.

.. _registry-kinds:

The five kinds
---------------

======================  =========================================================  =========================================
``kind``                 What it produces                                          Required fields
======================  =========================================================  =========================================
``sphinx`` (default)     A local Sphinx build; an ``objects.inv``/needs.json peer   ``builders``
``doxygen``              A local Doxygen build; a ``doxygen.tag`` peer              — (no ``builders``; see below)
``external``             No build; a ``:qmsdoc:`` target only                      ``remote-url``
``sphinx-external``      No local build; a real intersphinx fetch at build time     ``remote-url``
``doxygen-external``     No local build; the engine downloads the tag file itself   ``remote-url``, ``remote-tagfile``
======================  =========================================================  =========================================

A ``kind: doxygen`` document's registry id is taken verbatim: it becomes the
target name, the default source folder and both deploy paths, with nothing
prepended or stripped —
:external+zdocs-api:cmake:command:`add_docs_from_registry <command:add_docs_from_registry>`
passes the id straight through to
:external+zdocs-api:cmake:command:`add_doxygen_target <command:add_doxygen_target>`.
The engine has no naming convention of its own here; a consumer who wants
one writes it into the id. An id of ``widget`` gets a bare target, folder and
deploy path; an id of ``dox-widget`` gets a ``dox-`` prefix on all of them,
opaque to the engine either way.

.. _registry-doxyfile-keys:

Doxyfile keys the engine owns
-------------------------------

A line in your ``Doxyfile.in`` setting one of these is read, then discarded —
the engine's own value is appended to the *generated* doxyfile after your
template is expanded, and Doxygen keeps only the last value of a repeated key
(:doc:`../explanation/architecture/crosscutting`). Source:
``cmake/doxygen.cmake``.

Assigned outright (a consumer's own line is fully overridden):

- ``HTML_OUTPUT`` — forced to ``"."`` (Doxygen's syntax for "no subfolder"),
  because ``OUTPUT_DIRECTORY`` is itself already the document's final public
  HTML directory under the builder-first deploy layout.
- ``GENERATE_TAGFILE`` — forced to ``<html dir>/doxygen.tag``.
- ``GENERATE_XML`` — forced to ``NO``, or ``YES`` when the top-level
  ``doxygen_xml:`` opt-in is on. Either way, this overrides your own setting in
  both directions.
- ``XML_OUTPUT`` — forced to an absolute path outside the servable tree, only
  when XML is enabled.
- ``HTML_STYLESHEET``, ``HTML_EXTRA_STYLESHEET``, ``HTML_EXTRA_FILES`` — reset
  to empty first (so a template shipping its own copy of the vendored theme
  does not load two versions of it), then appended to as below.
- ``HTML_HEADER`` — the engine's own header template.
- ``GENERATE_TREEVIEW``, ``HTML_COLORSTYLE`` — fixed theme settings.
- ``HTML_FOOTER`` — set only when a ``REGISTRY`` is given (cross-document nav
  needs siblings to list).

Appended to with ``+=`` (a consumer's own entries survive, engine entries are
added):

- ``TAGFILES`` — one entry per other ``kind: doxygen``/``doxygen-external``
  peer, derived from the registry.
- ``STRIP_FROM_PATH``, ``STRIP_FROM_INC_PATH`` — ``ZDOCS_PROJECT_BASE``,
  ``ZDOCS_WEST_TOPDIR`` and ``ZDOCS_DOXYGEN_INC_ROOTS``.
- ``HTML_EXTRA_STYLESHEET``, ``HTML_EXTRA_FILES`` — the vendored theme, then
  (if set) ``ZDOCS_PROJECT_LOGO``/``ZDOCS_DOXYGEN_EXTRA_CSS``, then the
  cross-document navigation widget last, so its overrides win over everything
  before it.

A separate, stage-1-only mechanic is not in this list because it is not part
of the generated doxyfile at all: the stage-1 build runs against a tiny
overlay file that ``@INCLUDE``\ s the full doxyfile and then blanks
``TAGFILES`` with a plain (non-appending) assignment, so a document's own
first build never depends on a peer's not-yet-built tag file.
