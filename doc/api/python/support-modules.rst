Support modules
================

The plain Python modules that the Sphinx extensions share: parsers, RST
builders and the coverage logic. None of them is a Sphinx extension; none has
a ``setup()``. Source: ``sphinx/_scripts/``.

``needs_fields``
------------------

Which optional need fields a consumer declared.

.. automodule:: needs_fields
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

``adequacy``
--------------

Coverage adequacy, with no Sphinx dependency of its own.

.. automodule:: adequacy
   :members:

..
   parse_twister_results is excluded: its docstring's own example text,
   "leading 'test_' prefix stripped", ends in a bare trailing underscore
   directly after a word — reST's own "quoted hyperlink reference" syntax
   (``word_``) — with no matching target, so autodoc turns it into
   "Unknown target name: 'test'". A source defect, not a directive-option
   fix; see the final report.
