Adding a Doxygen document
============================

Continuing from :doc:`first-docset`: the same project, one more document, this
time from the other toolchain — still standalone, with no registry and no
cross-references to the ``runbook`` document from the previous tutorial. That
comes in :doc:`cross-reference-two-documents`.

Lay out the document
------------------------

A Doxygen document's folder is named for its id, the same as a Sphinx
document's:

.. code-block:: console

   $ mkdir -p doc/widget

``doc/widget/mainpage.md``:

.. code-block:: markdown

   # Widget API

   Doxygen document for the widget API.

``doc/widget/Doxyfile.in``:

.. code-block:: text

   PROJECT_NAME           = "Widget API"
   PROJECT_BRIEF          = "The widget API"

   OUTPUT_DIRECTORY       = @DOXY_OUT@
   CREATE_SUBDIRS         = NO

   INPUT                  = @DOXY_SRC_DIR@/mainpage.md \
                            @MY_PROJECT_BASE@/api/widget.h

   USE_MDFILE_AS_MAINPAGE = @DOXY_SRC_DIR@/mainpage.md
   RECURSIVE              = YES
   FILE_PATTERNS          = *.h *.c

   EXTRACT_ALL            = YES
   OPTIMIZE_OUTPUT_FOR_C  = YES

   GENERATE_HTML          = YES
   GENERATE_LATEX         = NO

``configure_file(... @ONLY)`` substitutes ``@DOXY_OUT@`` and ``@DOXY_SRC_DIR@``
— engine-provided — and ``@MY_PROJECT_BASE@``, which is *your* CMake variable
from :doc:`first-docset`'s ``CMakeLists.txt``, referenced here exactly the way
you'd reference any of your own. Nothing about ``HTML_OUTPUT``,
``GENERATE_TAGFILE`` or ``GENERATE_XML`` belongs in this file: the engine
appends all three itself, after this template is expanded, and a line setting
one here would simply be discarded — see
:doc:`../reference/registry-schema`'s list of engine-owned Doxyfile keys.

Point it at some real input — an ``api/widget.h`` with a documented function
or two, anywhere Doxygen's ``FILE_PATTERNS``/``INPUT`` above will find it.

Add the target
------------------

One line in ``doc/CMakeLists.txt``, after the ``add_sphinx_target`` call from
:doc:`first-docset`:

.. code-block:: cmake

   add_doxygen_target(widget)

The factory's argument is the document's id (``widget``); it derives the
source folder (``doc/widget/``) and the deploy path
(``deploy/html/widget/``) from it directly, with nothing prepended. If you
wanted a ``dox-`` prefix on the folder, the target name and the deploy path,
you would write it into the id itself and call
``add_doxygen_target(dox-widget)`` against a ``doc/dox-widget/`` folder —
the engine holds no opinion either way.

Build it
------------

.. code-block:: console

   $ cmake --build build

``all-docs`` now builds both documents. Open
``build/deploy/html/widget/index.html`` alongside
``build/deploy/html/runbook/index.html`` from the previous tutorial — two
independent documents, from two different toolchains, in one build, still with
no link between them: each one's navigation and cross-reference machinery only
activates once a registry names them as peers.

What's next
--------------

:doc:`cross-reference-two-documents` introduces ``documents.yaml`` and turns
these two standalone documents into a proper :term:`document set`: a shared
navigation sidebar, and a real cross-reference from the Sphinx document into
the Doxygen one.
