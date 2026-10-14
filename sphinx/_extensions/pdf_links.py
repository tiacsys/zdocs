# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: the links of a PDF go into the PDF set, and none is dead.

**Into the PDF set.** The PDFs of a document set go into one folder,
``deploy/pdf``, as ``<title>_<version>.pdf`` (``docrefs.py pdf-deliver``). A
link to a page of a peer in the set (``<peer URL>/<page>.html#<anchor>``)
becomes a link to the peer's PDF and the named destination of that label:
``<file>#<page>:<anchor>``, or ``<file>#<page>::doc`` for a page without an
anchor. The destinations exist because zdocs_conf sets hyperref's
``destlabel``: each LaTeX label is a destination of the same name. hyperref
writes such a link as a "go to remote" action (GoToR), file and destination.
``zdocs_pdf_peers`` (from docrefs) maps each peer's URL to its file.

**No dead link.** A PDF has no sibling tree of HTML pages. Two kinds of link
from the HTML world are dead in it:

- a relative link, such as ``../../dox-api/main_8c_source.html``: it
  resolves against the folder of the PDF, where no such page is;
- a link to a local server (``localhost`` or a loopback address): the
  registry's ``base_url`` of a development build.

In a LaTeX build, this extension writes such a link as its text, without the
link, and warns once per document. Set ``ZDOCS_DOC_BASE_URL`` to the
published site to keep the links to other documents. Links inside the PDF and
links to another host stay as they are.

It runs on ``doctree-resolved``, after sphinx-needs has written the links of
the needs (doctree-resolved at the default priority 500).
"""

import ipaddress
from urllib.parse import unquote, urlsplit

from docutils import nodes

from sphinx.util import logging

logger = logging.getLogger(__name__)


def local_host(host):
    """Whether ``host`` is this machine: ``localhost``, a loopback address or
    the unspecified address."""
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def dead_in_pdf(uri):
    """Whether ``uri`` (a ``refuri``) has no target from a PDF."""
    if not uri or uri.startswith(("#", "%")):  # inside the document
        return False
    parts = urlsplit(uri)
    if parts.scheme in ("http", "https"):
        return local_host(parts.hostname)
    if parts.scheme == "file":
        return True
    return not parts.scheme  # a relative path; mailto: and the like stay


def pdf_target(uri, peers):
    """``uri`` as a link into the PDF set (``<file>#<page>:<anchor>``), or
    ``None`` if it goes to no peer in ``peers`` (``{peer URL: file}``)."""
    for base, name in peers.items():
        base = base.rstrip("/")
        if uri != base and not uri.startswith(base + "/"):
            continue
        path, _, frag = unquote(uri[len(base):].lstrip("/")).partition("#")
        if path.endswith(".html"):
            page = path[: -len(".html")]
        else:
            page = f"{path.rstrip('/')}/index" if path else "index"
        return f"{name}#{page}:{frag}" if frag else f"{name}#{page}::doc"
    return None


def _unlink(app, doctree, docname):
    if app.builder.format != "latex":
        return
    peers = getattr(app.config, "zdocs_pdf_peers", None) or {}
    for ref in doctree.findall(nodes.reference):
        target = pdf_target(ref.get("refuri", ""), peers) if not ref.get("refid") else None
        if target:
            ref["refuri"] = target
            ref["classes"].append("zd-pdf-set")
    # Not by the "internal" flag: sphinx-needs sets it on a needtable link to
    # a need of another document too. In LaTeX, a link inside the document
    # starts with "%" or "#", which dead_in_pdf keeps.
    dead = [
        ref for ref in doctree.findall(nodes.reference)
        if not ref.get("refid")
        and "zd-pdf-set" not in ref["classes"]
        and dead_in_pdf(ref.get("refuri"))
    ]
    for ref in dead:
        ref.replace_self(nodes.inline(ref.rawsource, "", *ref.children, classes=ref["classes"]))
    if dead:
        logger.warning(
            f"pdf_links: {len(dead)} link(s) written as text, without the link: they "
            f"go to a local server or to an HTML path next to the PDF (the first: "
            f"{dead[0].get('refuri')}). Set ZDOCS_DOC_BASE_URL to the published site "
            f"to keep the links to other documents.",
            location=docname,
            type="zdocs",
            subtype="pdf_links",
        )


def setup(app):
    # {peer URL: PDF file name}, set by zdocs_conf from the registry.
    app.add_config_value("zdocs_pdf_peers", {}, "env")
    app.connect("doctree-resolved", _unlink, priority=900)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
