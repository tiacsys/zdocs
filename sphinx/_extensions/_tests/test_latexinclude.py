# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the two path spellings `latexinclude` accepts.

The directive's real behaviour is covered end-to-end by the acceptance suite
(tests/test_15_latex.py, which builds a PDF and greps it). These tests pin the
PATH RESOLUTION on its own, because that is the part with two bases and a
depth-dependence that a passing PDF build does not distinguish: an
authored-relative path and a source-tree-absolute one can both be right for the
same file, and only one of them stays right when the document moves.
"""

import types

import pytest
from sphinx.errors import ExtensionError

import latexinclude


def _directive(argument, *, confdir, srcdir, docname, builder_format="latex"):
    """A LatexIncludeDirective wired to just the attributes run() reads."""
    env = types.SimpleNamespace(
        app=types.SimpleNamespace(
            confdir=str(confdir),
            builder=types.SimpleNamespace(format=builder_format),
        ),
        srcdir=str(srcdir),
        docname=docname,
        note_dependency=lambda path: None,
    )
    inserted = []
    state = types.SimpleNamespace(
        document=types.SimpleNamespace(
            settings=types.SimpleNamespace(env=env),
        )
    )
    state_machine = types.SimpleNamespace(
        insert_input=lambda lines, source: inserted.append((lines, source)),
        # docutils' Directive.__init__ reads this; nothing here uses it.
        reporter=types.SimpleNamespace(),
    )
    d = latexinclude.LatexIncludeDirective(
        "latexinclude", [argument], {}, [], 1, 0, "", state, state_machine
    )
    return d, inserted


@pytest.fixture
def tree(tmp_path):
    """A doc root holding the shared file, plus one document at each depth.

    doc/_glossary_terms.rst
    doc/handbook/            <- depth 1
    doc/qms/handbook/        <- depth 2
    """
    shared = tmp_path / "_glossary_terms.rst"
    shared.write_text("Shared glossary line\n", encoding="utf-8")
    (tmp_path / "handbook").mkdir()
    (tmp_path / "qms" / "handbook").mkdir(parents=True)
    # the copied source tree, as external_content_contents would leave it
    srcdir = tmp_path / "build" / "src"
    srcdir.mkdir(parents=True)
    (srcdir / "_glossary_terms.rst").write_text("Copied glossary line\n", encoding="utf-8")
    return tmp_path, srcdir


# ---------------------------------------------------------------------------
# authored-relative (the original spelling) — must keep working
# ---------------------------------------------------------------------------


def test_authored_relative_resolves_from_depth_one(tree):
    root, srcdir = tree
    d, inserted = _directive(
        "../_glossary_terms.rst",
        confdir=root / "handbook",
        srcdir=srcdir,
        docname="doc-control",
    )
    assert d.run() == []
    assert inserted[0][0] == ["Shared glossary line"]


def test_authored_relative_is_depth_dependent(tree):
    """The defect this whole change exists to remove: the SAME directive text,
    in a document one level deeper, resolves somewhere else and fails."""
    root, srcdir = tree
    d, _ = _directive(
        "../_glossary_terms.rst",
        confdir=root / "qms" / "handbook",
        srcdir=srcdir,
        docname="doc-control",
    )
    with pytest.raises(ExtensionError) as exc:
        d.run()
    assert "no such file" in str(exc.value)
    assert "AUTHORED directory" in str(exc.value)


# ---------------------------------------------------------------------------
# source-tree-absolute (the new spelling) — depth-independent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "confdir_parts",
    [("handbook",), ("qms", "handbook")],
    ids=["depth-1", "depth-2"],
)
def test_srcdir_absolute_resolves_identically_at_any_depth(tree, confdir_parts):
    root, srcdir = tree
    d, inserted = _directive(
        "/_glossary_terms.rst",
        confdir=root.joinpath(*confdir_parts),
        srcdir=srcdir,
        docname="doc-control",
    )
    assert d.run() == []
    # the COPY in the source tree, not the authored original
    assert inserted[0][0] == ["Copied glossary line"]


def test_srcdir_absolute_ignores_docname_subdirectory(tree):
    """A source-tree path must not pick up the including file's sub-directory
    the way an authored-relative one does."""
    root, srcdir = tree
    d, inserted = _directive(
        "/_glossary_terms.rst",
        confdir=root / "handbook",
        srcdir=srcdir,
        docname="chapters/deep/doc-control",
    )
    assert d.run() == []
    assert inserted[0][0] == ["Copied glossary line"]


def test_srcdir_absolute_missing_file_names_the_source_tree(tree):
    root, srcdir = tree
    d, _ = _directive(
        "/nope.rst", confdir=root / "handbook", srcdir=srcdir, docname="doc-control"
    )
    with pytest.raises(ExtensionError) as exc:
        d.run()
    msg = str(exc.value)
    assert "SOURCE TREE" in msg
    assert "external_content_contents" in msg


# ---------------------------------------------------------------------------
# builder gating is unchanged by either spelling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argument", ["../_glossary_terms.rst", "/_glossary_terms.rst"])
def test_non_latex_builders_skip_without_touching_the_filesystem(tree, argument):
    """Including for html would give that reader a duplicate of a page they can
    already open — and would register every term twice."""
    root, srcdir = tree
    d, inserted = _directive(
        argument,
        confdir=root / "handbook",
        srcdir=srcdir,
        docname="doc-control",
        builder_format="html",
    )
    assert d.run() == []
    assert inserted == []


def test_a_missing_file_is_not_reported_for_a_non_latex_builder(tree):
    """The skip happens first, so an html build of a document whose glossary is
    absent still builds — the error is a LaTeX-build concern."""
    root, srcdir = tree
    d, _ = _directive(
        "/nope.rst",
        confdir=root / "handbook",
        srcdir=srcdir,
        docname="doc-control",
        builder_format="html",
    )
    assert d.run() == []
