0006. The deploy tree is organised by builder, not by document
===============================================================

Status
------

Accepted.

Context
-------

Output used to land at ``deploy/<document>/<builder>/``: each document owned a
folder, and its HTML, PDF and other builder outputs sat inside it. That groups
by the wrong axis for the one operation the tree exists for. Publishing means
"put the HTML on the web server" — and under that layout the HTML of a
documentation set is scattered across as many folders as there are documents,
interleaved with PDFs and LaTeX intermediates that must not be served.

Decision
--------

The axes are swapped: ``deploy/<builder>/<document>/``. The publish step
becomes a single directory sync of ``deploy/html/`` (and optionally
``deploy/pdf/``), and the servable tree contains nothing that is not servable.

The ``latex`` builder's folder is named ``pdf``, because what is published from
it is the PDF, not the LaTeX intermediates that produced it.

The engine also takes control of Doxygen's ``HTML_OUTPUT`` as part of this: a
Doxygen document's public directory could not otherwise be reached, because
Doxygen's own default nests an ``html/`` level inside whatever output directory
it is given.

