0013. The PDFs of a document set link to each other
====================================================

Status
------

Accepted, 2026-10-14. Changes the ``deploy/pdf`` part of
:doc:`0006-deploy-tree-by-builder`.

Context
-------

A PDF leaves the deploy tree: it is mailed, filed and signed. Its links to
other documents went to the published HTML site (the registry's
``base_url``), so a reader needed the site and a network, and a link from a
released PDF could open a newer version of the target. A PDF of a
development build linked a local server, or nothing (``pdf_links``).

``deploy/pdf/<document>/`` held the whole LaTeX build directory: the .tex,
the auxiliary files and the PDF, which Sphinx names after the project title.
Nothing in it was meant for a reader except the PDF.

Decision
--------

The PDFs of a set are one deliverable that works offline and links within
itself:

- ``deploy/pdf`` is the PDF set: one ``<title>_<version>.pdf`` per document
  with a ``latex`` builder, side by side. The title is the registry
  ``title:`` (white space as ``-``), the version is the one the document
  shows (its ``version_scope``). ``docrefs.py pdf-deliver`` copies latexmk's
  PDF there and removes the other versions of the same document. Two
  documents with the same title part are a configure-time error.
- The LaTeX build directory is a work area at ``<build>/<document>/latex``,
  outside the deploy tree.
- Each LaTeX label is a named destination of the same name (hyperref's
  ``destlabel``). Sphinx writes a label for each need, section and page:
  ``<page>:<anchor>``.
- A link to a document of the set becomes a link to its PDF:
  ``<title>_<version>.pdf#<page>:<anchor>``, which hyperref writes as a
  "go to remote" action (file and named destination). A link to another
  document keeps the rules before: the ``base_url``, or text when that is a
  local server (``pdf_links``).
- ``doc-check`` reads the PDFs and fails on a link into the set whose file or
  destination does not exist.

Consequences
------------

- The set works offline and in one version: each link names the file of the
  version it was built with. A new version of one document renames its file,
  so the documents that link to it must be built again (the set is built and
  released together).
- The links work only while the files keep their names and stay in one
  folder. Deliver the set as one unit (a folder or an archive); a system that
  renames the files breaks the links.
- Viewer support can differ. Evince follows the links, and pdf.js opens a
  PDF at a named destination. The "go to remote" links were not tested in
  browser viewers.
- Doxygen documents have no PDF; links to them stay web links or text.
- A consumer that picked up ``deploy/pdf/<document>/<title>.pdf`` must take
  ``deploy/pdf/<title>_<version>.pdf`` instead.
