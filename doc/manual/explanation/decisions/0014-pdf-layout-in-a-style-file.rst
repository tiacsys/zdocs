0014. The PDF layout is a LaTeX style file
==========================================

Status
------

Accepted, 2026-10-14.

Context
-------

The look of a zdocs PDF was the Sphinx default with a few changes: strings
of LaTeX in ``zdocs_conf.py`` for the running header and footer. The result
had several problems:

- The body text used a serif font, and the headings and the title page used
  a sans-serif font.
- The contents were on a page of their own, and the title page was mostly
  empty.
- A need card was a table of grey rows, because the card look is CSS, which
  does not reach LaTeX. The fields came before the text, and their labels
  looked like their values.
- A need table did not fit the page.

A consumer could change the PDF only by replacing ``latex_elements`` in its
``conf.py``, which also drops the engine's settings.

Decision
--------

- The engine has a LaTeX package, ``zdocs.sty`` (``sphinx/_latex/``). Each
  PDF loads it after Sphinx's own package. ``zdocs_conf`` gives it only the
  values of the build, with ``\zdsetup{...}``.
- ``zdocs.sty`` changes the Sphinx layout only through what Sphinx
  documents: the page styles ``normal`` and ``plain``, ``\sphinxmaketitle``,
  ``\sphinxtableofcontents``, the table hooks ``\sphinxattablestart`` and
  ``\sphinxatlongtablestart``, the class environments ``sphinxclass<name>``
  and the paragraph start ``\sphinxAtStartPar``. It does not copy or patch
  ``sphinx.sty``.
- ``zdocs.sty`` loads no package that a Sphinx xelatex build does not load
  already. The need card uses ``framed``, not ``tcolorbox``.
- An extension writes semantic markup where a style needs it: ``need_cards``
  writes a zdocs card as ``zdneed`` with ``\zdneedhead``, ``\zdneedtitle``
  and ``\zdneedfield``; ``pdf_tables`` gives a need table its widths and its
  class. The style file decides how this markup looks, as the CSS does for
  the HTML.
- A consumer gives its own style file with ``configure(latex_style=...)``.
  The PDF loads it last, so it can set the keys, colors, fonts and macros
  again (:doc:`../../howto/change-the-look-of-the-pdf`).

Consequences
------------

- The PDF layout is in one file, in LaTeX, and not in Python strings.
- A Sphinx upgrade can change a documented hook. Sphinx is pinned
  (``requirements-doc.txt``), so an upgrade is a deliberate step, and the
  acceptance suite builds a PDF.
- The look of a card is in two places: ``zdocs-needs.css`` for HTML and
  ``zdocs.sty`` for the PDF. The accent of a type and the colors of a status
  are the same in both; a change to one needs the same change to the other.
- A consumer that defines a macro of ``zdocs.sty`` again does not get the
  changes of a new zdocs version for that macro.
- The default fonts stay the ones that Sphinx needs (FreeSans, FreeMono). A
  consumer that wants other fonts must install them on each machine that
  builds the PDF.
