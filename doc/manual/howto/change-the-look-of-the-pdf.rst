Change the look of the PDF
==========================

The look of a zdocs PDF is in the LaTeX package ``zdocs.sty``
(``sphinx/_latex/`` in the engine). Each PDF loads it after Sphinx's own
package. To change the look for your documents, give a style file of your
own. The PDF loads it after ``zdocs.sty``, so it can change what
``zdocs.sty`` sets.

Give a style file
-----------------

1. Put a ``.sty`` file in the folder of the document, for example
   ``doc/handbook/acme-pdf.sty``. Do not call it ``zdocs.sty``.
2. Give its path to ``configure()`` in the document's ``conf.py``:

   .. code-block:: python

      from pathlib import Path

      from zdocs_conf import configure

      configure(
          globals(),
          Path(__file__).parent,
          project="ACME Handbook",
          latex_style=Path(__file__).parent / "acme-pdf.sty",
      )

   Use an absolute path: Sphinx reads ``conf.py`` from a copy of the
   document folder in the build tree.
3. Build the PDF (``<document>-latex``).

What a style file can change
----------------------------

Settings, with ``\zdsetup{key=value, ...}``. ``zdocs_conf`` sets these from
the build; a style file can set them again:

``title``
   The running header, left. Default: the document title.
``version``
   The running header, right, and the title page. Default: the document
   version.
``footer``
   The running footer, left, and the title page. Default:
   ``Copyright <year> <holder>``.
``docid``
   The document ID on the title page. Default: the registry ID.

Colors, with ``\definecolor`` (xcolor):

``zdRule``, ``zdMuted``
   The lines and the text of the running header and footer.
``zdLabel``
   The labels of the fields in a need card, and of the rows on the title page.
``zdTonegood``, ``zdTonebad``, ``zdTonegap``, ``zdTonenone``
   The status badge of a need card: passed, failed, partial, not run. A
   status of another value (for example ``approved``) has the accent color of
   its need type.

Fonts, with fontspec. The text and the headings use the sans-serif font,
the code the monospaced font:

.. code-block:: latex

   \setsansfont{TeX Gyre Heros}
   \setmonofont{TeX Gyre Cursor}

The font must be in the TeX installation of each machine that builds the
PDF, also in CI. The default fonts (FreeSans, FreeMono) are the ones that a
Sphinx PDF needs already.

The width of the label column of a need card:

.. code-block:: latex

   \setlength{\zdneedlabelwidth}{9em}

For a bigger change, a style file can define a macro of ``zdocs.sty`` again
(``\renewcommand``, ``\renewenvironment``): ``\sphinxmaketitle`` (the title
page), the environment ``zdneed`` and the macros ``\zdneedhead``,
``\zdneedtitle`` and ``\zdneedfield`` (the need card). Their arguments are in
the comments of ``zdocs.sty``. A macro that you define again does not get
the changes of a new zdocs version.

An example
----------

.. code-block:: latex

   % acme-pdf.sty
   \ProvidesPackage{acme-pdf}
   \zdsetup{footer={ACME Instruments Ltd. -- Confidential}}
   \definecolor{zdRule}{HTML}{005A9C}
   \setlength{\zdneedlabelwidth}{8em}

See also :doc:`../explanation/decisions/0014-pdf-layout-in-a-style-file`.
