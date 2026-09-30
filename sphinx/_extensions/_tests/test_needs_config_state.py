# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""needs_config_state — incremental builds after the needs TOML or an import changes.

sphinx-needs registers its types, links and fields with rebuild "html", so a
change to the TOML they come from did not re-read any document. The pickled
needs had no entry for a new link type, and the first need using it crashed the
build: ``KeyError: "Link type 'fulfills' does not exist in backlinks."``.

A change to an imported needs.json (``needs_external_needs``) did not write the
importing document's pages again either, so a new incoming link from a peer's
need did not show on the page of the linked need.
"""

import json

from pathlib import Path

import needs_config_state as ncs
import pytest

_EXTENSIONS = str(Path(__file__).resolve().parents[1])

_TOML = """\
[needs]
id_regex = "^[A-Z][A-Z0-9_]+"

[[needs.types]]
directive = "req"
title = "Requirement"
prefix = "R_"

[[needs.types]]
directive = "spec"
title = "Specification"
prefix = "S_"

[needs.links.verifies]
incoming = "verified by"
outgoing = "verifies"
"""

_NEW_LINK = """
[needs.links.fulfills]
incoming = "fulfilled by"
outgoing = "fulfills"
"""

_INDEX = """\
Index
=====

.. toctree::

   other

.. req:: A requirement
   :id: REQ_001

.. spec:: A specification
   :id: SPEC_001
   :verifies: REQ_001
"""

_OTHER = "Other\n=====\n"

_OTHER_WITH_NEW_LINK = _OTHER + """
.. spec:: A design
   :id: SPEC_002
   :fulfills: REQ_001
"""


def _project(root, extensions):
    src = root / "src"
    src.mkdir(parents=True)
    (src / "conf.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {_EXTENSIONS!r})\n"
        f"extensions = {extensions!r}\n"
        "needs_from_toml = 'needs.toml'\n"
        "suppress_warnings = ['config.cache']\n"
    )
    (src / "needs.toml").write_text(_TOML)
    (src / "index.rst").write_text(_INDEX)
    (src / "other.rst").write_text(_OTHER)
    return src


def _add_link_type_and_use_it(src):
    """What order 006 did: a new link in the TOML, a new need in another page."""
    (src / "needs.toml").write_text(_TOML + _NEW_LINK)
    (src / "other.rst").write_text(_OTHER_WITH_NEW_LINK)


# ---------------------------------------------------------------------------
# The digest
# ---------------------------------------------------------------------------


def test_digest_is_empty_without_a_file(tmp_path):
    assert ncs.needs_config_digest(tmp_path, None) == ""
    assert ncs.needs_config_digest(tmp_path, "") == ""
    assert ncs.needs_config_digest(tmp_path, "missing.toml") == ""


def test_digest_follows_the_content_not_the_mtime(tmp_path):
    toml = tmp_path / "needs.toml"
    toml.write_text(_TOML)
    first = ncs.needs_config_digest(tmp_path, "needs.toml")
    toml.write_text(_TOML)  # rewritten, same content
    assert ncs.needs_config_digest(tmp_path, "needs.toml") == first
    toml.write_text(_TOML + _NEW_LINK)
    assert ncs.needs_config_digest(tmp_path, "needs.toml") not in ("", first)


def test_digest_resolves_a_relative_path_against_the_conf_dir(tmp_path):
    (tmp_path / "cfg").mkdir()
    (tmp_path / "needs.toml").write_text(_TOML)
    rel = ncs.needs_config_digest(tmp_path / "cfg", "../needs.toml")
    assert rel == ncs.needs_config_digest(tmp_path, str(tmp_path / "needs.toml")) != ""


# ---------------------------------------------------------------------------
# The incremental build
# ---------------------------------------------------------------------------


def test_incremental_build_after_a_new_link_type(make_app, tmp_path):
    src = _project(tmp_path, ["sphinx_needs", "needs_config_state"])
    make_app("html", srcdir=src).build()

    _add_link_type_and_use_it(src)
    app = make_app("html", srcdir=src)
    app.build()  # raised KeyError before the fix

    assert app.statuscode == 0
    assert "starting from a fresh environment" in app._status.getvalue()
    index = (Path(app.outdir) / "index.html").read_text()
    assert "fulfilled by" in index and "SPEC_002" in index


def test_unchanged_toml_keeps_the_cache(make_app, tmp_path):
    src = _project(tmp_path, ["sphinx_needs", "needs_config_state"])
    make_app("html", srcdir=src).build()

    (src / "needs.toml").write_text(_TOML)  # touched, same content
    app = make_app("html", srcdir=src)
    app.build()
    assert "config changed" not in app._status.getvalue()
    assert "0 added, 0 changed, 0 removed" in app._status.getvalue()


def test_removing_a_used_link_type_does_not_crash_an_importer(make_app, tmp_path):
    """The other direction: a peer drops a link type its needs used.

    The importing document's pickled environment still held the peer's needs
    under the old vocabulary; re-reading alone crashed it once with the same
    KeyError, so the environment is dropped instead.
    """
    peer = _project(tmp_path / "peer", ["sphinx_needs", "needs_config_state"])
    importer = _project(tmp_path / "importer", ["sphinx_needs", "needs_config_state"])
    toml = tmp_path / "needs.toml"
    toml.write_text(_TOML)
    peer_json = tmp_path / "peer" / "src" / "_build" / "html" / "needs.json"
    for src, extra in (
        (peer, "needs_build_json = True\nversion = '1.0'\n"),
        (importer, f"version = '1.0'\nneeds_external_needs = [{{'json_path': {str(peer_json)!r}, "
                   "'base_url': 'http://peer/', 'version': '1.0', 'id_prefix': 'P'}]\n"),
    ):
        conf = src / "conf.py"
        conf.write_text(conf.read_text().replace("'needs.toml'", repr(str(toml))) + extra)

    def build_both():
        for src in (peer, importer):
            app = make_app("html", srcdir=src)
            app.build()
            assert app.statuscode == 0

    build_both()
    _add_link_type_and_use_it(peer)
    toml.write_text(_TOML + _NEW_LINK)
    build_both()
    toml.write_text(_TOML)
    (peer / "other.rst").write_text(_OTHER)
    build_both()  # the importer raised KeyError here with re-reading alone


def test_drop_stale_environment(tmp_path):
    pickle = tmp_path / ncs.ENV_PICKLE
    pickle.write_bytes(b"env")
    assert ncs.drop_stale_environment(tmp_path, "d1")  # no stamp: stale
    assert not pickle.exists()
    pickle.write_bytes(b"env")
    assert not ncs.drop_stale_environment(tmp_path, "d1")
    assert pickle.exists()
    assert ncs.drop_stale_environment(tmp_path, "d2")
    assert (tmp_path / ncs.STAMP_NAME).read_text().strip() == "d2"


def test_control_without_the_extension_the_build_crashes(make_app, tmp_path):
    """The defect, pinned against sphinx-needs as installed.

    Should this start failing after a sphinx-needs upgrade, sphinx-needs now
    re-reads on a vocabulary change itself, and the extension may be obsolete.
    """
    src = _project(tmp_path, ["sphinx_needs"])
    make_app("html", srcdir=src).build()

    _add_link_type_and_use_it(src)
    app = make_app("html", srcdir=src)
    with pytest.raises(Exception, match="does not exist in backlinks"):
        app.build()


# ---------------------------------------------------------------------------
# Imported needs
# ---------------------------------------------------------------------------

_PEER_INDEX = """\
Peer
====

