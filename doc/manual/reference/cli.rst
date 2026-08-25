Command-line tools
===================

Two standalone scripts under ``scripts/``, run directly with ``python3``, not
installed as console entry points — there is no packaging for either
(:doc:`../explanation/documentation-guidelines` — this docset's own
``README.rst`` is the same way). Both take ``--registry`` explicitly rather
than defaulting to one, since these scripts ship with the engine, which has no
registry of its own.

``docctl.py`` — controlled-document workflow
------------------------------------------------

.. code-block:: console

   $ python3 <zdocs>/scripts/docctl.py --registry documents.yaml <command> ...

Drives the author → review → approve lifecycle of a ``.. doc_control::`` block
(:doc:`directives-and-roles`) by editing it in place and committing the change
with your own git identity (``git config user.name``/``user.email``). Source:
:external+zdocs-api:py:mod:`docctl`.

``list``
   Print every document id that the other subcommands can actually operate
   on — one resolving to a source directory containing exactly one
   ``.. doc_control::`` directive. A registry entry with no such directive, an
   unresolvable ``doc_dir``, or more than one directive in its top-level files
   is silently excluded from this list, not reported as an error.

``author <document-id> [--version VERSION]``
   Sets ``:author:`` to your git identity and commits
   (``Signed-off-by:`` only). ``--version`` also overwrites ``:version:``.

``review <document-id> [--force]``
   Requires ``author`` to have already run. Refuses if the commit that set
   ``:author:`` (found via ``git blame``) has the same committer email as you
   — a reviewer must be a different person — unless ``--force``. Commits with
   a ``Reviewed-by:`` trailer in addition to ``Signed-off-by:``.

``approve <document-id> [--effective-date YYYY-MM-DD] [--force]``
   Requires ``reviewed_by`` to be set **and backed by a real commit** (not an
   uncommitted edit), unless ``--force``. Sets ``:approved_by:`` and
   ``:approval_date:`` (today), commits with an ``Approved-by:`` trailer, and
   creates a signed git tag ``<document-id>/<version>`` — the same
   ``<id>/*`` pattern :external+zdocs-api:py:func:`docrefs.resolve_version`
   matches against for the sidebar version.

``bump-version <document-id> [--major | --minor]``
   Starts a new version cycle on an already-released document: bumps
   ``:version:`` (``--minor`` is the default, ``x.Y`` → ``x.Y+1``; ``--major``
   is ``X.y`` → ``X+1.0``, and the current version must already be
   ``major.minor``), then **removes** ``:author:``, ``:reviewed_by:``,
   ``:approved_by:`` and ``:approval_date:`` outright (not blanks them), so
   ``doc_control``'s own placeholders take over again. Refused for
   ``classification: Record`` documents, which version by folder/edition
   instead. If a release tag for the *old* version exists, also repoints a
   ``.. git_changelog::`` directive's ``:rev-list:`` at
   ``<old-tag>..HEAD`` — but only if the document actually has one; nothing in
   this engine loads the ``sphinx_git`` extension that directive belongs to
   (neither ``zdocs_conf.py``'s extension list nor
   ``sphinx/requirements-doc.txt`` mentions it), so a document wanting
   ``git_changelog`` needs to add the package and the extension itself.

Every commit is both ``-s`` (signed-off) and ``-S`` (GPG-signed); an
unconfigured signing key is a hard failure here, not a silent skip, since this
is a compliance action. On error, ``docctl`` prints ``docctl: error: ...`` to
stderr and exits **1**; a successful run exits **0**. There is no dry-run
mode.

``doccheck.py`` — cross-reference integrity gate
----------------------------------------------------

.. code-block:: console

   $ python3 <zdocs>/scripts/doccheck.py --registry documents.yaml \
       --deploy build/deploy

Wired automatically as a ``POST_BUILD`` step of ``all-docs`` by
:external+zdocs-api:cmake:command:`add_doc_check <command:add_doc_check>` (so an ordinary build already
runs it) and as the standalone ``doc-check`` target, for re-checking an
existing deploy tree without rebuilding it. Source:
:external+zdocs-api:py:mod:`doccheck`.

Two checks, neither of which a green ``sphinx-build``/``doxygen`` log catches on
its own. Both read the built deploy tree, so ``--deploy`` is required — there
is no sources-only mode, because a run that checks nothing must not be able to
report success.

A. **Unresolved cross-references** — requires a registry
   ``xref_smoketest:`` page. Parses that one rendered page's cross-reference
   bullets and flags any that rendered as an empty node (a parse-time role
   whose target inventory was not built yet) or as plain text (the target
   itself is missing from this build) instead of a real link. Skipped, with a
   note in the final summary line, if no ``xref_smoketest:`` is configured —
   this docset does not currently set one, so check A does not run against it.

B. **Dead deploy links** — scans every rendered
   ``*.html`` page's ``href``s; resolves an absolute one starting with the
   registry's ``base_url`` back into the deploy tree, a bare relative one
   against the page's own directory, and skips anything that escapes the
   deploy tree entirely (external links, ``mailto:``, and similar) — policing
   those is not this check's job.

Exit codes: **0** clean, **1** one or more findings (printed to stderr, grouped
by check, with a final ``doccheck: FAILED with N finding(s)`` line), **2** bad
invocation (registry or deploy path does not exist). A clean run with no
``xref_smoketest:`` configured still exits 0, but says so explicitly in its
summary rather than reporting "OK" the same way a fully-covered run does.

.. note::

   A third check was removed from ``doccheck`` rather than fixed. It scanned
   document sources for tokens shaped like a document id and reported any the
   registry did not declare, to catch content still naming a deleted document.
   Recognising an id by shape means hardcoding a naming convention into the
   engine — the pattern was ``dox-``/``docctl-``/``sop-`` — and it cannot be
   derived from the registry instead, since an id that *is* declared is exactly
   the case the check must stay silent about. It also made documentation about
   zdocs unwritable: every example id in a tutorial was a finding.
