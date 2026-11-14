0016. A document is dated by its own repository
================================================

Status
------

Proposed, 2026-11-14.

Context
-------

A set can build a document of another west project through ``doc_dir:``, for
example a downstream repository that builds its upstream documents to check
its links into their needs. The registry key ``version_project`` names that
project, but only the Doxygen path (the ``docrefs.py version`` CLI) read it.
``zdocs_conf`` passed only ``version_scope``, so a Sphinx document showed the
consuming repository's version, and the two toolchains could disagree for one
repository. ``version_scope`` alone was matched in the consuming repository
too, so an upstream document's scoped tags (``sysreq/v1.0``) were never
found, and the ``version_project`` result kept its tag namespace
(``sysreq/v1.0`` instead of ``v1.0``).

Decision
--------

``version_project`` names the repository that dates the document;
``version_scope`` names which of its tags:

- With ``version_project``, the repository is that west project; without it,
  the consuming repository (``ZDOCS_PROJECT_BASE``), as before.
- ``version_scope`` is matched as ``<scope>/*`` in that repository and
  stripped, as before.
- ``version_project`` without ``version_scope`` gives the project's nearest
  tag with the namespace stripped: everything up to the last ``/``.
- The fallback ``v0.0-dev+g<sha>`` is the sha of that repository; a project
  without a tag gets it too (``git describe --always`` gave a bare sha), so
  an untagged upstream document shows the same downstream as in its own
  repository.
- Sphinx documents, the Doxygen CLI and the PDF file names use one function,
  ``docrefs.document_version``.

The repository is named in the registry, not derived from the git root of
``doc_dir``: a consumer whose documents sit in a nested repository or a
submodule would otherwise change version without a registry change.

Consequences
------------

- An upstream document built downstream shows the version of its own
  repository, the same in Sphinx and Doxygen. With the upstream's
  ``version_scope`` copied too, the same version as in the upstream's own
  build.
- A registry that set both keys used to show the consuming repository's
  scoped tags; it now shows the project's.
- The version needs ``west`` and ``ZDOCS_WEST_TOPDIR`` at build time; without
  them the consuming repository dates the document, as before.
