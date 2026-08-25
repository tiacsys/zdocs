0003. The engine carries its own unit suite, in the engine repository
======================================================================

Status
------

Accepted.

Context
-------

The test-module and twister extensions is roughly 1170 lines of
pure Python code — a Doxygen XML parser, a twister result reader,
two reStructuredText builders and a directive module. Unlike the CMake surface,
none of it needs a documentation build to exercise: it transforms XML and JSON
into rST and needs objects.

Putting those tests in the acceptance repository would have been wrong.
They would have run in minutes rather than in under a second, for code
whose failures are not interaction failures.

Decision
--------

The engine carries a **second, fast unit suite in its own repository**, at
``sphinx/_extensions/_tests/``, covering the pure-Python extension modules.

There are therefore two suites in two repositories:

.. code-block:: console

   $ cd tools/zdocs && python3 -m pytest sphinx/_extensions/_tests -q   # fast
   $ cd zdocs-tests && python3 -m pytest tests/ -q                      # acceptance

Neither layer can contaminate the other's count, and the engine becomes
independently testable without a consumer.
