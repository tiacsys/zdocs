Sphinx extensions
==================

Reference documentation for the modules under ``sphinx/_extensions/``: directives, roles and
builders loaded by :py:func:`zdocs_conf.configure`. The plain modules they share are on
:doc:`support-modules`. See the companion
manual's :external+zdocs-manual:doc:`Directives and roles <reference/directives-and-roles>`
page for how a document author uses each one.

``doc_control``
----------------

The ``.. doc_control::`` directive — the controlled-document header table.

.. automodule:: doc_control
   :members:
   :exclude-members: DEFAULT_CLASSIFICATIONS

..
   DEFAULT_CLASSIFICATIONS is excluded: its own `#:` doc-comment is not valid
   standalone reST once extracted (an "Override in conf.py:" line immediately
   followed by an indented example reads as a malformed definition list to
   docutils — "Definition list ends without a blank line; unexpected
   unindent"). A defect in the source docstring, not something this page's
   directive options can route around (this module and the other broken ones
   below live outside this step's file inventory — see the final report).

``qms_ref``
------------

The ``.. qms_role::`` directive. 

.. autoclass:: qms_ref.QmsDocRole
   :members:

``latexinclude``
------------------

The ``.. latexinclude::`` directive.

.. automodule:: latexinclude
   :members:

``test_module``
-----------------

The ``.. testmodule::``, ``.. testreport::`` and ``.. twisterinfo::``
directives.

.. automodule:: test_module
   :members:

``test_coverage``
-------------------

The ``.. testcoverage::`` directive. ``test_module`` loads it.

.. automodule:: test_coverage
   :members:

``symbol_needs``
------------------

The ``.. symbolneeds::`` directive.

.. automodule:: symbol_needs
   :members:

``input_tracking``
--------------------

Re-reads a document when an input from outside the source tree changes.

.. automodule:: input_tracking
   :members:

``needs_config_state``
------------------------

Re-reads a document when its sphinx-needs TOML file or the needs it imports change.

.. automodule:: needs_config_state
   :members:

``xref_builder``
------------------

The stage-1 ``xref`` builder for the two-stage documentation build.

.. automodule:: xref_builder
   :members:
