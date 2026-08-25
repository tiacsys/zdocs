# Copyright (c) 2026 almedso GmbH
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""The ``latexinclude`` directive — include an RST file in the PDF only.

::

    .. latexinclude:: ../_glossary_terms.rst

A printed document carries no hyperlinks, so anything an HTML reader would reach
by following a link has to travel with the PDF instead: a shared glossary, a
terms-and-abbreviations appendix, a standards list. Inlining the same content
into the HTML would just give that reader a second copy of a page they can
already open, so this includes for LaTeX builders and does nothing everywhere
else.

**The path is relative to the including file as AUTHORED**, which is not where
Sphinx parses it from. ``external_content`` copies each document's folder into
``<build>/<doc>/src`` and the build runs from that copy, so resolving the
argument against the parse location sends ``..`` into ``<build>/<doc>`` — a
directory of doctrees and logs, never of authored RST. The only file worth
including this way is a SHARED one (a file inside the document would simply be
part of it), and a shared file is by definition outside the folder that gets
copied. So the wrong base directory does not degrade this directive, it breaks
every legitimate use of it.

The authored location is reconstructed from Sphinx's own two facts: ``confdir``
is the document's authored directory (cmake passes it as ``-c``), and ``docname``
is the including file's path within the document. Together they give the file the
author was looking at when they counted the ``..``.
"""

from __future__ import annotations

import posixpath
from pathlib import Path

from docutils.parsers.rst import Directive
from sphinx.errors import ExtensionError


class LatexIncludeDirective(Directive):
    """Include an RST file for LaTeX builders, skipping it for every other."""

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {}

    def run(self):
        env = self.state.document.settings.env

        # Tested on the builder FORMAT, not its name. The stage-1 `xref` builder
        # is a DummyBuilder whose format is empty, so it correctly skips; a name
        # test ("latex" in builder.name) is the shape that would also fire for
        # some future "latexpdf-live" and, worse, quietly not fire for a builder
        # that produces LaTeX under another name.
        if env.app.builder.format != "latex":
            return []

        # The directory this file lives in AS AUTHORED. `docname` is posix-style
        # and relative to the source tree, so its dirname is the same relative
        # offset inside confdir -- which is where the author wrote it.
        authored_dir = Path(env.app.confdir) / posixpath.dirname(env.docname)
        include_path = (authored_dir / self.arguments[0]).resolve()

        if not include_path.is_file():
            # Loud, at build time, naming the resolved path -- rather than a
            # traceback out of `open()`, or (worse) an empty include that leaves
            # the glossary out of a signed-off PDF without anyone noticing.
            raise ExtensionError(
                f"latexinclude: no such file: {include_path}\n"
                f"  directive:  .. latexinclude:: {self.arguments[0]}\n"
                f"  in:         {env.docname}\n"
                f"  resolved against the AUTHORED directory {authored_dir}, not "
                f"the generated source tree the build parses from."
            )

        env.note_dependency(str(include_path))
        self.state_machine.insert_input(
            include_path.read_text(encoding="utf-8").splitlines(),
            str(include_path),
        )
        return []


def setup(app):
    app.add_directive("latexinclude", LatexIncludeDirective)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
