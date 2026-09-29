From annotated C to a test report
=================================

The longest chain in the engine turns C source into rendered, traceable test
documentation. Nothing along it is hand-written twice: the test cases come from
the same comments that live beside the code, and the results come from the test
runner's own output.

The chain
---------

.. code-block:: text

   annotated C  ->  Doxygen XML  ->  test specification  ->  test report
   (ztest suite)    (deploy/xml)     (spec needs)            (result needs)
                                          ^                       ^
                                    requirements            twister output

Four stages, each a different tool's output feeding the next:

1. **Annotated C.** A ztest suite carries Doxygen comments naming what each
   test verifies. The requirement ids it references are ordinary cross
   references — a dangling one warns.
2. **Doxygen XML.** The Doxygen document over that source emits XML into the
   non-servable part of the deploy tree
   (:doc:`decisions/0007-engine-managed-doxygen-xml`).
3. **The test specification.** A directive parses that XML *at parse time* and
   emits one need per test case, plus the procedure prose from the enclosing
   group's documentation.
4. **The test report.** Further directives read the test runner's output
   directory, correlate each result against the specification's needs, and emit
   result needs linked back to the cases they report on.

The names are the consumer's
----------------------------

Every need type and every link name in that picture is supplied by the
consuming project, not by the engine
(:doc:`decisions/0009-need-type-role-mapping`). The engine thinks in roles —
case, procedure, result, and the three links between them — and resolves each
role to whatever the project's quality system calls it.

This is the single most defect-prone thing about the chain, and the failure is
always the same: a place that emits or queries a **literal** name instead of a
mapped one produces an empty result with a clean exit. Correlation against a
project's own names comes back empty; a generated table renders with no rows.
Nothing errors, because nothing is wrong — there simply are no matches.

Two failure modes, deliberately different
-----------------------------------------

The specification half and the report half fail differently, on purpose:

- **A missing specification is a hard failure.** Its input is Doxygen XML
  produced by this very build; if it is absent, the build is wrong.
- **A missing test report is a normal state.** Its input is a test run that may
  legitimately not have happened yet — a documentation build can outrun its
  test run. The directives render a "not found" node and the build succeeds.

The soft-fail path is published, which makes it subject to the same rule as
every other rendered node: it names the file it looked for, never the absolute
path it looked in. A diagnostic is not an excuse to leak the build host's
layout into a published page — the log is where the full path belongs.

Ordering
--------

Because the report reads needs published by the specification, and both are
ordinary documents in the set, the build needs edges between them. Those edges
are **derived from the registry** — the report's own ``testmodule:`` block
already names the specification it reads — rather than hand-written by the
consumer, which would duplicate what the registry knows.

Parameterized tests
-------------------

A ztest ``ZTEST_P`` function runs once per parameter value, and twister
reports it twice over: one aggregate result, ``<scenario>.<suite>.<fn>``, from
ztest's summary line, and one result per value,
``<scenario>.<fn>[<instantiation>/<value>]`` — with no suite segment. The
specification documents the function once, so the report does too: each value
result is attached to the aggregate of the same run (platform and scenario),
and the aggregate's result need carries them. Its status comes from the
values — failed if any failed, skipped if all were skipped, passed if every
value that ran passed — and its body counts them ("9 values: 8 passed, 1
failed") and tabulates only the values that did not pass, with the assertion
each one failed on.

The aggregate's own status is not trusted for this. When one value fails,
ztest summarises the function as ``FLAKY``, which twister does not recognise:
it records the aggregate as ``blocked`` in ``twister.json`` and as a generic
"Testsuite failed" in the XML, and only the failing value's result carries the
real assertion. Where twister's status for the aggregate disagrees with the
values' verdict, the need says so ("Twister reported the test as
``blocked``").

A run whose values have no aggregate at all borrows the suite from other runs'
aggregates of the same scenario and function, or else from the specification
if exactly one test case has that function name. Values that match neither are
skipped with one warning per function, not one per value.

Where the test runner writes
----------------------------

The output directory is a build-time value, read from the environment on each
invocation rather than frozen when the project was configured, so a rebuild
picks up a newer test run without reconfiguring. Note that the runner writes
relative to the current working directory and rotates previous runs out of the
way, so a stable configured path sees the newest results — except under the
runner's own flags for keeping or deleting old output, where it may not.
