# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""needs_config_state — an incremental build after the needs TOML gains a link type.

sphinx-needs registers its types, links and fields with rebuild "html", so a
change to the TOML they come from did not re-read any document. The pickled
needs had no entry for a new link type, and the first need using it crashed the
build: ``KeyError: "Link type 'fulfills' does not exist in backlinks."``.
"""

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
