# Copyright (c) 2026 almedso GmbH
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""The ``latexinclude`` directive — include an RST file in the PDF only.

::

    .. latexinclude:: ../_glossary_terms.rst   # relative to the AUTHORED file
    .. latexinclude:: /_glossary_terms.rst     # relative to the SOURCE TREE

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

**A leading ``/`` means relative to the source tree instead**, exactly as it does
for Sphinx's own ``include`` directive ("interprets absolute paths correctly,
i.e. relative to source directory"). The same spelling then works from both
directives and from any depth, which is the point: an authored-relative path
encodes how far the including file sits below the shared file, so moving a
document from ``doc/<id>/`` to ``doc/<group>/<id>/`` silently changes what
``../`` means and turns a working glossary into a build failure. A source-tree
path says where the file IS, not how far away the author happened to be.

That spelling requires the shared file to be present in the source tree, which
it is not by default -- ``external_content`` copies only the document's own
folder. A consumer that wants it adds it to ``external_content_contents`` (and
to ``exclude_patterns``, since an include fragment is not a document). Both
spellings are supported and neither is deprecated: the authored-relative one
remains correct for a file that is deliberately NOT copied into the build.
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

        argument = self.arguments[0]

        if argument.startswith("/"):
            # Source-tree-relative, matching sphinx.directives.other.Include's
            # own handling of an absolute path. Depth-independent: the same
            # spelling resolves identically from every document, however deeply
            # it is nested, so moving a document cannot change what it means.
            base_dir = Path(env.srcdir)
            include_path = (base_dir / argument.lstrip("/")).resolve()
            base_note = (
                f"resolved against the SOURCE TREE {base_dir} (leading '/'). "
                f"The file has to be copied into the build -- see "
                f"external_content_contents -- for this spelling to work."
            )
        else:
            # The directory this file lives in AS AUTHORED. `docname` is
            # posix-style and relative to the source tree, so its dirname is the
            # same relative offset inside confdir -- which is where the author
            # wrote it.
            base_dir = Path(env.app.confdir) / posixpath.dirname(env.docname)
            include_path = (base_dir / argument).resolve()
            base_note = (
                f"resolved against the AUTHORED directory {base_dir}, not the "
                f"generated source tree the build parses from."
            )

        if not include_path.is_file():
            # Loud, at build time, naming the resolved path -- rather than a
            # traceback out of `open()`, or (worse) an empty include that leaves
            # the glossary out of a signed-off PDF without anyone noticing.
            raise ExtensionError(
                f"latexinclude: no such file: {include_path}\n"
                f"  directive:  .. latexinclude:: {argument}\n"
                f"  in:         {env.docname}\n"
                f"  {base_note}"
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
