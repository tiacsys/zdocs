Your first document
======================

This tutorial builds one Sphinx :term:`document`, on its own, in a Zephyr
module — from an empty folder to a rendered page. Nothing here touches the
:term:`registry`; that arrives in :doc:`cross-reference-two-documents`, once
there is a second document worth linking to.

Prerequisites
----------------

A west workspace with zdocs available as a module (either listed in your
manifest, or passed with ``EXTRA_ZEPHYR_MODULES`` below), and the packages in
``tools/zdocs/sphinx/requirements-doc.txt`` installed.

Lay out the document
------------------------

.. code-block:: console

   $ mkdir -p doc/runbook

``doc/runbook/conf.py``:

.. code-block:: python

   import os
   import sys
   from pathlib import Path

   sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])
   from zdocs_conf import configure

   configure(
       globals(),
       doc_dir=Path(__file__).resolve().parent,
       project="My Runbook",
   )

``ZDOCS_CONF_DIR`` is exported by the engine on every ``sphinx-build`` it
launches; this is how a ``conf.py`` finds :external+zdocs-api:py:func:`zdocs_conf.configure`
without the engine being installed as a Python package. Everything about your
document's identity — its project name, its theme, its two-stage build — comes
from that one call.

``doc/runbook/index.rst``:

.. code-block:: rst

   My Runbook
   ==========

   Nothing here yet.

Write the build description
--------------------------------

``doc/CMakeLists.txt``:

.. code-block:: cmake

   cmake_minimum_required(VERSION 3.20.0)
   project(my-doc LANGUAGES)

   find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE} .. COMPONENTS doc)

   if(NOT DEFINED ZEPHYR_ZDOCS_MODULE_DIR)
     message(FATAL_ERROR
       "zdocs module not found. Pass it with -DEXTRA_ZEPHYR_MODULES=<path to zdocs>.")
   endif()

   get_filename_component(MY_PROJECT_BASE ${CMAKE_CURRENT_LIST_DIR}/.. ABSOLUTE)
   set(ZDOCS_PROJECT_BASE ${MY_PROJECT_BASE})

   list(APPEND CMAKE_MODULE_PATH ${ZEPHYR_ZDOCS_MODULE_DIR}/cmake)
   include(zdocs)

   add_sphinx_target(runbook BUILDERS html)

``ZDOCS_PROJECT_BASE`` is the one variable :doc:`../reference/consumer-contract`
calls required, and it has to be set *before* ``include(zdocs)`` — the engine
checks for it immediately. The folder name (``runbook``) is what ties
``add_sphinx_target``'s first argument to ``doc/runbook/``; nothing else in
this file names it twice.

Build it
------------

.. code-block:: console

   $ cmake -S doc -B build -DEXTRA_ZEPHYR_MODULES=<path to zdocs>
   $ cmake --build build

Open ``build/deploy/html/runbook/index.html``. That is the whole tutorial:
one document, one :term:`builder`, no registry, no cross-references — the
smallest thing zdocs can build.

What's next
--------------

A real project rarely stops at one document.
:doc:`add-a-doxygen-document` adds a second one, from the other toolchain, the
same standalone way; :doc:`cross-reference-two-documents` then wires the two
together with a registry, which is where navigation and cross-references
actually come from.
