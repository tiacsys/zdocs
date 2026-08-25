# Copyright (c) 2026 inovex GmbH
# Copyright (c) 2026 almedso GmbH
#
# SPDX-License-Identifier: Apache-2.0

import posixpath
from datetime import datetime

from docutils import nodes
from docutils.parsers.rst import Directive, directives


def parse_date(value, field_name):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception as exc:
        raise ValueError(
            f"Invalid date format for '{field_name}': '{value}', expected YYYY-MM-DD"
        ) from exc


class DocCtrlDirective(Directive):
    has_content = False

    option_spec = {
        "version": directives.unchanged_required,
        "owner": directives.unchanged_required,
        "author": directives.unchanged_required,
        # Injected  by a CI job, extracted from git
        "approval_date": directives.unchanged_required,
        "approved_by": directives.unchanged_required,
        "reviewed_by": directives.unchanged_required,
        # Manually set
        "effective_date": directives.unchanged,
        "supersedes": directives.unchanged,
        # Nice to have for reviewer to know where it is derived from
        # Regulatory not needed
        "based_on_template": directives.unchanged,
        #
        "classification": directives.unchanged,
    }

    # `version` is NOT required: it defaults to the document's git-tag-derived
    # version (conf `version`, see scripts/docrefs.py resolve_version). Pass
    # `:version:` only to override.
    REQUIRED = [
        "owner",
    ]

    def run(self):
        opts = self.options

        opts = self._validate(opts)
        data = self._add_missing_attributes(opts)

        # Stashed so the doctree-resolved handler below (which builds the
        # PDF-only "signature_section") can look up this document's
        # reviewed_by/approved_by/approval_date without re-parsing the
        # directive's options itself.
        env = self.state.document.settings.env
        env.doc_control_data = getattr(env, "doc_control_data", {})
        env.doc_control_data[env.docname] = data

        return self._render(data)

    def _matches_docname(self, document_id, docname):
        # customize this logic
        return document_id == docname.split("/")[-1]

    def _determine_doc_title(self):

        doctree = self.state.document

        title_node = doctree.next_node(nodes.title)
        title = title_node.astext() if title_node else "<no title>"

        return title

    def _extract_document_id(self):
        env = self.state.document.settings.env
        return posixpath.basename(env.docname)

    def _validate(self, opts):

        # --- required field check ---
        missing = [k for k in self.REQUIRED if k not in opts]
        if missing:
            raise self.error(f"Missing required fields: {missing}")

        # --- date validation ---

        if "approval_date" in opts:
            parse_date(opts["approval_date"], "approval_date")

        if "effective_date" in opts and "approval_date" in opts:
            eff_date = parse_date(opts["effective_date"], "effective_date")
            appr_date = parse_date(opts["approval_date"], "approval_date")
            if eff_date < appr_date:
                raise self.error("effective_date must be >= approval_date")

        if "classification" in opts:
            allowed = self.state.document.settings.env.config.doc_control_classifications
            if allowed and opts["classification"] not in allowed:
                raise self.error(
                    f"Invalid classification '{opts['classification']}', "
                    f"allowed values are: {list(allowed)}"
                )

        return opts

    def _add_missing_attributes(self, data):

        data["document_id"] = self._extract_document_id()
        data["title"] = self._determine_doc_title()

        # Default the version to the document's git-tag-derived conf version
        # (same value shown in the sidebar). `:version:` overrides it.
        if "version" not in data:
            env = self.state.document.settings.env
            data["version"] = env.config.version or "unknown"

        if "author" not in data:
            data["author"] = "not-authored-yet"
        if "approval_date" not in data:
            data["approval_date"] = "not-approved-yet"
        if "approved_by" not in data:
            data["approved_by"] = "not-approved-yet"
        if "reviewed_by" not in data:
            data["reviewed_by"] = "will by stamped in after approval"

        if "supersedes" not in data:
            data["supersedes"] = "None"
        if "based_on_template" not in data:
            data["based_on_template"] = "None"
        if "classification" not in data:
            data["classification"] = "Unclassified"

        return data

    def _render(self, data):
        table = nodes.table()
        table["classes"].append("doc-ctrl")

        tgroup = nodes.tgroup(cols=2)
        table += tgroup

        tgroup += nodes.colspec(colwidth=35)
        tgroup += nodes.colspec(colwidth=65)

        thead = nodes.thead()
        tbody = nodes.tbody()

        tgroup += thead
        tgroup += tbody

        # header row
        header_row = nodes.row()
        header_row += nodes.entry("", nodes.paragraph(text="Field"))
        header_row += nodes.entry("", nodes.paragraph(text="Value"))
        thead += header_row

        # controlled output order
        order = [
            "document_id",
            "title",
            "version",
            "owner",
            "classification",
            "based_on_template",
            "author",
            "reviewed_by",
            "approved_by",
            "approval_date",
            "effective_date",
            "supersedes",
        ]

        for key in order:
            if key in data:
                row = nodes.row()

                label = key.replace("_", " ").title()
                value = data[key]

                row += nodes.entry("", nodes.paragraph(text=label))
                row += nodes.entry("", nodes.paragraph(text=value))

                tbody += row

        return [table]


_LATEX_ESCAPES = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def latex_escape(text):
    """Escape `text` for use in a LaTeX string.

    Public because ``zdocs_conf`` needs the same escaping for the running header
    and footer it builds out of consumer-supplied values (project name, copyright
    holder, document id). Those are the strings most likely to contain an ``&``
    or an ``_``, and a second copy of this table living in the config module is
    how the two would stop agreeing.
    """
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


