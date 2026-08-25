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

Match the served URL to ``base_url``
----------------------------------------

Every cross-document Sphinx link in the build is an **absolute URL** baked in
under the registry's ``base_url:`` (or whatever ``-DZDOCS_DOC_BASE_URL=…``
overrode it to) at build time. If the tree is served from anywhere else, those
links are wrong on the published site even though the build was clean — there
is no way to relocate a Sphinx page's own outbound links after the fact.
Rebuild with the right value set (:doc:`../reference/consumer-contract`)
*before* publishing, rather than after finding the links broken.

Doxygen's own cross-document links are relative hops within ``deploy/html/``,
so they are unaffected by where the tree is ultimately served from — only the
Sphinx side is base-URL sensitive.

Browsing before you publish
-------------------------------

Opening ``deploy/html/<doc>/index.html`` straight from the filesystem
(``file://``) works for reading one document in isolation, but every
cross-document Sphinx link will be dead: it is the absolute
``base_url``-rooted URL described above, and ``file://`` has no such host to
resolve it against. Doxygen's own inter-document links, being relative,
resolve fine even this way. This is expected engine behaviour, not something
to work around — check cross-document links by running ``doc-check``
(:doc:`../reference/cli`) against the built tree, not by clicking around it
locally.

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
