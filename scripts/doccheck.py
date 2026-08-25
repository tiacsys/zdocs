#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Post-build integrity checks for the document set.

Two failures this catches, both of which shipped silently before it existed:

  A. A cross-reference in the rendered smoke-test page did not resolve.  The
     `:external+<inv>:` intersphinx role runs at PARSE time, so if the peer's
     objects.inv did not exist yet it emits NOTHING AT ALL -- not a broken link,
     not plain text, an empty node.  Invisible in the log, invisible on the page
     unless you know what should be there.

  B. A link into the deploy tree points at a file that is not there.

Both need a built deploy tree, so `--deploy` is required.  There is no
sources-only mode: a run that checks nothing must not be able to print OK.

A third check was removed rather than fixed.  It scanned document sources for
tokens shaped like a document id and reported any that the registry did not
declare, to catch content still naming a removed document.  Recognising an id
by shape means hardcoding one project's naming convention -- the regex was
`dox-|docctl-|sop-` -- which is an engine constant standing in for a consumer's
vocabulary, and it cannot be derived from the registry instead: an id that IS
in the registry is precisely the case the check must not flag.  It also made
documentation ABOUT this engine unwritable, since every example id in a
tutorial was a finding.

Usage:  doccheck.py --registry doc/documents.yaml --deploy DIR
Exit:   0 clean, 1 findings, 2 bad invocation.
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import yaml


