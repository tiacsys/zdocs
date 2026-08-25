Scripts
========

Standalone command-line tools, run directly with ``python3`` — see
the companion manual's own task-facing page for how they are invoked. Source:
``scripts/``.

``docrefs``
------------

Central cross-document reference registry — read by every ``conf.py`` and by
:cmake:command:`add_docs_from_registry`, :cmake:command:`add_doxygen_target`
and :cmake:command:`add_sphinx_target` alike.

.. automodule:: docrefs
   :members:

``doccheck``
-------------

Post-build cross-reference integrity checks, wired by
:cmake:command:`add_doc_check`.

.. automodule:: doccheck
   :members:
   :exclude-members: check_dangling_ids

..
   check_dangling_ids is excluded: its own docstring's glob pattern
   ``doc/<id>/**.rst|.md`` contains a bare ``**`` that reST reads as an
   unterminated strong-emphasis start ("Inline strong start-string without
   end-string") -- a source defect, not something an automodule option
   routes around; see the final report.

``docctl``
-----------

The author/review/approve controlled-document workflow. Declared with a
bare ``.. py:module::`` rather than ``automodule``: the module's own
docstring opens a bulleted list directly after a paragraph with no
separating blank line, which reST reads as "Unexpected indentation" — a
source defect ``automodule`` cannot route around via a directive option
(unlike the single excluded members above, the broken text here IS the
module docstring itself). None of its subcommand functions
(``cmd_list``/``cmd_author``/``cmd_review``/``cmd_approve``/
``cmd_bump_version``) carry their own docstring, so there is no member-level
autodoc to fall back to either; see the companion manual's
:external+zdocs-manual:doc:`Command-line tools <reference/cli>` page for the
task-facing description of every subcommand, and ``scripts/docctl.py``
itself for the implementation. See the final report for this finding.

.. py:module:: docctl