def _signature_section_latex(data):
    """PDF-only sign-off block: one ruled line per role (Author is left for
    the signer to fill in by hand; Reviewer/Approver are pre-filled from
    the doc_control directive's own fields), plus the control approval_date
    — the one date doc_control actually tracks.
    """
    reviewed_by = latex_escape(data.get("reviewed_by", ""))
    approved_by = latex_escape(data.get("approved_by", ""))
    approval_date = latex_escape(data.get("approval_date", ""))
    return rf"""
\bigskip
\noindent\textbf{{Signatures}}\par
\bigskip
\signatureline{{Author}}{{}}
\signatureline{{Reviewer}}{{{reviewed_by}}}
\signatureline{{Approver}}{{{approved_by}}}
\noindent\textbf{{Date:}} {approval_date}\par
\bigskip
"""


def _pick_doc_control_data(app):
    """The doc_control data for this project's *primary* document.

    The LaTeX builder assembles a project's whole toctree into one combined
    tree before firing ``doctree-resolved`` — always for ``docname ==
    master_doc`` ("index"), regardless of which child document the content
    (and its ``.. doc_control::``) actually lives in. So this can't just
    look up ``env.doc_control_data[docname]``: for a single-file project the
    data lives under "index" itself, but for a project whose content is a
    separate document included via a toctree (e.g. doc-control.rst) it's
    filed under that document's own name. A project with several nested
    sub-documents also has one doc_control per included file if more than
    one declares the directive — those aren't the document being signed
    off, so an ambiguous match falls back to "whatever's there" rather than
    silently dropping the signature section.
    """
    all_data = getattr(app.env, "doc_control_data", {})
    if not all_data:
        return None
    master = app.config.master_doc
    if master in all_data:
        return all_data[master]
    top_level = {k: v for k, v in all_data.items() if "/" not in k}
    if len(top_level) == 1:
        return next(iter(top_level.values()))
    return next(iter(all_data.values()))


def _find_first_section(node):
    """Depth-first search for the first ``nodes.section`` anywhere under
    ``node``. The LaTeX builder's assembled tree wraps a toctree-included
    document's content in Sphinx-internal container nodes (``compound`` >
    ``start_of_file`` > ...) before its actual sections appear, so "the
    first section" isn't necessarily a direct child of the document root.
    """
    for child in node.children:
        if isinstance(child, nodes.section):
            return child
        found = _find_first_section(child)
        if found is not None:
            return found
    return None


def _insert_signature_section(app, doctree, docname):
    # HTML (and any other non-LaTeX builder) has no notion of a signature
    # page — a raw(format="latex") node is already a no-op there, but skip
    # the work entirely rather than relying on that alone.
    if app.builder.format != "latex":
        return

    mode = app.config.signature_section
    if mode not in ("top", "bottom"):
        return

    data = _pick_doc_control_data(app)
    if not data:
        return

    raw = nodes.raw("", _signature_section_latex(data), format="latex")

    if mode == "bottom":
        doctree.append(raw)
    else:
        # "top": right after the doc_control table (and any other
        # un-sectioned front matter), before the first real content section
        # — wherever in the (possibly nested) tree that section actually is.
        section = _find_first_section(doctree)
        if section is not None and section.parent is not None:
            parent = section.parent
            parent.insert(parent.index(section), raw)
        else:
            doctree.append(raw)


def _merge_doc_control_data(app, env, docnames, other):
    # This build (SPHINXOPTS "-j auto" — see cmake/sphinx.cmake) reads
    # documents in parallel worker processes, each with its own pickled copy
    # of `env`; only attributes Sphinx itself knows about get merged back
    # into the main process's `env` automatically. `env.doc_control_data`
    # (set in DocCtrlDirective.run(), read by _pick_doc_control_data at
    # doctree-resolved time) is our own attribute, so it needs its own
    # merge step here — without this, the main env's doc_control_data stays
    # permanently empty and the signature section is silently never
    # inserted, no matter what `signature_section` is set to.
    other_data = getattr(other, "doc_control_data", None)
    if not other_data:
        return
    env.doc_control_data = getattr(env, "doc_control_data", {})
    env.doc_control_data.update(other_data)


#: Default vocabulary for `:classification:`. A reasonable QMS starting point,
#: NOT a rule: it is one organisation's document taxonomy, and it was previously
#: hardcoded in the validator, so a project whose documents are called anything
#: else got `ERROR: Invalid classification` and — because a directive error is a
#: docutils system message, not a build failure — a green build with the entire
#: control table missing from the page.
#:
#: Override in conf.py:
#:     doc_control_classifications = ["Handbook", "Runbook", ...]
#: or set it to an empty list to accept any value.
DEFAULT_CLASSIFICATIONS = [
    "SOP",
    "Work Instruction",
    "Record",
    "Policy",
    "Plan",  # e.g. project plan, risk management plan
    "Report",  # e.g. validation report, risk assessment report
    "Specification",  # e.g. software design specification
    "Register",  # e.g. training record register, tool register
]


def setup(app):
    app.add_directive("doc_control", DocCtrlDirective)

    # The permitted `:classification:` values — a project's document taxonomy,
    # not the engine's. Empty list disables the check.
    app.add_config_value("doc_control_classifications", DEFAULT_CLASSIFICATIONS, "env")

    # Per-project switch (set as a plain variable in conf.py, e.g.
    # `signature_section = "top"`) — "none" (default), "top" or "bottom".
    # PDF/LaTeX only; see _insert_signature_section.
    app.add_config_value("signature_section", "none", "env")

    # Release stage gate for `.. ifconfig:: releaselevel not in (...)` blocks.
    # Set as a plain variable in conf.py (see conf_common.configure()) — must
    # be registered here for sphinx.ext.ifconfig to see it via config.
    app.add_config_value("releaselevel", "next", "env")
    app.connect("env-merge-info", _merge_doc_control_data)
    app.connect("doctree-resolved", _insert_signature_section)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
