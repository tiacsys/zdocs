0010. The engine payload is split by tool, freeing ``doc/`` for documentation
=============================================================================

Status
------

Accepted.

Context
-------

The engine shipped its Sphinx configuration, its Sphinx extensions, its
templates and static files, its vendored Doxygen theme and its Doxygen
header/footer all inside a folder called ``doc/``.

Inside the engine they are not documentation at all. They are payload — the
files the engine hands to Sphinx and to Doxygen when it runs them. Meanwhile
the one folder an engine's own documentation would naturally live in was
occupied, and the CMake modules that drive the two toolchains
(``sphinx.cmake``, ``doxygen.cmake``) had no structural counterpart in the
payload they configure.

Decision
--------

Split the payload by **tool**, mirroring the CMake modules:

``sphinx/``
   The shared Sphinx configuration, the extensions (including their unit
   suite), templates and static files.

``doxygen/``
   The vendored Doxygen theme, header and footer, and the cross-document
   navigation widget.

``doc/``
   Freed, and left deliberately empty, for the engine's own documentation.

Consequences
------------

- **The underscore prefixes stayed, and the nesting depth was preserved
  exactly.** The extension test tree sits at the same depth it did before, so
  the fixed ``parents[N]`` indices in its configuration needed no edit. If one
  of those ever needs editing, a file is in the wrong place — fix the layout,
  not the index.
- Only three bindings pointed into the old tree, which is what made the move
  cheap: two CMake variables and one hardcoded test path. Every consumer
  document reaches the engine's Sphinx configuration through an environment
  variable and needed nothing.
- One variable was **deleted rather than updated**: it was set and never read
  anywhere in either repository. A rename is the moment to notice that.
- **A configure does not verify this kind of change.** A wrong payload path
  survives configure and only fails when the tool runs — and for the Doxygen
  half, only in the rendered output. The check that mattered was building a
  full sample end to end and confirming the theme files landed in the HTML.
- The engine's documentation, which this decision made room for, is the
  docset you are reading (:doc:`0011-documentation-structure`).
