Cross-referencing two documents
==================================

You have two standalone documents from :doc:`first-docset` and
:doc:`add-a-doxygen-document` — a Sphinx ``runbook`` and a Doxygen
``widget``, built together but knowing nothing about
each other. This
tutorial introduces the :term:`registry` and turns them into one
:term:`document set`: a shared navigation sidebar, and a real cross-reference
from Sphinx prose into a Doxygen symbol.

Write the registry
----------------------

``doc/documents.yaml``:

.. code-block:: yaml

   docs_root: "."
   base_url: "https://docs.example.invalid/"

   groups:
     - id: interfaces
       title: "Interfaces"
     - id: guides
       title: "Guides"

   documents:
     widget:
       title: "Widget API"
       kind: doxygen
       group: interfaces
       prefix: my-widget

     runbook:
       title: "Runbook"
       kind: sphinx
       group: guides
       prefix: runbook
       builders: [html]

Every field here is covered in :doc:`../reference/registry-schema`; the two
that matter for this step are ``group`` (every document needs one, and it must
be declared under ``groups:``) and ``prefix`` (the name the *other* document
will use to reference this one).

Switch to the registry-driven factory
-------------------------------------------

Replace the two ``add_sphinx_target``/``add_doxygen_target`` lines in
``doc/CMakeLists.txt`` with one call:

.. code-block:: cmake

   set(DOC_REGISTRY ${CMAKE_CURRENT_LIST_DIR}/documents.yaml)
   add_docs_from_registry(REGISTRY ${DOC_REGISTRY})

``add_docs_from_registry`` reads ``documents.yaml`` and dispatches into the
same two factories you called by hand a moment ago — you are not adding a
third build mechanism, you are letting the registry drive the two you already
have. Nothing in either document's ``conf.py``/``Doxyfile.in`` changes: each
one already reads its cross-document wiring from the environment the factory
sets, not from anything you write per document.

Reference the Doxygen document from Sphinx
------------------------------------------------

In ``doc/runbook/index.rst``:

.. code-block:: rst

   See :my-widget:`acme_widget_init` for the widget API.

The role name is the target document's ``prefix:`` from the registry — not a
fixed engine name. This resolves through :term:`doxylink`, against
``widget``'s tag file, and it resolves at **parse**
time: if you rebuild only ``runbook`` without first building ``widget``,
the reference degrades to plain text rather than breaking
the build. ``all-docs`` avoids that for you automatically, by building every
tag file before any Sphinx document is parsed.

Build it
------------

.. code-block:: console

   $ cmake --build build

CMake notices ``CMakeLists.txt`` changed and reconfigures on its own; you do
not need to re-run ``cmake -S`` by hand. Open
``build/deploy/html/runbook/index.html``: the ``acme_widget_init`` reference is
now a real link into the Widget API document, and the navigation sidebar
lists both documents, grouped under "Interfaces" and "Guides" — on *both*
documents' pages, including the Doxygen one, which gets the identical grouped
list through its own cross-document navigation widget.

What's next
--------------

From here, :doc:`../howto/add-a-document` covers adding a third document to a
registry-driven set the same way, and
:doc:`../reference/registry-schema` is the complete field reference for
everything ``documents.yaml`` can express — remote peers, sphinx-needs
imports, version scoping, and the ``testmodule:`` block covered in
:doc:`../howto/render-test-specifications`.
