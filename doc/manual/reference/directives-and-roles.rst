Directives and roles
=====================

What a document author writes in RST. Every directive here is loaded for
every document by :external+zdocs-api:py:func:`zdocs_conf.configure`, whether
or not the document uses it — an extension list that varied by document would
make the two build stages' configuration differ and invalidate the shared
doctree cache. The ``testmodule``/``testreport``/``twisterinfo`` directives and
``symbolneeds`` are the exceptions: they load only for a document whose
registry entry carries a ``testmodule:`` or ``symbol_needs:`` block
(:doc:`registry-schema`).

``.. doc_control::``
--------------------

The controlled-document header table: owner, classification, approval dates,
version, supersession. Source:
:external+zdocs-api:py:class:`doc_control.DocCtrlDirective`.

.. code-block:: rst

   .. doc_control::
      :owner: Quality Team
      :classification: SOP
      :author: Jane Doe <jane@example.com>
      :approved_by: John Roe <john@example.com>
      :approval_date: 2026-01-15

``owner`` is the only required option. Everything else defaults to a
placeholder string (``"not-authored-yet"``, and similarly for
``reviewed_by``/``approved_by``) so the table always renders a complete row set
even for a document nobody has touched yet — these placeholders are computed
at build time, never written back into the source; ``docctl`` (:doc:`cli`) is
what edits the source.

``version`` defaults to the document's resolved git-tag version (the same
value shown in the sidebar) rather than requiring it to be typed twice;
``:version:`` overrides it. ``classification`` is checked against
``doc_control_classifications`` (a ``conf.py`` config value, default a list of
eight QMS-flavoured terms — ``"SOP"``, ``"Record"``, ``"Policy"``, and so on);
set it to your own vocabulary in ``conf.py``, or to an empty list to accept
anything.

Two further ``conf.py`` values control PDF-only behaviour: ``signature_section``
(``"none"`` default, or ``"top"``/``"bottom"`` to insert a sign-off block with
ruled lines for Author/Reviewer/Approver, pre-filled from this directive's own
fields where set) and ``releaselevel`` (default ``"next"``, read by
``sphinx.ext.ifconfig`` for ``.. ifconfig:: releaselevel not in (...)`` blocks).
Neither has any effect in HTML.

``:qmsdoc:`` role
-----------------

References a ``kind: external``/``sphinx-external``/``doxygen-external``
registry document by id — the only way to link to one, since it has no local
Sphinx label and (for plain ``external``) is deliberately excluded from
intersphinx (there is no ``objects.inv`` to fetch). Source:
:external+zdocs-api:py:class:`qms_ref.QmsDocRole`.

.. code-block:: rst

   See :qmsdoc:`sop-swdp` for the full procedure.
   See :qmsdoc:`SOP-SWDP <sop-swdp>` for the full procedure.

Renders as a real hyperlink for HTML, and as plain text for every other
builder (a PDF has no notion of a live web link). Referencing an id that is
not a ``documents.yaml`` entry of one of those three kinds is a build error at
the point of use.

``.. latexinclude::``
----------------------

Includes another RST file, for the ``latex`` builder only — a no-op everywhere
else. For content that has to travel with a PDF because a printed document
carries no hyperlinks: a shared glossary, a terms appendix. Source:
:external+zdocs-api:py:class:`latexinclude.LatexIncludeDirective`.

.. code-block:: rst

   .. latexinclude:: ../_glossary_terms.rst

The path is resolved relative to the file **as you wrote it**, not to the
generated build tree ``external_content`` copies sources into — the directive
reconstructs your authored directory from ``confdir`` and ``docname``
specifically so that ``..`` means what it looks like it means. A missing file
is a build error naming the resolved path, not a silently empty include.

``.. testmodule::``, ``.. testreport::``, ``.. twisterinfo::``
------------------------------------------------------------------

The chain from annotated ztest C source to a rendered, traceable test report
— see :doc:`../explanation/testmodule-and-twister` for the mechanism and
:doc:`../howto/render-test-specifications` for a worked recipe. Source:
:external+zdocs-api:py:mod:`test_module`.

