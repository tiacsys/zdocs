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
``deploy/pdf/`` folder, if any document declares the ``latex`` builder, is a
separate artifact you distribute on its own terms, covered below.

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

A document built with the ``latex`` builder lands at
``deploy/pdf/<document>/<document>.tex`` and its ``latexmk`` output alongside
it, including the final PDF. A PDF is the one artifact that leaves the deploy
tree entirely: its ``base_url`` is fixed at build time and travels with the
file wherever it is filed or mailed, so a PDF built against a development
``base_url`` points at a host that may not exist — permanently, in a document
that could already be signed off. Build (or rebuild) with the production
``base_url`` before generating a PDF meant for distribution or signature.
