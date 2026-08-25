System context
==============

zdocs sits between a consuming project and the two documentation toolchains it
drives. It owns no content of its own: every input comes from the consumer, and
every output is a directory the consumer publishes.

.. graphviz::
   :caption: Level 1 — zdocs in its environment

   digraph context {
     rankdir=TB;
     node [shape=box, style="rounded,filled", fillcolor="#f6f6f6",
           fontname="Helvetica", fontsize=10, margin="0.18,0.12"];
     edge [fontname="Helvetica", fontsize=9];

     author   [label="Document author\nrST, annotated C", shape=box, style=filled, fillcolor="#e8eef7"];
     project  [label="Consuming project\ndocuments.yaml, doc sources,\nZDOCS_* variables"];
     zdocs    [label="zdocs\ndocumentation engine\n(Zephyr module)", fillcolor="#dce8f5", penwidth=2];
     sphinx   [label="Sphinx\n+ sphinx-needs, doxylink,\nintersphinx"];
     doxygen  [label="Doxygen"];
     twister  [label="Twister\ntest results"];
     deploy   [label="deploy/\nhtml, pdf, xml", fillcolor="#e9f3e9"];
     reader   [label="Reader\nweb server, PDF", shape=box, style=filled, fillcolor="#e8eef7"];

     author  -> project [label="writes"];
     project -> zdocs   [label="declares documents,\nsets contract"];
     zdocs   -> sphinx  [label="configures, runs\n(twice)"];
     zdocs   -> doxygen [label="configures, runs\n(twice)"];
     twister -> sphinx  [label="results read by\ndirectives", style=dashed];
     sphinx  -> deploy;
     doxygen -> deploy;
     deploy  -> reader  [label="published by copying"];
   }

The consuming project
---------------------

A Zephyr workspace. It supplies the document sources, one registry file
describing the set, and the ``ZDOCS_*`` contract — where its repository root
is, which include roots its API documentation uses, which sphinx-needs
methodology applies, and where the set is published. It calls
``include(zdocs)`` and one registry function; it never reaches into engine
paths. See :doc:`../decisions/0001-zephyr-module-seam`.

The two toolchains
------------------

zdocs generates the configuration both tools run under: a ``conf.py`` shim
resolves to shared Sphinx configuration, and a consumer's ``Doxyfile.in`` is
expanded and then overridden with the keys the engine owns. Neither tool is
invoked directly by the consumer, and each is run **twice** — see
:doc:`crosscutting`.

Twister
-------

Zephyr's test runner is an input, not a dependency: its output directory is
read at build time by the test-report directives, and a documentation build
with no test results present renders a "not found" node rather than failing.
A docs build may legitimately outrun the test run that feeds it.

The deploy tree
---------------

The single output. It is organised by builder — ``deploy/html/<document>/`` —
so publishing is a directory sync and the servable tree contains nothing that
is not servable. See :doc:`../decisions/0006-deploy-tree-by-builder`.

What is deliberately *not* in the picture: any hosting, CI or publishing
machinery. zdocs produces the tree and checks its integrity; moving it
anywhere is the consuming project's business.