.. spec:: A specification
   :id: SPEC_001
   :verifies: REQ_001
"""

_PEER_NEW_NEED = """
.. spec:: A later specification
   :id: SPEC_002
   :verifies: REQ_001
"""

_IMPORTER_INDEX = """\
Importer
========

.. req:: A requirement
   :id: REQ_001
"""


def _needs_json(path, needs, **extra):
    data = {"current_version": "1.0", "versions": {"1.0": {"needs": needs, **extra}}}
    path.write_text(json.dumps(data))


def test_imported_digest_is_empty_without_a_json_path_source(tmp_path):
    assert ncs.imported_needs_digest(tmp_path, None) == ""
    assert ncs.imported_needs_digest(tmp_path, []) == ""
    assert ncs.imported_needs_digest(tmp_path, [{"json_url": "http://peer/needs.json"}]) == ""


def test_imported_digest_follows_the_imported_needs(tmp_path):
    peer = tmp_path / "needs.json"
    sources = [{"json_path": str(peer), "base_url": "http://peer"}]
    missing = ncs.imported_needs_digest(tmp_path, sources)
    _needs_json(peer, {"SPEC_001": {"id": "SPEC_001", "verifies": ["REQ_001"]}})
    first = ncs.imported_needs_digest(tmp_path, sources)
    assert first not in ("", missing)

    # Not imported by sphinx-needs, so not part of the digest.
    _needs_json(
        peer,
        {"SPEC_001": {"id": "SPEC_001", "verifies": ["REQ_001"], "verifies_back": ["X"]}},
        creator={"program": "other"},
    )
    assert ncs.imported_needs_digest(tmp_path, sources) == first

    _needs_json(
        peer,
        {
            "SPEC_001": {"id": "SPEC_001", "verifies": ["REQ_001"]},
            "SPEC_002": {"id": "SPEC_002", "verifies": ["REQ_001"]},
        },
    )
    assert ncs.imported_needs_digest(tmp_path, sources) != first


def test_imported_digest_reads_the_configured_version(tmp_path):
    peer = tmp_path / "needs.json"
    data = {
        "current_version": "2.0",
        "versions": {"1.0": {"needs": {"A": {"id": "A"}}}, "2.0": {"needs": {}}},
    }
    peer.write_text(json.dumps(data))
    pinned = ncs.imported_needs_digest(tmp_path, [{"json_path": str(peer), "version": "1.0"}])
    current = ncs.imported_needs_digest(tmp_path, [{"json_path": str(peer)}])
    assert pinned != current


def test_imported_digest_resolves_a_relative_path_against_the_conf_dir(tmp_path):
    (tmp_path / "cfg").mkdir()
    _needs_json(tmp_path / "needs.json", {"A": {"id": "A"}})
    rel = ncs.imported_needs_digest(tmp_path / "cfg", [{"json_path": "../needs.json"}])
    _needs_json(tmp_path / "needs.json", {})
    assert ncs.imported_needs_digest(tmp_path / "cfg", [{"json_path": "../needs.json"}]) != rel


def _peer_and_importer(tmp_path, extensions):
    toml = tmp_path / "needs.toml"
    toml.write_text(_TOML)
    peer = tmp_path / "peer"
    importer = tmp_path / "importer"
    peer_json = peer / "_build" / "html" / "needs.json"
    for src, index, extra in (
        (peer, _PEER_INDEX, "needs_build_json = True\n"),
        (importer, _IMPORTER_INDEX, f"needs_external_needs = [{{'json_path': {str(peer_json)!r}, "
                                    "'base_url': 'http://peer', 'version': '1.0'}]\n"),
    ):
        src.mkdir()
        (src / "conf.py").write_text(
            "import sys\n"
            f"sys.path.insert(0, {_EXTENSIONS!r})\n"
            f"extensions = {extensions!r}\n"
            f"needs_from_toml = {str(toml)!r}\n"
            "version = '1.0'\n"
            "suppress_warnings = ['config.cache', 'needs.link_outgoing']\n" + extra
        )
        (src / "index.rst").write_text(index)
    return peer, importer


def _build(make_app, src):
    app = make_app("html", srcdir=src)
    app.build()
    assert app.statuscode == 0
    return app


def _peer_gains_a_need(make_app, tmp_path, extensions):
    """Build both, add a peer need that links to the importer's need, build both again."""
    peer, importer = _peer_and_importer(tmp_path, extensions)
    _build(make_app, peer)
    _build(make_app, importer)
    (peer / "index.rst").write_text(_PEER_INDEX + _PEER_NEW_NEED)
    _build(make_app, peer)
    app = _build(make_app, importer)
    return app, (Path(app.outdir) / "index.html").read_text()


