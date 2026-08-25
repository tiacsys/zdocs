Adding a document to a registry-driven set
============================================

You already have a :term:`document set` built through
:external+zdocs-api:cmake:command:`add_docs_from_registry <command:add_docs_from_registry>`, and want to add one
more :term:`document` — a Sphinx one, in this recipe; a Doxygen one differs
only in the two steps called out below.

1. Create the source folder
------------------------------

.. code-block:: console

   $ mkdir doc/notes
   $ cat > doc/notes/conf.py <<'EOF'
   import os, sys
   from pathlib import Path

   sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])
   from zdocs_conf import configure

   configure(globals(), doc_dir=Path(__file__).resolve().parent, project="Notes")
   EOF
   $ echo -e "Notes\n=====\n" > doc/notes/index.rst

The folder name (``notes``) becomes the document's registry id — unless you
give it a ``doc_dir:`` (below), in which case the id and the folder can
differ.

For a Doxygen document, the same rule applies to the folder — ``doc/notes/``
— and you write a ``Doxyfile.in`` there rather than a ``conf.py``. Give it a
``dox-`` prefix (``doc/dox-notes/``) only if you want one: the engine has no
convention of its own here, so whatever you write into the id is what you
get. See the ``doxygen-simple`` sample tree for the smallest working one.

2. Declare it in the registry
--------------------------------

.. code-block:: yaml

   documents:
     notes:
       title: "Notes"
       kind: sphinx
       group: guides
       prefix: notes
       builders: [html]

``group`` must already exist under ``groups:``; ``kind: sphinx`` is the
default and may be omitted; ``builders:`` is required for a Sphinx document
and its absence is a configure-time error naming this id
(:doc:`../reference/registry-schema`). For a Doxygen document, drop
``builders:`` entirely and set ``kind: doxygen``.

3. Reconfigure and build
--------------------------

.. code-block:: console

   $ cmake --build <build>

You do not need to re-run ``cmake -S`` by hand: every ``add_sphinx_target``/
``add_doxygen_target`` call registers ``documents.yaml`` as a configure-time
dependency, so CMake reconfigures itself on the next build when the registry
changed. The new document gets its own ``notes-html``/``notes-html-nodeps``
targets, joins ``all-docs`` and its group's aggregate target, and — because
every *other* document's cross-reference mapping is derived from the same
registry — becomes referenceable from anywhere in the set without touching
any other document's ``conf.py`` or ``Doxyfile.in``.

4. Cross-reference it, and check the navigation
--------------------------------------------------

From any other document:

.. code-block:: rst

   See :external+notes:doc:`index` for the details.

and rebuild that *other* document (or ``all-docs``) so its stage-1 index sees
the new peer. Then open any page in the set: the new document's title should
now appear under its ``group``'s heading in the navigation sidebar, on every
page — not only on pages that reference it, since navigation is derived from
the whole registry, not from what links exist.

If your document relocates its content away from ``<same directory as
documents.yaml>/<id>/``, add ``doc_dir:`` to its registry entry instead of a
:doc:`../reference/registry-schema` ``DOCDIR`` argument — resolution rules for
the two differ (see that page's note on how ``doc_dir:`` is resolved).
