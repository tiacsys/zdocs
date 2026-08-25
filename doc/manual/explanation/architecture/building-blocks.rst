Building blocks
===============

zdocs is four areas: the CMake surface a consumer calls, the Python scripts
that read the registry and check the result, the Sphinx payload handed to
``sphinx-build``, and the Doxygen payload handed to ``doxygen``. The split
follows the tool each area serves — see
:doc:`../decisions/0010-payload-split-by-tool`.

.. graphviz::
   :caption: Level 2 — inside zdocs

   digraph blocks {
     rankdir=LR;
     compound=true;
     node [shape=box, style="rounded,filled", fillcolor="#f6f6f6",
           fontname="Helvetica", fontsize=9, margin="0.16,0.10"];
     edge [fontname="Helvetica", fontsize=8];
     graph [fontname="Helvetica", fontsize=10, style=filled, fillcolor="#fbfbfb"];

     registry_file [label="documents.yaml\n(consumer)", fillcolor="#e8eef7"];

     subgraph cluster_cmake {
       label="cmake/ — the consumer surface";
       zdocs_cm   [label="zdocs.cmake\nentry point"];
       common_cm  [label="common.cmake\nhelpers, add_doc_check"];
       registry_cm[label="registry.cmake\nadd_docs_from_registry"];
       sphinx_cm  [label="sphinx.cmake\nadd_sphinx_target"];
       doxygen_cm [label="doxygen.cmake\nadd_doxygen_target"];
     }

     subgraph cluster_scripts {
       label="scripts/";
       docrefs  [label="docrefs.py\nregistry reader"];
       doccheck [label="doccheck.py\nintegrity gate"];
       docctl   [label="docctl.py\ncontrolled documents"];
     }

     subgraph cluster_sphinx {
       label="sphinx/ — payload";
       conf   [label="zdocs_conf.py\nshared configure()"];
       exts   [label="_extensions/\nxref_builder, doc_control,\nqms_ref, latexinclude,\ntest_module + parsers"];
       tmpl   [label="_templates/, _static/"];
     }

     subgraph cluster_doxygen {
       label="doxygen/ — payload";
       theme  [label="doxygen-awesome theme,\nzdocs CSS"];
       nav    [label="header/footer,\ncross-doc-nav"];
     }

     registry_file -> docrefs [label="read by"];
     zdocs_cm   -> common_cm  [style=dotted, label="includes"];
     registry_cm -> sphinx_cm  [label="dispatches"];
     registry_cm -> doxygen_cm [label="dispatches"];
     registry_cm -> docrefs   [label="manifest"];
     sphinx_cm  -> conf       [label="ZDOCS_CONF_DIR"];
     conf       -> docrefs    [label="imports"];
     conf       -> exts;
     conf       -> tmpl;
     doxygen_cm -> theme      [label="HTML_EXTRA_*"];
     doxygen_cm -> nav;
     doccheck   -> registry_file [style=dashed, label="checks set against"];
   }

``cmake/`` — the consumer surface
---------------------------------

``zdocs.cmake`` is the entry point a consumer includes; it pulls in the rest.
``registry.cmake`` reads the manifest and creates every document's targets,
plus the per-group aggregates. ``sphinx.cmake`` and ``doxygen.cmake`` are the
two document factories, each responsible for the two build stages of its
toolchain. ``common.cmake`` holds shared helpers and the ``doc-check`` target.
Two further modules are ``cmake -P`` wrappers invoked at **build** time rather
than configure time — one runs Doxygen with a freshly resolved version number,
the other downloads a remote peer's tag file.

``scripts/`` — registry, gate, controlled documents
---------------------------------------------------

``docrefs.py`` is the only reader of the registry, and every derived value —
intersphinx mappings, tag file lists, navigation entries, needs imports,
document manifests — comes out of it, whether the caller is CMake or a
``conf.py``. ``doccheck.py`` is the integrity gate that runs after a full
build. ``docctl.py`` is a standalone command-line tool for controlled-document
transitions, and is the one part of the engine that touches no build at all.

``sphinx/`` — the Sphinx payload
--------------------------------

``zdocs_conf.py`` is what a consumer's ``conf.py`` shim calls: it assembles the
whole configuration, including the engine's extension list, and appends the
consumer's own extensions rather than being replaced by them. The extensions
divide into presentation (``doc_control``, ``qms_ref``, ``latexinclude``),
build machinery (``xref_builder``, which provides the stage-one index builder)
and the test-specification block (``test_module`` with its Doxygen XML parser,
twister reader and rST builders).

``doxygen/`` — the Doxygen payload
----------------------------------

A vendored theme, the engine's own stylesheet, and the header/footer plus
cross-document navigation widget that give a Doxygen document the same sidebar
its Sphinx peers have.

Where a document's data comes from
----------------------------------

Every consumer-supplied fact enters through one of exactly three doors: the
``ZDOCS_*`` CMake variables, the registry, or the document's own sources. There
is no fourth, and adding one is the mistake this architecture keeps having to
resist — a per-document value that the registry could already derive.
