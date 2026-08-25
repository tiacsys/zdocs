Building these docs
====================

This page builds the very :term:`document set` you are reading — the
``manual``/``api`` pair declared in ``tools/zdocs/doc/documents.yaml`` and
built through the engine's own public CMake surface, exactly like any other
:term:`consumer`.

Install the Python requirements
--------------------------------

.. code-block:: console

   $ pip install -r doc/requirements.txt

That file is this docset's own dependency list — the engine's
``sphinx/requirements-doc.txt`` plus ``sphinxcontrib-moderncmakedomain``, which
only this docset needs (it extracts the CMake API reference from bracket
comments in the ``.cmake`` sources; see :doc:`../explanation/architecture/crosscutting`
and :doc:`../reference/consumer-contract`). It is deliberately not folded into
the engine's own requirements file, which every other consumer also installs.

You also need `Graphviz <https://graphviz.org/>`_'s ``dot`` binary on
``PATH`` — not a Python package, so ``pip`` cannot install it. The two
architecture pages under :doc:`../explanation/architecture/index` render their
C4-style diagrams with ``.. graphviz::`` from source, and the build fails
without it.

Configure and build
--------------------

.. code-block:: console

   $ cmake -S tools/zdocs/doc -B <build> -DEXTRA_ZEPHYR_MODULES=$PWD/tools/zdocs
   $ cmake --build <build>

``ZDOCS_PROJECT_BASE`` is set inside ``doc/CMakeLists.txt`` to the engine's own
repository root — the one place this docset's build description differs from
an ordinary consumer's, because here the engine *is* the consuming project.

The default target is ``all-docs``, which builds both documents' ``html``
:term:`builder` and then runs the ``doc-check`` integrity gate
(:doc:`../reference/cli`) automatically as a post-build step — an ordinary
build is already checked; you do not need a separate command for that.

Where the output lands
------------------------

.. code-block:: text

   <build>/deploy/html/manual/index.html
   <build>/deploy/html/api/index.html

See :doc:`../explanation/deploy-layout` for the full shape. Neither document
declares a ``latex`` builder, so this docset produces no PDF.

Rebuilding after an edit
--------------------------

.. code-block:: console

   $ cmake --build <build> --target manual-html-nodeps

The ``-nodeps`` variant skips the stage-1 cross-reference rebuild, which is
safe for an edit confined to prose — anything that changes what one document
exports to the other (a new label, a new API symbol) needs a plain
``manual-html``/``api-html`` (or ``all-docs``) instead, so the peer's index is
current before the render that reads it.
