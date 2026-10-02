# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: re-read a document when its needs vocabulary changes.

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
document starts from a fresh one, as in a clean build. The digest the
environment was built with is kept beside it, in the doctree directory.
"""

import hashlib
from pathlib import Path

from sphinx.util import logging

logger = logging.getLogger(__name__)

CONFIG_NAME = "zdocs_needs_config_digest"

#: Beside the pickled environment: the digest it was built with.
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


def _set_digest(app, config):
    digest = needs_config_digest(app.confdir, getattr(config, "needs_from_toml", None))
    config[CONFIG_NAME] = digest
    if drop_stale_environment(app.doctreedir, digest):
        logger.info("needs vocabulary changed: starting from a fresh environment")


def setup(app):
    app.add_config_value(CONFIG_NAME, "", "env")
    app.connect("config-inited", _set_digest)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
