Running the test suites
==========================

zdocs has two test suites, in two repositories, exercising different layers.
Neither substitutes for the other:
:doc:`../explanation/decisions/0002-acceptance-tests-in-a-consumer-repo` and
:doc:`../explanation/decisions/0003-engine-unit-suite` record why.

The engine's own unit suite
------------------------------

In the zdocs repository, no build tree and no west workspace required:

.. code-block:: console

   $ python3 -m pytest sphinx/_extensions/_tests -q

Pure-Python tests over the Sphinx extensions (``doxygen_parser``,
``rst_builders``, ``twister_reader``, ``test_module``, and their need-type
mapping) run in-process against fixture XML/JSON — no Sphinx build, no
Doxygen, no CMake. It runs in about a second, which is what makes it the right
tool for iterating on extension logic; it proves nothing about CMake wiring or
about what actually lands in rendered HTML.

The acceptance suite
------------------------

Lives in a separate repository (``zdocs-tests``, referred to in its own
tests as "ACME") that consumes zdocs the way a real project does: real
``cmake``/``sphinx-build``/``doxygen`` invocations, assertions on rendered
output in ``deploy/``, never on configuration or exit codes alone.

.. code-block:: console

   $ python3 -m pytest tests/ -q

Needs a west workspace (``zdocs_conf`` loads Zephyr's own Sphinx extensions)
and the packages in ``tools/zdocs/sphinx/requirements-doc.txt``. Two things
have to be true before it will pass:

- **Two annotated git tags** in the ``zdocs-tests`` repository
  (``widget/v2.3``, ``handbook/v1.4``) that the version-scope tests resolve
  against. Each has its own guard test, so a missing tag reads as "recreate
  the fixture" rather than as an engine defect — the suite's own ``README.md``
  has the exact ``git tag`` commands.
- **``zdocs`` reachable as a Zephyr module**, either because the active west
  manifest already lists it, or by passing it explicitly:

  .. code-block:: console

     $ cmake -B <build> -S tests/fixtures/doc-canonical \
         -DEXTRA_ZEPHYR_MODULES=<workspace>/tools/zdocs

The suite is deliberately cumulative rather than one isolated fixture per
feature (``tests/fixtures/doc-canonical`` is *everything* every prior step
added, not a fresh minimal case each time) — the engine's defects have
historically been interactions between documents, which an isolated
per-feature fixture would hide. Budget on the order of two minutes for a full
run; it configures and builds a complete two-stage docset more than once.

Which one to run
-------------------

Changed an extension's Python logic with no new CMake wiring or registry
field? The unit suite catches it in a second — run that first. Changed
anything a consumer would notice (a new ``ZDOCS_*`` variable, a registry
field, a CMake target, cross-document link behaviour)? Only the acceptance
suite builds real output to assert against; run it before calling the change
done.
