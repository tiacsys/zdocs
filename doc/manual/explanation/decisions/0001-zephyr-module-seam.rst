0001. zdocs is a Zephyr module, included by name
=================================================

Status
------

Accepted.

Context
-------

Zephyr already has a mechanism for shipping reusable CMake to a consuming
project — the module system — and every intended consumer of this engine is
already a Zephyr workspace. The question was therefore not *whether* to be a
Zephyr module but *how* a consumer reaches the engine's CMake surface once it
is one.

The obvious route does not work. ``find_package(Zephyr COMPONENTS doc)`` is a
reduced flow: it does not reliably run a module's own ``CMakeLists.txt``, so a
module cannot count on being able to define its functions that way.

Decision
--------

zdocs is a Zephyr module whose CMake is consumed **by name, not by path**:

.. code-block:: cmake

   list(APPEND CMAKE_MODULE_PATH ${ZEPHYR_ZDOCS_MODULE_DIR}/cmake)
   include(zdocs)

Zephyr's module system sets ``ZEPHYR_ZDOCS_MODULE_DIR`` when it loads the
module, whether the module is a project of the active west manifest or is
supplied out-of-tree with ``EXTRA_ZEPHYR_MODULES``. The consumer therefore
never writes a path into the engine.

Everything the engine needs from the consuming project arrives through the
``ZDOCS_*`` variables (see :doc:`../../reference/consumer-contract`), set
*before* ``include(zdocs)``. The engine ships no project-specific default and
guesses nothing: a missing ``ZDOCS_PROJECT_BASE`` is a fatal error at
configure time, not a silently-wrong path at build time.