.. code-block:: rst

   .. testmodule:: widget_probe_module
      :module: checks/widget/probe

``testmodule``'s argument is a Doxygen ``@defgroup`` name (the *module* group,
never a suite or a path); ``:module:`` is a project-relative path used only to
locate that module's scenario file for the rendered scenario table: the first
of ``testcase.yaml``, ``tests.yaml`` and ``sample.yaml`` that exists. Every
``ZTEST``/``ZTEST_SUITE``/... in the named group and its inner suite/procedure
groups becomes one need each — nothing is written by hand per test case.

The Source line of a test case or a procedure (``main.c (line 290)``) links
to the Doxygen source listing of its file, at that line, if the test
specification's Doxyfile sets ``SOURCE_BROWSER = YES``. zdocs reads the
setting from the ``Doxyfile.xml`` that Doxygen writes beside the XML. Without
the listings, the Source line links to the member's documentation in the
group page.

A test case need's ``suite`` field is its inner suite group's name, so name
that group after the ``ZTEST_SUITE``: ``testreport`` finds the test case for a
twister result by the pair (suite, function). Two test modules that declare the
same ztest suite (Zephyr's workq ``user_work`` and ``work_queue`` both declare
``workqueue_api``) cannot share one group, though, because then both module
pages render every test in it and the need ids collide. So give each module its
own group, and set a qualifier in the ``conf.py`` of the document that holds
the ``testmodule`` directives, after the ``configure()`` call:

.. code-block:: python

   testmodule_suite_qualifier = "__"

.. code-block:: c

   /** @defgroup kernel_workq_user_work_module__workqueue_api workqueue_api ZTest suite
    *  @ingroup kernel_workq_user_work_module */

The suite is the part of the group name after the qualifier's **last**
occurrence (here ``workqueue_api``). A group name without the qualifier is used
whole, and so is every name when the value is unset (the default, ``""``). The
qualifier splits only the Doxygen group name the suite is derived from. The
(suite, function) key a result is correlated by does not change, and it now
sees the real suite name, which is the point. The fallback id of a test case
without ``@testid``, ``testspec-<group>-<function>``, keeps the whole group
name: two modules may have a function of the same name in the same suite, and
their ids must not collide. A result of such a function is still ambiguous by
(suite, function), and ``testreport`` skips it with a warning, as it does for
any pair that two modules document.

.. code-block:: rst

   .. testreport:: twister_report.xml
      :path: tests/kernel/timer/timer_error_case

   .. twisterinfo:: twister.json

``testreport``'s and ``twisterinfo``'s arguments are filenames resolved
against ``ZDOCS_TWISTER_OUT`` (or the including document's own directory, as a
fallback, if that is unset) unless given as an absolute path.

``testreport`` selects which runs a page shows with two optional options:

``:path:``
   A test directory, exactly as twister records it in ``twister.json``'s
   testsuite ``path`` — relative to ``ZEPHYR_BASE``, e.g.
   ``tests/kernel/timer/timer_error_case`` (a test root outside the Zephyr
   tree reads ``../<project>/tests/...``). Compared exactly after normalising
   slashes, a leading ``./`` and a trailing ``/``; never as a prefix. The path
   comes from the ``twister.json`` beside the report XML (the XML has none), and
   each result is matched to its testsuite by platform and scenario name. If
   that ``twister.json`` is missing, the directive soft-fails to a "not found"
   paragraph like the other inputs.
``:module:``
   A scenario-name prefix, matched against the JUnit ``classname`` (the
   scenario itself, or ``<module>.`` followed by anything).

With both, a run must match both. With neither, the page shows every result in
the report. ``:path:`` is the one that identifies a test module: scenario
names do not follow directories upstream — tests/kernel/timer/timer_api runs
as ``kernel.timer``, a prefix of timer_error_case's ``kernel.timer.error_case``
— so ``:module:`` alone can put one module's results on another's page, where
the second page then fails with "A need with ID … already exists". The
execution-log section and the result summary follow the same selection, so a
page is consistent with itself.

