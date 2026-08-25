Directives and roles
=====================

What a document author writes in RST. Every directive here is loaded for
every document by :external+zdocs-api:py:func:`zdocs_conf.configure`, whether
or not the document uses it — an extension list that varied by document would
make the two build stages' configuration differ and invalidate the shared
doctree cache. The ``testmodule``/``testreport``/``twisterinfo`` directives are
the one exception: they load only for a document whose registry entry carries
a ``testmodule:`` block (:doc:`registry-schema`).

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
locate that module's ``testcase.yaml`` for the rendered scenario table. Every
``ZTEST``/``ZTEST_SUITE``/... in the named group and its inner suite/procedure
groups becomes one need each — nothing is written by hand per test case.

.. code-block:: rst

   .. testreport:: twister_report.xml
      :module: widget.probe

   .. twisterinfo:: twister.json

``testreport``'s and ``twisterinfo``'s arguments are filenames resolved
against ``ZDOCS_TWISTER_OUT`` (or the including document's own directory, as a
fallback, if that is unset) unless given as an absolute path.
``testreport``'s optional ``:module:`` prefix-matches against the JUnit
``classname``. Both directives **soft-fail** to a short "not found" paragraph
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

.. code-block:: c

   /**
    * @reqref{DUTY_001}
    * @see acme_widget_init()
    * @testid{WIDGET-PROBE-001}
    */
   ZTEST(widget_probe_suite, test_widget_reports_initial_value)
   {
       ...
   }

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
