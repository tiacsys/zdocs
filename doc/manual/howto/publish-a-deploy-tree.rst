Publishing a deploy tree
==========================

A finished build's :term:`deploy tree` is already organised the way it needs
to be served — publishing it is a directory sync, nothing more. See
:doc:`../explanation/deploy-layout` for the full shape; this page is the
recipe.

Sync the HTML tree
--------------------

.. code-block:: console

   $ rsync -a --delete <build>/deploy/html/ webserver:/var/www/docs/

Sync ``deploy/html/`` specifically, not ``deploy/`` as a whole: ``deploy/xml/``
is Doxygen's machine-readable XML, generated only when a registry opts into it
and never meant to be public
(:doc:`../explanation/decisions/0007-engine-managed-doxygen-xml`); a
``deploy/pdf/`` folder, if any document declares the ``latex`` builder, is the
PDF set, a separate artifact you distribute on its own terms, covered below.

Serve it from anywhere
------------------------

Every cross-document link inside ``deploy/html/`` — Sphinx and Doxygen alike —
is a relative path (:doc:`../explanation/decisions/0012-relative-cross-document-links`),
so the tree can be published under any host, port or subdirectory without a
rebuild, and ``deploy/html/<doc>/index.html`` can be browsed straight from the
filesystem (``file://``) with working cross-document links. Still check them
with ``doc-check`` (:doc:`../reference/cli`) rather than by clicking around.

Distributing a PDF
---------------------

The PDF of each document with the ``latex`` builder lands in the PDF set,
``deploy/pdf``, as ``<title>_<version>.pdf``: the registry ``title:`` with
white space as ``-``, and the version the document shows. For example::

   deploy/pdf/
     Requirement-Specification_1.2.pdf
     Test-Specification_1.2.pdf
     Test-Report_1.2.pdf

The LaTeX build directory (the .tex, the auxiliary files) is a work area at
``<build>/<document>/latex`` and is not part of the deploy tree.

The PDFs of the set link to each other: a link to a need or a page of another
document of the set opens that document's PDF at that place
(:doc:`../explanation/decisions/0013-linked-pdf-set`). So the set is one
deliverable:

- Distribute the whole folder, for example as one archive, and keep the file
  names. A renamed file breaks the links into it.
- Build and release the set together. The file names carry the versions, so a
  new version of one document needs new PDFs of the documents that link to it.
- ``doc-check`` reads the PDFs and fails on a link into the set whose file or
  place does not exist.

A PDF is the one artifact that leaves the deploy tree entirely: its links to
documents outside the set (such as the Doxygen documents) use the ``base_url``,
fixed at build time. So a PDF built against a development ``base_url`` points
at a host that may not exist — permanently, in a document that could already
be signed off. Build (or rebuild) with the production ``base_url`` before
generating a PDF meant for distribution or signature.

The links of a PDF to documents outside the set use the ``base_url``: the
links of the needs, and the links to Doxygen pages (Source, See also, Declared
in). Two kinds of link would be dead in a PDF: a link to a local server
(``localhost`` or a loopback address, such as a development ``base_url``)
and a relative HTML path, which has no target next to the PDF. The
``pdf_links`` extension writes each of them as its text, without the link,
and warns once per document::

   WARNING: pdf_links: 72 link(s) written as text, without the link: they go
   to a local server or to an HTML path next to the PDF (the first:
   http://localhost/html/...). Set ZDOCS_DOC_BASE_URL to the published
   site to keep the links to other documents. [zdocs.pdf_links]

So a PDF of a development build has no dead links, only fewer links. The
links within the set do not depend on the ``base_url``. A new
``ZDOCS_DOC_BASE_URL`` takes effect on the next incremental build: the
imported needs are read again with the new URL.