A parameterized test (``ZTEST_P``) gets one result need per run, not one per
parameter value: the values' results are attached to the test's aggregate
result, which takes its status from them and lists the values that did not
pass (:doc:`../explanation/testmodule-and-twister`). No need type or field is
added for this; the values render in the need's body.

Each result also says whether its build met the test case's ``depends_on``
(the ``@kconfig_depends`` conditions below), and each skipped result why it was
skipped. Both are read from the run, not from the spec alone:

``depends_met``
   ``yes`` or ``no``: the case's conditions, all of which must hold, evaluated
   against the ``.config`` twister kept for that build
   (``<platform>/<toolchain>/<test path>/<scenario>/zephyr/.config`` under the
   report's directory). ``CONFIG_X`` and ``defined(CONFIG_X)`` are true when
   the symbol has a value (``=y``, a number, a string; not ``is not set``);
   ``!``, ``&&``, ``||`` and parentheses combine them. ``n/a`` when the case
   has no condition, the build's ``.config`` is not there, or a condition uses
   anything else (another macro, ``IS_ENABLED()``, a comparison): its value is
   not known from ``.config``, so none is guessed, and the build warns once per
   case and condition. A result that passed with ``no`` ran although its
   condition was false.
``skip_class``
   On skipped results only. ``build-only``: twister built the test but did not
   run it. ``platform``: a memory region overflowed, or the platform was
   filtered out. ``config``: ztest skipped it and ``depends_met`` is ``no``.
   ``unexplained``: anything else.

Both are set only where your ``needs_config.toml`` declares them (string
fields), under names you may choose, like the need types and links:

.. code-block:: python

   testreport_need_fields = {"depends_met": "depends_met", "skip_class": "skip_class"}  # defaults

Both directives **soft-fail** to a short "not found" paragraph
when their input is absent, rather than failing the build — a documentation
build outrunning its test run is a normal pipeline state. ``testmodule`` does
**not** soft-fail on a missing Doxygen group: annotated source is expected to
always be present, so a miss there is treated as a real error.

Two ``conf.py`` values let a project rename the three need types
(``case``/``procedure``/``result``) and three link types
(``verifies``/``result_of``/``covers``) the directives emit — the engine
thinks in roles, never in literal names:

.. code-block:: python

   testmodule_need_types = {"case": "probe", "procedure": "routine", "result": "outcome"}
   testmodule_need_links = {"verifies": "confirms", "result_of": "produced_by", "covers": "spans"}

Omit them entirely and you get the engine's own defaults
(``test_case``/``test_procedure``/``test_result``,
``verifies``/``result_of``/``covers``). Whatever names you choose, every one —
plus nine custom fields the directives attach to needs
(``test_function``, ``test_module``, ``suite``, ``suite_title``,
``platform``, ``scenario``, ``twister_id``, ``execution_time``, ``reason``) —
must be declared in your ``needs_config.toml``
(``ZDOCS_NEEDS_CONFIG``, :doc:`consumer-contract`), or sphinx-needs rejects the
need with an ``Unknown option``/``Unknown need type`` warning per occurrence.

Doxygen annotations feeding these directives use two custom Doxygen
``ALIASES`` your ``Doxyfile.in`` declares yourself (the alias *names* are
yours; the ``\xrefitem`` keys ``testids``/``reqrefs`` they expand to are what
the parser matches on, and must be spelled exactly):

.. code-block:: text

   ALIASES += "testid{1}=\xrefitem testids \"Test ID\" \"Test IDs\" \1"
   ALIASES += "reqref{1}=\xrefitem reqrefs \"Requirement\" \"Requirements\" \1"

A third alias is optional. ``@kconfig_depends{<condition>}`` records the
Kconfig condition a test case (or, with ``symbolneeds``, an API symbol) is
built under; the key ``kconfig_depends`` is what the parser matches, the titles
are yours and the first one labels the rendered line:

.. code-block:: text

   ALIASES += "kconfig_depends{1}=\xrefitem kconfig_depends \"Depends on\" \"Kconfig dependencies\" \1"

Every condition is kept verbatim (``(CONFIG_A && !CONFIG_B) || CONFIG_C``;
write a comma as ``\,``), once, in source order. It renders in the need's body
("Depends on: ``CONFIG_ASSERT``") on ``testmodule`` and ``symbolneeds`` needs,
and fills the optional field ``depends_on`` — the conditions joined with
``"; "`` — if, and only if, your ``needs_config.toml`` declares it. Declare it
as a string field:

.. code-block:: toml

   [needs.fields.depends_on]
   description = "Kconfig conditions the need depends on"
   nullable = true
   [needs.fields.depends_on.schema]
   type = "string"

Left undeclared, no need gets the field and nothing warns. Declared as an
``array``, it works only while no condition contains ``;``, ``|`` or ``,``,
where sphinx-needs splits an array value; a need with such a condition gets no
field and a warning instead.

.. code-block:: c

   /**
    * @reqref{DUTY_001}
    * @see acme_widget_init()
    * @kconfig_depends{CONFIG_WIDGET_PROBE}
    * @testid{WIDGET-PROBE-001}
    */
   ZTEST(widget_probe_suite, test_widget_reports_initial_value)
   {
       ...
   }

``.. testcoverage::``
----------------------

One ``adequacy`` need per requirement that a per-test coverage run can assess.
The verdict says if the requirement's own verifying tests run the code that
satisfies it. ``test_module`` loads the directive.

.. code-block:: rst

   .. testcoverage::
      :run: nightly-cov
      :layout: adequacy

The optional argument is the run directory. Without it, the directive reads
``ZDOCS_COVERAGE_OUT`` (:doc:`consumer-contract`). The run directory holds
``twister.json``, ``coverage/test_matrix.json`` and ``zephyr.sha``. The
``:run:`` option names the run in the need ids. Without it, the name is the
first tag (sorted) on the run commit. If the commit has no tag, the name is
the name of the run directory. The ``:layout:`` option sets the sphinx-needs
layout of each need.

The directive joins these inputs:

* The requirement's verifying test cases, through the ``verifies`` link of
  the case needs.
* The requirement's satisfying symbols, through the ``satisfies`` link of the
  implementation needs (``IMPL-<symbol>``, see ``symbolneeds``).
* The test cases that the run ran. Each twister case goes to its spec case
  by (suite, function), as a test result does. Its matrix key is built from
  the scenario and the C function name (``kernel.lifo.usage`` +
  ``test_x`` gives ``kernel_lifo_usage_test_x``). The directive does not parse
  keys, because scenario names are prefixes of other scenario names.
* The needs come from ``needs_external_needs`` and ``testspec_needs_json``.

The directive finds the bodies of each symbol in the sources of the run
commit (``git show <sha>:<path>`` in ``testmodule_root``). The commit comes
from ``zephyr.sha``, else from the ``-g<hash>`` of
``environment.zephyr_version`` in ``twister.json``. If the commit is not in
the tree, the directive reads the working tree and warns. A body is
``z_impl_<symbol>``, ``z_vrfy_<symbol>`` (the verifier that a user-mode test
reaches), a plain definition, or a header ``static inline``. A macro has no
body.

``testcoverage_impl_files`` sets the files that hold the bodies. Each entry is
a glob pattern relative to ``testmodule_root``: ``**/`` is zero or more
directories, and ``*`` stays in one directory. In a ``.h`` file, only a
``static inline`` definition is a body. The default is the set of the
original resolver:

.. code-block:: python

   testcoverage_impl_files = [  # default
       "kernel/*.c",
       "kernel/**/*.c",
       "include/zephyr/kernel.h",
       "include/zephyr/kernel/**/*.h",
       "include/zephyr/sys/**/*.h",
   ]

An empty list gives the default. A symbol with its body outside these files
gets the verdict ``unresolved``. The summary of the run lists the files that
the directive searched.

The verdicts:

``true``
   The own tests run every symbol that coverage can judge.
``partial``
   The own tests run some of these symbols, not all.
``broken``
   Other tests of the run reach the code. The own tests never do.
``unattributed``
   No test of the run covers any body. Coverage cannot judge the link.
``unresolved``
   No satisfying symbol maps to a body (a macro).
``no-cov``
   The verifying tests have no coverage data in the run.
``no-impl``
   No symbol satisfies the requirement.

The directive assesses a requirement if the run ran at least one of its
verifying test cases. It renders a summary of the run, a table of the
verdicts, and one section per verdict. A need has the title of its
requirement. Its body has:

* One sentence that says why the verdict is what it is ("The own tests run 1
  of the 2 symbols that coverage can judge. Only other tests run
  ``k_inline``.").
* A table with one row per body: the function (``z_vrfy_k_sem_give``), its
  form and place, the lines that the own tests ran of the lines that any test
  of the run ran, and the number of other test cases that ran it. A
  requirement with no body (``unresolved``, ``no-impl``) has no table.
* For each body that the own tests never run, the other tests that do: the
  places where a ``@verifies`` can go. A test case is named once. The test
  cases that ran the same lines are one group.
* The verifying tests, and the fields that the consumer does not declare
  (``verdict``, ``evidence``, ``coverage_run``).

The table cells use the roles ``zd-adq-ok``, ``zd-adq-miss``, ``zd-adq-none``
and ``zd-adq-loc``. Each gives the text a class of the same name. The zdocs
need card (:ref:`need-layouts`) colors them.

The id of a need is ``ADQ-<run>/<requirement>``. ``testcoverage_id_prefix``
sets the prefix. The type, the link and the fields are roles, as for the other
directives:

.. code-block:: python

   testcoverage_need_types = {"adequacy": "adequacy"}  # defaults
   testcoverage_need_links = {"assesses": "assesses"}
   testcoverage_need_fields = {
       "verdict": "verdict", "evidence": "evidence", "coverage_run": "coverage_run",
       "judged_symbols": "judged_symbols", "symbol_hits": "symbol_hits",
   }

Declare the type and the link in your ``needs_config.toml``. The directive
sets a field only if your ``needs_config.toml`` declares it (string fields).
The body shows the verdict, the evidence and the run when they are not
fields. The fields:

``verdict``
   One of the verdicts above.
``evidence``
   The state of the verifying tests in the coverage run: ``passing``,
   ``failing``, ``skipped``, ``no-run`` or ``untested``.
``coverage_run``
   The name of the run.
``judged_symbols``
   The satisfying symbols, joined with ``"; "``.
``symbol_hits``
   Per symbol, the body lines that the own tests ran and that any test ran
   (``k_sem_init: own 11, any 11``).

A parameterized test (``ZTEST_P``) has one matrix key for all its values: the
per-test dump of Zephyr has no value in its tag.

``.. symbolneeds::``
--------------------

One need per API symbol (function, macro, ...) carrying a Doxygen 1.16
``\satisfies <UID>``, linked to the requirement needs those UIDs name. Loads
only for a document whose registry entry has a ``symbol_needs:`` block
(:doc:`registry-schema`), which also names the Doxygen document whose XML is
read. Source: :external+zdocs-api:py:mod:`symbol_needs`.

.. code-block:: rst

   .. symbolneeds::

   .. symbolneeds:: queue_apis

Without an argument, every annotated symbol in the Doxygen project is
emitted, in sections headed by the group (or file) that documents it. With a
Doxygen group name, only that group's symbols, with no heading. Each symbol is
emitted once. A symbol without ``\satisfies`` gets no need.

Each need is titled with the symbol name and has the id
``<TYPE>-<symbol>``, where ``<TYPE>`` is the need type's name in upper case
(``IMPL-k_queue_init``). Its body gives the kind, the brief, a link to the
symbol's Doxygen page and the file it is declared in; no custom field is
needed for them. "Declared in" links to the declaration's line in Doxygen's
source listing, if the run wrote one: with ``SOURCE_BROWSER = YES`` for every
file, with ``VERBATIM_HEADERS = YES`` (the Doxygen default) for the headers.
The need type and link are engine roles, named by the consumer like the test
directives' (ADR-0009):

.. code-block:: python

   symbolneeds_need_types = {"implementation": "impl"}      # the defaults
   symbolneeds_need_links = {"satisfies": "satisfies"}

Declare both in ``needs_config.toml``; the link's ``incoming`` name is what a
requirement's page shows:

.. code-block:: toml

   [[needs.types]]
   directive = "impl"
   title = "Implementation"
   prefix = "IMPL_"

   [needs.links.satisfies]
   outgoing = "satisfies"
   incoming = "satisfied by"

A ``\satisfies`` naming a UID that no requirement need has is reported like a
dangling ``verifies``: sphinx-needs warns "unknown outgoing link" in the
stage-2 build (the XML cannot tell, since Doxygen writes a
``requirement_<UID>`` refid for any UID), and Doxygen's own "Reference to
unknown requirement" warning fails the Doxygen document through
``ZDOCS_DOXYGEN_WARN_FAIL_PATTERNS`` (:doc:`consumer-contract`).

.. _need-layouts:

Need layouts
------------

Not a directive: helpers for a document's ``conf.py``, which it imports from
``zdocs_conf``. Source: :external+zdocs-api:py:mod:`need_layouts`.

``need_layout()`` gives the zdocs need card: a head with the type, the ID, a
pill and the title; then the text of the need; then its fields and links.
``zdocs-needs.css`` styles a need whose layout name starts with ``zdocs``, so
give the layout such a name:

.. code-block:: python

   from zdocs_conf import configure, need_layout

   needs_layouts = {
       "zdocs_requirement": need_layout(
           fields=[("rtype", "Kind"), ("component", "Component")],
           hide_backlinks=["covers"],
       ),
   }
   needs_default_layout = "zdocs_requirement"

``fields``
   ``(name, label)`` pairs, in the order to show. A field without a value
   shows no row. Without ``fields``, the card shows every field that has a
   value, under its own name; ``fields=[]`` shows the links only. A label is
   plain words.
``hide_backlinks``
   The links whose incoming side the card does not show. A requirement can
   have hundreds of test results that cover it, and that list hides the rest
   of the need.
``pill``
   The field that the head shows as a pill: ``status`` (the default), or
   ``verdict`` for an adequacy need. The pill of a test result status and of
   a verdict has the color of its value.

The rows stay in the sphinx-needs order (head, fields, text) in the HTML; the
CSS shows the text before the fields. So the PDF and a screen reader still
give the fields first.

The ``need_cards`` extension (loaded by ``zdocs_conf``) gives each card the
``color`` of its need type in ``needs_config.toml`` as the accent, and the
class ``zd-status-<status>`` / ``zd-verdict-<verdict>`` that colors the pill.
A type without a color stays grey.

The engine puts the references of a generated need (Depends on, Source, See
also, Declared in) in a ``need-refs`` container: the card shows them as one
block under the text.

A document with its own layout uses ``links_line()`` in place of
``<<meta_links_all()>>``:

.. code-block:: python

   from zdocs_conf import configure, links_line

   "meta": [
       '<<meta("status", prefix="\\*\\*status:\\*\\* ")>>',
       links_line(["result_of"]),
   ],

Use the link name from ``needs_config.toml`` (``covers``), not its
``incoming`` title (``covered by``). A name with a space or a quote is an
error. A name that is no link type of the document is not an error, but it
hides nothing. The outgoing side of the link stays. The links also stay in the
need data, so ``needs.json``, need tables and need flows still show them.

Doxylink prefixes
-----------------

Not a directive at all, but the mechanism every Doxygen document's symbols are
reached through from Sphinx prose. Every ``kind: doxygen`` (and
``doxygen-external``) registry entry contributes a role named after its own
``prefix:`` (:doc:`registry-schema`), resolved through that document's
:term:`tag file`:

.. code-block:: rst

   See :acme-widget:`acme_widget_init` for the full signature.

This is distinct from ``:external+<prefix>:`` (used for a Sphinx peer's own
labels/objects — see :doc:`../index`): a doxylink role has no ``external+``
prefix of its own, because doxylink is not intersphinx and does not share its
role syntax.
