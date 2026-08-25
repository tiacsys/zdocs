Sphinx extensions
==================

Reference documentation for the modules under ``sphinx/_extensions/``: directives, roles and
builders loaded by :py:func:`zdocs_conf.configure`. See the companion
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

``xref_builder``
------------------

The stage-1 ``xref`` builder for the two-stage documentation build.

.. automodule:: xref_builder
   :members:

``doxygen_parser``
--------------------

Doxygen XML parsing, with no Sphinx dependency of its own.

.. automodule:: doxygen_parser
   :members:

``rst_builders``
------------------

RST string builders, with no Sphinx dependency of their own.

.. automodule:: rst_builders
   :members:

``twister_reader``
--------------------

Twister output parsing, with no Sphinx dependency of its own.

.. automodule:: twister_reader
   :members:
   :exclude-members: parse_twister_results

..
   parse_twister_results is excluded: its docstring's own example text,
   "leading 'test_' prefix stripped", ends in a bare trailing underscore
   directly after a word — reST's own "quoted hyperlink reference" syntax
   (``word_``) — with no matching target, so autodoc turns it into
   "Unknown target name: 'test'". A source defect, not a directive-option
   fix; see the final report.
