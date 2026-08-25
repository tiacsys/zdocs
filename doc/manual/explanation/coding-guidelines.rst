Engineering guidelines
======================

The conventions this engine is built under, stated as norms. They are not
style preferences — each one exists because its absence produced a real defect,
usually a silent one. See :doc:`documentation-guidelines` for the equivalent
conventions covering prose, and :doc:`architecture/crosscutting` for the
architectural concerns several of these support.

Testing
-------

- **Write the acceptance test first, and make sure it fails for the intended
  reason.** A test that fails because a fixture died before the assertion ran
  tells you nothing about the assertion. Distinguish a *failure* from an
  *error* before believing the red: a cascade of errors and a wall of correct
  failures look equally red and are not equally informative.
- **One cumulative fixture, not isolated per-feature trees.** Step *N*'s
  fixture is everything the previous steps added — see
  :doc:`decisions/0002-acceptance-tests-in-a-consumer-repo`.
- **Assert rendered output, never configuration.** A generated doxyfile with
  the right ``TAGFILES`` line proves nothing; that was the exact state of the
  world when cross-referencing was broken. Follow hrefs to files on disk.
- **Never trust an exit code alone.** Two silent successes are on record: a
  module supplied under the wrong variable name configures cleanly and is
  simply absent, and a failed registry script once left the tag file list empty
  while the build went green.
- **Verify against the tool, with a control.** "Longest prefix wins" was
  established by also running the case that should lose. One observation is not
  a result.
- **Some defects are only visible after layout.** Valid HTML plus valid CSS
  that disagree by twenty-two pixels is not reachable from either file; the
  suite drives a headless browser and asserts on geometry rather than on
  stylesheet text.

Engine boundaries
-----------------

- **Project-specific values are consumer inputs, never engine constants.**
  Anything naming one company, one product or one upstream project belongs in
  the ``ZDOCS_*`` contract or the registry. Reading a key out of a tool's own
  output schema is not branding; reading a host environment variable named
  after one project is.
- **No engine module is included ahead of the test that exercises it.**
- **Fail loudly at configure time rather than degrade at build time.** A
  missing required variable, a missing module or an unparseable registry is a
  fatal error carrying a message that names the fix.
- **The engine owns its tool discovery.** Relying on the consumer to find
  Doxygen worked by accident and then failed as a permission error.
- **Engine markup may not depend on consumer CSS.** Branding is optional and
  must never be load-bearing: the header has to render correctly with none of
  it set. Both header defects found so far were exactly this.

CMake
-----

- ``CMAKE_CURRENT_LIST_DIR`` inside a function is the **caller's** directory.
  Use it for consumer-owned paths and ``CMAKE_CURRENT_FUNCTION_LIST_DIR`` for
  everything the engine ships.
- ``if(<var>)`` asks whether a value is *true*, not whether it was *given*.
  ``0``, ``OFF``, ``NO``, ``FALSE`` and anything ending in ``-NOTFOUND`` all
  read as false, so an optional string argument tested that way silently falls
  back to its default. Test with ``NOT x STREQUAL ""``.

Python
------

- The rST-building modules must not import Sphinx or read the application
  configuration; anything they need is passed in. Their unit tests call them
  bare.
- Module-level docstrings are the API reference — they are rendered into the
  companion API document, so write them for a reader who has not seen the code.

Build hygiene
-------------

- Scratch space here is often a RAM-backed filesystem, and a full documentation
  build peaks well over a gigabyte. Cap parallelism, delete build trees when
  done, and treat an unbounded ``-j`` as a way to lose the host.
