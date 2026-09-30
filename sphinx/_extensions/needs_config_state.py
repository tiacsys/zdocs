# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: re-read a document when its needs vocabulary or imports change.

A document's need types, links and fields come from a TOML file
(``needs_from_toml``, set by ``zdocs_conf`` from ``ZDOCS_NEEDS_CONFIG``).
Sphinx re-reads every document when a config value registered with rebuild
``"env"`` changes, but sphinx-needs registers ``needs_types``,
``needs_links`` and ``needs_fields`` with rebuild ``"html"``, and the config
value ``needs_from_toml`` is only the file's path. So after the file gains a
link type, an incremental build reuses the pickled needs, which have no entry
for the new link, and the first new need that uses it crashes the build:
``KeyError: "Link type 'fulfills' does not exist in backlinks."``. A clean
build works.

This extension registers ``zdocs_needs_config_digest``, rebuild ``"env"``,
and sets it to the SHA-256 of the file's content. A change to the file changes
the value, and Sphinx re-reads the document ("config changed"). The value is
the same for both build stages, so the stage caches stay valid while the file
does not change.

Re-reading is not enough when a link type is REMOVED: the pickled environment
still holds needs imported from a peer's needs.json under the old vocabulary,
and the importing document crashes the same way once, although the peer's
file no longer has the link. So on a change the pickled environment is also
dropped before Sphinx loads it (``config-inited`` runs first), and the
document starts from a fresh one, as in a clean build. The digests the
environment was built with are kept beside it, in the doctree directory.

The needs that a document imports (``needs_external_needs``) have a
similar problem. sphinx-needs loads them again on each build, but Sphinx
writes only the pages of the documents that it read. When a peer's
needs.json gains a need that links to a need of this document, the source of
the page with that need does not change. So Sphinx does not write the page
again, and the page does not show the new incoming link. For example, a
requirement page did not show "assessed by" after the test report gained
adequacy needs.

So the extension also registers ``zdocs_imported_needs_digest``, rebuild
``"env"``: a SHA-256 over the needs that each imported file gives. A change
to it also starts from a fresh environment. This also removes the needs that
a peer no longer has.
"""

import hashlib
import json
from pathlib import Path

from sphinx.util import logging

logger = logging.getLogger(__name__)

CONFIG_NAME = "zdocs_needs_config_digest"
IMPORTS_CONFIG_NAME = "zdocs_imported_needs_digest"

#: Beside the pickled environment: the digests it was built with.
STAMP_NAME = "zdocs-needs-config.sha256"
#: Sphinx's pickled environment in the doctree directory.
ENV_PICKLE = "environment.pickle"


def needs_config_digest(confdir, from_toml):
    """SHA-256 of the needs TOML file, or ``""`` if none is set or it is unreadable.

    ``from_toml`` is resolved against ``confdir``, as sphinx-needs resolves it.
    """
    if not from_toml:
        return ""
    try:
        data = Path(confdir, from_toml).resolve().read_bytes()
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()


def _imported_content(json_path, version):
    """The part of a needs.json that sphinx-needs imports, as canonical JSON.

    That is the needs of the imported version (``version``, else the file's
    ``current_version``) and its schema, which gives the defaults. The
    ``<link>_back`` fields are not part of it: sphinx-needs does not import
    them, and when two documents import each other, they would make each
    document read again one more time after each change. A missing or
    unreadable file gives a fixed marker, so that its return is a change too.
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        versions = data.get("versions") or {}
        entry = versions.get(version or data.get("current_version"), {})
    except (OSError, ValueError, AttributeError):
        return "unreadable"
    needs = {
        need_id: {k: v for k, v in need.items() if not k.endswith("_back")}
        for need_id, need in (entry.get("needs") or {}).items()
    }
    return json.dumps([needs, entry.get("needs_schema")], sort_keys=True, default=str)


def imported_needs_digest(confdir, external_needs):
    """SHA-256 over the needs that ``needs_external_needs`` imports, or ``""`` if none.

    Only ``json_path`` sources count. A relative path is resolved against
    ``confdir``, as sphinx-needs resolves it. A ``json_url`` source is not read.
    """
    sha = hashlib.sha256()
    count = 0
    for source in external_needs or []:
        json_path = source.get("json_path") if isinstance(source, dict) else None
        if not json_path:
            continue
        path = Path(confdir, json_path)
        sha.update(f"{path}\0{_imported_content(path, source.get('version'))}\0".encode())
        count += 1
    return sha.hexdigest() if count else ""


def drop_stale_environment(doctreedir, digest):
    """Delete the pickled environment in ``doctreedir`` unless it was built with ``digest``.

    An environment with no recorded digest (a build dir from before this
    extension) counts as stale. Returns whether one was deleted; records
    ``digest`` either way.
    """
    doctreedir = Path(doctreedir)
    stamp = doctreedir / STAMP_NAME
    pickle = doctreedir / ENV_PICKLE
    try:
        recorded = stamp.read_text().strip()
    except OSError:
        recorded = None
    dropped = False
    if pickle.exists() and recorded != digest:
        pickle.unlink()
        dropped = True
    if recorded != digest:
        doctreedir.mkdir(parents=True, exist_ok=True)
        stamp.write_text(digest + "\n")
    return dropped


def _set_digests(app, config):
    digest = needs_config_digest(app.confdir, getattr(config, "needs_from_toml", None))
    imports = imported_needs_digest(app.confdir, getattr(config, "needs_external_needs", None))
    config[CONFIG_NAME] = digest
    config[IMPORTS_CONFIG_NAME] = imports
    if drop_stale_environment(app.doctreedir, f"{digest}:{imports}"):
        logger.info(
            "needs vocabulary or imported needs changed: starting from a fresh environment"
        )


def setup(app):
    app.add_config_value(CONFIG_NAME, "", "env")
    app.add_config_value(IMPORTS_CONFIG_NAME, "", "env")
    app.connect("config-inited", _set_digests)
    return {"version": "0.2", "parallel_read_safe": True, "parallel_write_safe": True}
