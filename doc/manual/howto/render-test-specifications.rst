Rendering test specifications from annotated source
========================================================

You have a Sphinx document that should render sphinx-needs test cases
straight from Doxygen-annotated ``ZTEST`` sources, and (optionally) a second
document correlating those cases against a real Twister run. This is the
recipe; the mechanism is :doc:`../explanation/testmodule-and-twister` and the
directive/role reference is :doc:`../reference/directives-and-roles`. The
``testmodule`` sample tree (``zdocs-tests/samples/testmodule``, with its own
``README.md``) is a complete, working instance of every step below.

1. Enable Doxygen XML for the project
------------------------------------------

.. code-block:: yaml

   doxygen_xml: true

Top-level, project-scoped — every ``kind: doxygen`` document generates XML,
not just the one you care about. Required: without it, ``testmodule`` finds an
empty XML directory, which looks like a parser fault and is not one.

2. Opt in on the specification document
---------------------------------------------

.. code-block:: yaml

   documents:
     spec:
       kind: sphinx
       builders: [html]
       testmodule:
         doxygen_source: dox-checks   # kind: doxygen — its XML gets parsed
         api_reference: dox-api       # optional — where @see resolves to

The block's presence is the entire opt-in: a document without it never loads
the extension at all. Both ids are validated at configure time — a typo or a
non-``doxygen`` target is a hard error naming this document, not a silently
empty page. ``dox-checks`` and ``dox-api`` are this project's own choice of
id, not an engine requirement — an id is taken verbatim, so ``checks`` and
``api`` would work exactly as well; the ``dox-`` here is written into the id
because that project wants it in the folder name, the target name and the
published URL.

3. Annotate the Doxyfile
----------------------------

Two additions to the ``kind: doxygen`` document's ``Doxyfile.in`` are easy to
miss:

.. code-block:: text

   ALIASES     += "testid{1}=\xrefitem testids \"Test ID\" \"Test IDs\" \1"
   ALIASES     += "reqref{1}=\xrefitem reqrefs \"Requirement\" \"Requirements\" \1"
   PREDEFINED  = "ZTEST(suite, fn)=/** \ingroup suite */ void fn(void)" \
                 "ZTEST_SUITE(suite, predicate, setup, before, after, teardown)="

The alias *names* are yours; the ``\xrefitem`` keys (``testids``, ``reqrefs``)
are matched by the parser and must be spelled exactly. Without
``PREDEFINED`` macro expansion, every ``ZTEST`` is documented as a function
literally named ``ZTEST`` — expanding it also injects ``\ingroup suite`` from
the macro's own argument, which is what attaches a test case to its suite
without a hand-written (and driftable) ``@ingroup``.

4. Declare the needs vocabulary
------------------------------------

Everything the directives emit — three need types (case/procedure/result),
three link types, and up to nine custom fields — must be declared in
``needs_config.toml`` (``ZDOCS_NEEDS_CONFIG``), or sphinx-needs rejects the
need with an ``Unknown option``/``Unknown need type`` warning per occurrence.
Renaming the three roles away from the engine defaults, if you want project
vocabulary rather than ``test_case``/``verifies``/etc., is a matching pair of
``conf.py`` dicts — see :doc:`../reference/directives-and-roles`.

5. Write the directive
---------------------------

.. code-block:: rst

   .. testmodule:: widget_probe_module
      :module: checks/widget/probe

The argument is the Doxygen **module** group's name, never a suite; ``:module:``
is a project-relative path used only to find that module's ``testcase.yaml``
for the scenario table.

6. Add the report half (optional)
---------------------------------------

.. code-block:: yaml

     report:
       kind: sphinx
       builders: [html]
       testmodule:
         spec: spec                 # whose needs.json to correlate against
         doxygen_source: dox-checks
         api_reference: dox-api

.. code-block:: rst

   .. testreport:: twister_report.xml
      :module: widget.probe

   .. twisterinfo:: twister.json

Point ``ZDOCS_TWISTER_OUT`` at a real ``west twister`` output directory
(``-DZDOCS_TWISTER_OUT=$(west topdir)/twister-out``). Leaving it unset is
supported: both directives render a "not found" note and the build still
succeeds, since a docs build legitimately outrunning its test run is a normal
pipeline state. ``spec:`` is what lets the two ordering edges between the
report and its specification (a stage-1 needs-export race, and a stage-2
Doxygen-XML race) resolve automatically — nothing about them is hand-wired.
