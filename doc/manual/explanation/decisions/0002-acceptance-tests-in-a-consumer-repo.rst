0002. Acceptance tests live in a consumer repository, over one cumulative fixture
=================================================================================

Status
------

Accepted.

Context
-------

Every defect this engine has had was an **interaction**, not a unit failure: a
tag file that was computed correctly but never wired into the doxyfile that
needed it; a Sphinx role that resolved at parse time against an index which did
not exist yet; a doctree cache shared between two build stages that answered
for work never redone. In each case every component was individually correct
and the assembled documentation set was wrong — and in most of them the build
exited 0 while producing a complete-looking docset with dead cross-references.

Unit tests over the engine's Python modules cannot see that class of defect at
all. Neither can a per-feature fixture that builds one document in isolation:
the interaction only exists when two documents, two toolchains, and two build
stages are present at once.

Decision
--------

The engine's primary test layer is an **acceptance suite in a separate
repository** called which consumes zdocs exactly as a real project would — a Zephyr
workspace with its own documents, its own registry, and its own vocabulary. It
configures and builds with the same ``cmake`` commands a user runs, and asserts
on what lands in ``deploy/``. There are no mocks and no in-process Sphinx.

Consequences
------------

- The suite is slow by unit-test standards — minutes, not seconds — because
  every test builds real documentation with real Sphinx and real Doxygen. That
  cost buys the only signal that matters for this engine, and it is why a
  second, fast unit layer was later added for the pure-Python parts
  (:doc:`0003-engine-unit-suite`).
