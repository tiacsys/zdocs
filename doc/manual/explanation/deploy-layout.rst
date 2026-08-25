The deploy tree
===============

Everything a build produces for publication lands under one directory,
organised by builder:

.. code-block:: text

   deploy/
     html/          <- the servable tree: sync this to a web server
       manual/
       api/
       widget/      <- Doxygen documents are peers here
     pdf/           <- the latex builder's folder, named for what it delivers
       handbook/
     xml/           <- Doxygen XML: machine input, never published
       widget/

Publishing is a directory sync of ``deploy/html/``, and optionally
``deploy/pdf/``. Nothing else needs selecting, excluding or post-processing —
which is the whole reason for this shape. See
:doc:`decisions/0006-deploy-tree-by-builder`.

What is servable, and what is not
---------------------------------

The distinction the layout enforces is **servable versus not**, and it is not
the same as "output versus intermediate".

Doxygen XML is real output — the test-specification extension parses it to
render test cases — but it is machine input, sizeable, and meaningless to a
reader. It lives outside ``html/`` entirely
(:doc:`decisions/0007-engine-managed-doxygen-xml`). A tag file, by contrast,
stays *inside* a Doxygen document's published directory on purpose: that is
what makes it fetchable by another project that wants to cross-reference this
one over HTTP.

The trap this layout creates
----------------------------

Doxygen resolves several of its output settings **relative to its output
directory** — and the engine points that directory at the document's public
HTML directory. So any Doxygen output key the engine does not explicitly
control lands in the servable tree by default. That is how XML got there in the
first place, and any future key of the same family behaves the same way.

Two link shapes, one tree
-------------------------

Within the same tree, the two toolchains address each other differently:

- **Doxygen to Doxygen** is a relative hop — one ``../`` under this layout.
- **Sphinx to anything** is an absolute URL under the set's base URL.

So a deploy tree opened from the filesystem has working Doxygen cross-links and
broken Sphinx ones. That is expected. It also means the base URL is baked into
every published Sphinx page at build time, which matters most for PDFs — see
:doc:`architecture/crosscutting`.

Cleaning
--------

A document's clean target enumerates one path per builder it produces, plus,
for a Doxygen document, its XML directory — unconditionally, because a document
can stop generating XML across a re-configure and the previously generated
files must still go.