class _ListItemLinks(HTMLParser):
    """Collect (text, had_link) for every <li> in the cross-reference sections."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, bool]] = []
        self._depth = 0
        self._text: list[str] = []
        self._link = False

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self._depth += 1
            if self._depth == 1:
                self._text, self._link = [], False
        elif tag == "a" and self._depth:
            self._link = True

    def handle_endtag(self, tag):
        if tag == "li" and self._depth:
            if self._depth == 1:
                self.items.append(("".join(self._text).strip(), self._link))
            self._depth -= 1

    def handle_data(self, data):
        if self._depth:
            self._text.append(data)


def check_xref_smoketest(deploy: Path, smoke_page: str) -> list[str]:
    """B. Every bullet in the rendered cross-reference test must have resolved.

    The page exists to exercise every link channel from content.  A bullet with
    no <a> in it is a channel that silently produced nothing.

    Its location is a CONSUMER setting (`xref_smoketest:` in the registry), not a
    constant: it used to be hardcoded to one project's
    `docctl-swds/html/architecture/xref-test.html`, so for every other project
    this check reported "smoke test not found" -- a finding about the checker's
    own configuration, on every run, which is the fastest way to teach people to
    ignore it.
    """
    page = deploy / smoke_page
    if not page.exists():
        return [
            f"{page}: cross-reference smoke test not found in the deploy tree "
            f"(registry says xref_smoketest: {smoke_page})"
        ]

    html = page.read_text(encoding="utf-8", errors="replace")
    # Scope to the rendered article: the theme's sidebar, breadcrumb and footer
    # are full of <li> that have nothing to do with this test.
    body = html.find('itemprop="articleBody"')
    if body != -1:
        html = html[body:]

    parser = _ListItemLinks()
    parser.feed(html)
    if not parser.items:
        return [f"{page}: no list items found -- page structure changed?"]

    findings = []
    for text, had_link in parser.items:
        # Prose asides and the needtable rows have no link by design; only items
        # shaped like "Label: <reference>" are the cross-reference bullets.
        if had_link or ":" not in text:
            continue
        label, _, target = text.partition(":")
        label = label.strip()
        if target.strip():
            # Plain text rather than a link. Tolerated ANYWHERE ELSE -- a
            # degraded reference is still readable -- but not here: every bullet
            # on this page exists to prove one link channel works, so one that
            # renders unlinked means that channel is broken. This was found the
            # hard way: a rebase onto a branch without the API sources left all
            # five doxylink bullets as plain text, and the build stayed green
            # because this check only looked for EMPTY renders.
            findings.append(
                f"{page.name}: '{label}' rendered as PLAIN TEXT, not a link -- "
                f"the target symbol/document is missing from this build. Point it "
                f"at something this branch actually builds, or fix the target."
            )
        else:
            findings.append(
                f"{page.name}: '{label}' rendered EMPTY -- its cross-reference "
                f"produced no output at all (parse-time role with a missing inventory?)"
            )
    return findings


HREF_RE = re.compile(r'href="([^"#?]+)', re.I)

#: Excluded from the dead-link scan by BASENAME, not by path: these files are
#: generated per Doxygen document, so a path list would need one entry per
#: document and would silently miss the next one added.
#:
#: ``doxygen_crawl.html`` is Doxygen's own machine-facing page — it titles itself
#: "Validator / crawler helper" and exists so a crawler can reach pages the
#: JavaScript navigation hides. It is not a document page: nobody reads it, and
#: nothing in a docset navigates to it.
#:
#: It must be excluded because Doxygen lists entities known only from a TAG FILE
#: in it, under LOCAL filenames. A document that mentions a namespace its peer
#: documents (here: `utils`, owned by another Doxygen document and reached through
#: its tag file) correctly gets no local page for it in stage 2 — Doxygen knows it
#: is external — yet the crawl helper still names `namespaceutils.html` as though
#: it were local. That is a defect in a helper file, with no user-visible effect,
#: and it is unfixable from this side.
#:
#: Two reasons not to leave it in scope. It would fail the build of every
#: consumer whose Doxygen documents share a namespace, permanently and with no
#: available fix — and a check that fails for reasons the author cannot act on is
#: how people learn to ignore the check (the same argument this file already makes
#: about the smoke page's hardcoded path). And it costs no coverage: every
#: DOCUMENT page's links are still scanned, and the crawl helper only ever
#: enumerates pages Doxygen generated or knows of, so a genuinely dead link in it
#: is either also present on a real page or points at something no reader can
#: reach.
#:
#: This masked a real defect once, so it is worth knowing what it does NOT hide:
#: before stage 1 stopped generating HTML, stage 1 (which has no TAGFILES and so
#: DID emit a local `namespaceutils.html`) left that file behind for stage 2 to
#: not overwrite, and the link resolved by accident. Fixing the stage-1 overwrite
#: removed the accidental file and exposed this. Incremental build trees still
#: hold the stale page, so this only reproduces on a CLEAN build.
_DEPLOY_LINK_SCAN_EXCLUDED = {"doxygen_crawl.html"}


def check_deploy_links(deploy: Path, base_url: str) -> list[str]:
    """C. Deploy-internal links that point at a missing file."""
    findings = []
    seen: set[tuple[str, str]] = set()
    for page in sorted(deploy.rglob("*.html")):
        if page.name in _DEPLOY_LINK_SCAN_EXCLUDED:
            continue
        text = page.read_text(encoding="utf-8", errors="replace")
        for href in HREF_RE.findall(text):
            if base_url and href.startswith(base_url):
                target = deploy / href[len(base_url) :].lstrip("/")
            elif href.startswith(("http://", "https://", "mailto:", "//", "javascript:")):
                continue
            else:
                target = (page.parent / href).resolve()
            try:
                target.relative_to(deploy.resolve())
            except ValueError:
                continue  # escapes the deploy tree; not ours to police
            if target.exists():
                continue
            key = (str(page.relative_to(deploy)), href)
            if key in seen:
                continue
            seen.add(key)
            findings.append(f"{key[0]}: dead link -> {href}")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, required=True)
    ap.add_argument(
        "--deploy",
        type=Path,
        required=True,
        help="built deploy/ tree — both checks read it, so it is not optional",
    )
    args = ap.parse_args()

    if not args.registry.is_file():
        print(f"doccheck: no registry at {args.registry}", file=sys.stderr)
        return 2

    raw = yaml.safe_load(args.registry.read_text(encoding="utf-8"))
    base_url = (raw.get("base_url") or "").rstrip("/")
    smoke_page = raw.get("xref_smoketest")

    if not args.deploy.is_dir():
        print(f"doccheck: no deploy tree at {args.deploy}", file=sys.stderr)
        return 2

    groups: list[tuple[str, list[str]]] = []
    if smoke_page:
        groups.append(
            ("unresolved cross-references", check_xref_smoketest(args.deploy, smoke_page))
        )
    groups.append(("dead deploy links", check_deploy_links(args.deploy, base_url)))

    total = 0
    for title, findings in groups:
        if findings:
            total += len(findings)
            print(f"\ndoccheck: {title} ({len(findings)}):", file=sys.stderr)
            for f in findings:
                print(f"  {f}", file=sys.stderr)

    if total:
        print(f"\ndoccheck: FAILED with {total} finding(s)", file=sys.stderr)
        return 1
    checked = "deploy tree"
    if not smoke_page:
        # Said out loud rather than skipped quietly: a check that is not running
        # must not look like a check that passed.
        checked += ", no xref_smoketest configured"
    print(f"doccheck: OK ({checked})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