def test_a_new_incoming_link_from_an_import_shows(make_app, tmp_path):
    app, page = _peer_gains_a_need(make_app, tmp_path, ["sphinx_needs", "needs_config_state"])
    assert "starting from a fresh environment" in app._status.getvalue()
    assert "SPEC_001" in page and "SPEC_002" in page  # SPEC_002 was missing


def test_an_unchanged_import_keeps_the_cache(make_app, tmp_path):
    peer, importer = _peer_and_importer(tmp_path, ["sphinx_needs", "needs_config_state"])
    _build(make_app, peer)
    _build(make_app, importer)
    _build(make_app, peer)  # writes needs.json again, with the same needs
    status = _build(make_app, importer)._status.getvalue()
    assert "fresh environment" not in status
    assert "0 added, 0 changed, 0 removed" in status


def test_a_need_the_peer_removes_goes_from_the_page(make_app, tmp_path):
    peer, importer = _peer_and_importer(tmp_path, ["sphinx_needs", "needs_config_state"])
    (peer / "index.rst").write_text(_PEER_INDEX + _PEER_NEW_NEED)
    _build(make_app, peer)
    _build(make_app, importer)
    (peer / "index.rst").write_text(_PEER_INDEX)
    _build(make_app, peer)
    app = _build(make_app, importer)
    assert "SPEC_002" not in (Path(app.outdir) / "index.html").read_text()


def test_control_without_the_extension_the_new_link_is_missing(make_app, tmp_path):
    """The defect, pinned against sphinx-needs as installed.

    If this starts to fail after an upgrade, Sphinx or sphinx-needs now writes
    the pages again when an import changes, and this part of the extension can
    be obsolete.
    """
    _, page = _peer_gains_a_need(make_app, tmp_path, ["sphinx_needs"])
    assert "SPEC_001" in page and "SPEC_002" not in page
