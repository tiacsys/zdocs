# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Shared Sphinx configuration for zdocs documents.

Each document's ``conf.py`` is a thin shim that calls :func:`configure`, passing
its own directory. This module is named ``zdocs_conf`` to not
conflict with a docset wide `conf_common`` the user might have on the path as well.

**Environment contract** (all set by ``add_sphinx_target``):

``ZDOCS_CONF_DIR``
    Where this file lives. zdocs is a separate repository, checked out wherever
    the Zephyr module system put it, so no relative path from a consumer's tree
    can reach it. (A consumer's ``conf.py`` *is* read from its authored
    directory, so relative paths to the consumer's own files work fine.)
``ZDOCS_DOC_ID``
    The document's registry key (its folder name).
``ZDOCS_PROJECT_BASE``
    The consuming repository's root — the git repo whose tags date the document.
``ZDOCS_REGISTRY``
    Optional path to ``documents.yaml``. Empty means a standalone document with
    no cross-references, which is a supported configuration, not a degraded one.
``ZDOCS_DOC_BUILD_DIR``, ``ZDOCS_DOC_DEPLOY_DIR``, ``ZDOCS_DOC_BASE_URL``
    Build tree, deploy tree, and the URL the deploy tree is served under.
"""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

ZDOCS_DOC_DIR = Path(__file__).resolve().parent
ZDOCS_BASE = ZDOCS_DOC_DIR.parent

# zdocs' own extensions and scripts, plus Zephyr's doc extensions (external_content
# assembles the Sphinx source tree). ZEPHYR_BASE is exported by the Zephyr build
# that ran find_package(Zephyr).
sys.path.insert(0, str(ZDOCS_DOC_DIR / "_extensions"))
sys.path.insert(0, str(ZDOCS_BASE / "scripts"))
_zephyr_base = os.environ.get("ZEPHYR_BASE")
if _zephyr_base:
    sys.path.insert(0, str(Path(_zephyr_base) / "doc" / "_extensions"))

import docrefs  # noqa: E402  (needs the sys.path above)
from doc_control import latex_escape  # noqa: E402  (same)

#: Defines the macro ``doc_control`` emits for the PDF-only sign-off block.
#:
#: The two halves live apart for a reason that is easy to get wrong: the
#: extension decides WHAT is signed (which roles, pre-filled from which
#: directive fields) and the preamble decides what a signature line LOOKS like.
#: But they are a pair, and only one of them can fail loudly — an emitted
#: ``\signatureline`` with nothing defining it stops xelatex dead ("Undefined
#: control sequence"), whereas the macro sitting unused costs nothing. So the
#: engine always ships the definition, whatever ``signature_section`` is set to.
_SIGNATURE_LINE_MACRO = r"""
\newcommand{\signatureline}[2]{%
    \noindent\textbf{#1}\par
    \vspace{0.35cm}
    \noindent#2\par
    \vspace{0.20cm}
    \noindent\makebox[\linewidth]{\rule{0pt}{0.5pt}\hrulefill}\par
    \vspace{0.85cm}
}
"""


def _env_path(name):
    value = os.environ.get(name)
    return Path(value).resolve() if value else None


def configure(
    namespace,
    doc_dir,
    project=None,
    author=None,
    copyright_holder=None,
    html_logo=None,
    extensions=None,
    static_path=None,
    css_files=None,
    templates_path=None,
    needs_config=None,
):
    """Populate a document's ``conf.py`` globals with the shared configuration.

    ``doc_dir`` is the document's own directory. ``project``, ``author`` and
    ``copyright_holder`` are the consumer's identity.

    ``extensions`` is appended to the engine's list rather than replacing it, so
    a consumer can add its own without having to restate the two-stage build's
    requirements (and without being able to drop them by accident).
    """
    doc_dir = Path(doc_dir)
    folder = doc_dir.name
    project = project or folder.replace("-", " ").title()

    doc_id = os.environ.get("ZDOCS_DOC_ID", folder)
    project_base = _env_path("ZDOCS_PROJECT_BASE")
    registry = _env_path("ZDOCS_REGISTRY")

    # -- Extensions -----------------------------------------------------------
    #
    # xref_builder registers the `-b xref` builder that stage 1 runs. Without it
    # the stage-1 command fails outright, which is the good failure -- the bad
    # one would be a build that quietly skips indexing and leaves every
    # cross-document reference unresolvable.
    engine_extensions = [
        "xref_builder",
        "sphinx.ext.intersphinx",
        "sphinx_rtd_theme",
        # Resolves :<prefix>:`symbol` against another document's Doxygen tag
        # file. Loaded unconditionally so the extension list does not vary with
        # whether a registry happened to be passed; with no registry the
        # `doxylink` mapping below is simply empty.
        "sphinxcontrib.doxylink",
        # Structured, linkable requirements/specifications. Loaded for every
        # document: the directives are inert in one that uses none, whereas a
        # conditional extension list would make the two build stages' configs
        # differ and invalidate the doctree cache between them.
        "sphinx_needs",
        # The `doc_control` directive: the controlled-document header (owner,
        # classification, approval dates, version). Registers `signature_section`
        # and `releaselevel` as config values, so it must be loaded even by
        # documents that use no directive from it — sphinx.ext.ifconfig reads
        # `releaselevel` through the config, and an unregistered value is an error
        # rather than a default.
        "doc_control",
        # The `:qmsdoc:` role, for `kind: external` registry documents — ones
        # this project does not build and cannot reach with :ref: or intersphinx.
        "qms_ref",
        # The `latexinclude` directive: content that belongs in the PDF and
        # nowhere else, typically a shared glossary. Loaded for every document
        # like the rest — the directive is a no-op in any non-LaTeX builder, and
        # an extension list that varied by builder would make the two build
        # stages' configs differ and invalidate the doctree cache between them.
        "latexinclude",
    ]
    if _zephyr_base:
        # Assembles the Sphinx source tree by copying the document's own files
        # into <build>/<doc>/src. The engine builds from that copy, not from the
        # authored directory.
        engine_extensions.append("zephyr.external_content")

    all_extensions = engine_extensions + list(extensions or [])

    # -- Cross-document links, if this document is part of a set ---------------
    refs = None
    version_scope = None
    if registry and registry.is_file():
        refs = docrefs.load(registry=registry, this_doc=doc_id)
        version_scope = refs.version_scope

    #
    # The registry entry IS the opt-in: a document whose entry carries no
    # `testmodule:` block gets NONE of this — not the extension, not any of its
    # config values — rather than an `add_test_config(namespace)` call a
    # consumer's conf.py has to remember , or unconditional
    # registration in `engine_extensions` above.
    testmodule = refs.testmodule if refs else None
    if testmodule is not None:
        all_extensions.append("test_module")

    # Version, from this document's scoped git tags in the CONSUMING repository
    # (or the VERSION env override) — the same resolver the Doxygen side uses, so
    # the two toolchains cannot disagree about the version of one repository.
    #
    # Displayed by _templates/layout.html, which restores the sidebar version
    # block sphinx_rtd_theme 3.1.0 dropped — without it a self-hosted document
    # resolves a version perfectly and shows it nowhere.
    version = docrefs.resolve_version(scope=version_scope, repo_root=project_base)

    copyright_year = datetime.datetime.now().year
    holder = copyright_holder or author or project

    # -- LaTeX / PDF ----------------------------------------------------------
    #
    # LATEX_DOC=<doc>.tex is set on every sphinx-build by cmake/sphinx.cmake, and
    # is the filename it then tells `latexmk` to build. It has to be repeated
    # here because Sphinx otherwise names the .tex after the project TITLE
    # ("ACME Handbook" -> acmehandbook.tex) — the build then does a full parse,
    # writes a perfectly good .tex, and dies at the last step with "Latexmk:
    # Could not find file 'handbook.tex'". The fallback is for an ad-hoc
    # sphinx-build outside the CMake build; folder == document name by
    # convention, which is the same convention add_sphinx_target relies on.
    latex_target = os.environ.get("LATEX_DOC") or f"{folder}.tex"

    # The running header and footer.
    #
    # A PDF leaves the deploy tree — it gets printed, mailed, filed in a binder —
    # so unlike an HTML page it carries no navigation and no URL to say what it
    # is. This is the only thing that does, which is why the version goes in it:
    # a printed controlled document that does not state its own version is not a
    # controlled document.
    #
    # Every value here is the CONSUMER's, and every one is escaped. These are the
    # strings most likely to contain LaTeX syntax by accident — a company called
    # "Smith & Co", a document id with an underscore — and unescaped they are a
    # compile error at the very end of a long build, not a typo on a page.
    #
    # sphinxlatexstylepage.sty (pulled in by \usepackage{sphinx}) defines the
    # "normal" and "plain" page styles with \fancypagestyle, and the body and ToC
    # pages select those BY NAME rather than a bare "fancy". Redefining those two
    # names, after \usepackage{sphinx} has run, is what actually sticks;
    # \pagestyle{fancy} in the preamble does not.
    page_style = rf"""
    \fancyhf{{}}
    \fancyhead[L]{{{latex_escape(doc_id)}}}
    \fancyhead[C]{{{latex_escape(project)}}}
    \fancyhead[R]{{{latex_escape(version)}}}
    \fancyfoot[L]{{Copyright {copyright_year} {latex_escape(holder)}. All rights reserved}}
    \fancyfoot[R]{{\thepage/\pageref{{LastPage}}}}
    \renewcommand{{\headrulewidth}}{{0.4pt}}
    \renewcommand{{\footrulewidth}}{{0.4pt}}
    """

    latex_preamble = (
        r"""
\usepackage{longtable}
\usepackage{array}
\usepackage{booktabs}
\usepackage{fancyhdr}
\usepackage{lastpage}
\usepackage{xcolor}
\usepackage{tabularx}
\usepackage{graphicx}
"""
        + _SIGNATURE_LINE_MACRO
        + rf"""
\fancypagestyle{{normal}}{{{page_style}}}
\fancypagestyle{{plain}}{{{page_style}}}
"""
        + r"""
% Top-level headings are \section, not \chapter (see latex_toplevel_sectioning):
% no "Chapter N" banner and no forced page break before each one, which suits a
% controlled document of a few dozen pages rather than a book.
%
% \thesection must then be re-anchored to \arabic{section}. In this document
% class it is \thechapter.\arabic{section}, and with no \chapter command ever
% invoked the chapter counter is never incremented — so every heading in the
% document numbers itself 0.1, 0.2, 0.3. That renders, compiles clean, and is
% only visible once someone looks at the PDF.
\renewcommand{\thesection}{\arabic{section}}

% No index, no glossary back-matter. Sphinx appends an index to a manual-class
% document by default; for a controlled document it is a page of nothing, since
% the terms that matter are in the glossary the document itself includes.
\let\printindex\relax
\let\printglossary\relax
\let\printglossaries\relax
"""
    )

    namespace.update(
        {
            # -- Project information ----------------------------------------
            "project": project,
            # The document's registry id, exposed to doc_control (which has
            # no other engine-side way to learn it) so its `Document Id`
            # field agrees with the id you type at `docctl author <id>` and
            # with the LaTeX running header above, instead of guessing from
            # whatever fragment the directive happens to sit in.
            "zdocs_doc_id": doc_id,
            "author": author or project,
            "copyright": f"{copyright_year}, {holder}",
            "version": version,
            "release": version,
            # -- General configuration --------------------------------------
            "extensions": all_extensions,
            "exclude_patterns": ["_build", "Thumbs.db", ".DS_Store"],
            # zdocs' templates first (they extend the theme), consumer's after.
            "templates_path": [str(ZDOCS_DOC_DIR / "_templates")]
            + [str(p) for p in (templates_path or [])],
            # external_content copies these into the Sphinx source tree. The
            # document's own folder is always included; a consumer adding more
            # does so by extending this afterwards in its conf.py.
            "external_content_contents": [(doc_dir, "*")],
            "intersphinx_mapping": refs.intersphinx_mapping if refs else {},
            # Doxygen tag files for every other `kind: doxygen` document, keyed
            # by that document's registry prefix — so :acme-widget:`some_symbol`
            # links into the API docs.
            #
            # Emitted unconditionally, like intersphinx, so the configuration is
            # identical in both build stages. Unlike intersphinx the ROLE
            # resolves at PARSE time, which is why every stage-1 index build
            # waits on the `doc-tags` aggregate: with no tag file present when
            # the document is parsed, the role degrades to plain text rather
            # than failing.
            "doxylink": refs.doxylink if refs else {},
            # doxylink parses EVERY signature in EVERY tag file to do overload
            # resolution, and warns once per signature its C++ grammar rejects —
            # on every document's build. The rejected ones are a mix of artifacts
            # doxygen recorded as "functions" that never were (attribute-
            # decorated declarations, function-like macros) and genuine C APIs
            # the grammar cannot handle. Neither is actionable in bulk, and
            # suppressing them loses nothing: referencing an unparseable symbol
            # still warns AT THE USE SITE, with file and line, which is the
            # message worth acting on.
            "doxylink_parse_error_ignore_regexes": [
                r"Error reported from parser was",
            ],
            # -- sphinx-needs -------------------------------------------------
            #
            # The export is a cross-document index exactly like objects.inv, and
            # the engine depends on it: sphinx-needs writes needs.json from a
            # `build-finished` hook whenever this is set, whatever the active
            # builder, which is what makes the stage-1 `xref` build produce one
            # without rendering HTML. Not a consumer preference — a document
            # whose needs are not exported cannot be imported by its peers.
            "needs_build_json": True,
            # Imports of other documents' needs, derived from the registry.
            "needs_external_needs": refs.needs_external_needs if refs else [],
            # -- HTML output ------------------------------------------------
            "html_title": project,
            "html_show_sphinx": False,
            "html_theme": "sphinx_rtd_theme",
            "html_theme_options": {
                "prev_next_buttons_location": "bottom",
                "style_external_links": False,
                "collapse_navigation": True,
                "sticky_navigation": True,
                "navigation_depth": 3,
                "includehidden": True,
                "titles_only": False,
            },
            # -- LaTeX / PDF output -------------------------------------------
            #
            # xelatex, not pdflatex: the documents this engine builds carry
            # names, standards references and units that are not Latin-1, and
            # pdflatex's answer to those is an inputenc error at the end of a
            # long build. It also lets fontspec use a system OpenType font
            # rather than a T1-encoded substitute.
            "latex_engine": "xelatex",
            # xindy handles non-English index sorting, which is the only reason
            # to prefer it — and there is no index (see the preamble). Left on,
            # it is one more binary a consumer has to install to build a PDF.
            "latex_use_xindy": False,
            "latex_domain_indices": False,
            # Top level of the document is a section; see the preamble note on
            # why that also needs \thesection re-anchored.
            "latex_toplevel_sectioning": "section",
            "latex_elements": {
                "papersize": "a4paper",
                "pointsize": "11pt",
                "figure_align": "htbp",
                # Both emptied because they are pdflatex's answer to encoding
                # and xelatex reads UTF-8 natively — left in place they load
                # inputenc, which under xelatex is an error rather than a
                # no-op.
                "inputenc": "",
                "utf8extra": "",
                # oneside: no blank verso pages, and no gutter that alternates
                # sides — a controlled document is read on screen and printed
                # single-sided far more often than it is bound. openany goes
                # with it: no forced recto start per top-level heading.
                "classoptions": "oneside,openany",
                "preamble": latex_preamble,
                "maketitle": r"\sphinxmaketitle",
                "printindex": "",
            },
            # (start docname, filename, title, author, class). The filename is
            # the contract with cmake — see latex_target above. "index" is
            # Sphinx's own default master_doc and the convention every document
            # in a zdocs set follows; a consumer that changes master_doc has to
            # restate this entry, which is the honest failure (a PDF built from
            # the wrong root would otherwise just be quietly incomplete).
            "latex_documents": [
                ("index", latex_target, project, author or project, "manual"),
            ],
        }
    )

    # Need types, link types and schemas are a METHODOLOGY choice — a
    # medical-device QMS wants hazard/risk, a security analysis wants threat —
    # and none of it belongs in a documentation engine. The engine only carries
    # the path across; sphinx-needs resolves it against the conf directory, so an
    # absolute path (which is what a consumer computing one from __file__ gets)
    # works unchanged.
    #
    # PROJECT-scoped by default (ZDOCS_NEEDS_CONFIG), not per document, because
    # the registry hands EVERY document an import of every needs-publishing
    # document. So a set whose documents declare different types is not a
    # configuration choice, it is a broken import, and the failure lands on the
    # innocent document rather than the one that diverged.
    #
    # The per-document argument still wins, for a document that genuinely needs
    # its own vocabulary and accepts being unable to import its peers'.
    needs_config = needs_config or os.environ.get("ZDOCS_NEEDS_CONFIG") or None
    if needs_config:
        namespace["needs_from_toml"] = str(needs_config)

    if html_logo:
        namespace["html_logo"] = html_logo
    # The engine's own static files always come first; a consumer's are appended
    # so a same-named file of theirs wins. Absolute paths, because a consumer's
    # conf.py is read from the copied source tree and relative ones would resolve
    # against the wrong directory.
    namespace["html_static_path"] = [str(ZDOCS_DOC_DIR / "_static")] + [
        str(p) for p in (static_path or [])
    ]
    namespace["html_css_files"] = ["zdocs-sphinx.css"] + list(css_files or [])
    if refs is not None:
        # Consumed by the cross-document navigation in the page template.
        namespace["html_context"] = {"reference_groups": refs.reference_groups}

    if testmodule is not None:
        namespace["testmodule_xml_dir"] = testmodule["xml_dir"]
        namespace["testspec_doxygen_url"] = testmodule["doxygen_url"]
        namespace["api_doxygen_url"] = testmodule["api_url"]
        namespace["testspec_needs_json"] = testmodule["needs_json"]
        namespace["testmodule_root"] = str(project_base) if project_base else ""
        namespace["twister_output_dir"] = os.environ.get("ZDOCS_TWISTER_OUT", "")
        namespace["twisterinfo_project_name"] = project
        namespace["twisterinfo_project_version"] = version
