# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""A tag-file reference links into the document whose tag file resolved it.

Doxygen marks a symbol it resolved through a tag file with
``external="<tag file path>"``. The test documents sent every such reference
to the ``api_reference`` document. A test that mentions a kernel internal
(``cpu_mask_mod()``, documented by the Detailed Design and resolved through
its tag file) then linked to a page the API document does not have.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import doxygen_parser as dp
import test_module as tm
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import docrefs  # noqa: E402

API = "../api"
SPEC = "../testspec"
DD = "../design"
API_TAG = "/deploy/html/api/doxygen.tag"
DD_TAG = "/deploy/html/design/doxygen.tag"
TAGS = {API_TAG: API, DD_TAG: DD}


def _ref(tag, name="cpu_mask_mod()", refid="cpu__mask_8c_1a9f"):
    return f"<ref refid='{refid}' kindref='member' external='{tag}'>{name}</ref>"


def _links(tags=TAGS):
    return dp.RefLinks(api=API, local=SPEC, tags=tags)


# ---------------------------------------------------------------------------
# doxygen_parser
# ---------------------------------------------------------------------------


def test_reference_goes_to_the_document_of_its_tag_file():
    para = ET.fromstring(f"<para>Calls {_ref(DD_TAG)}.</para>")
    text = dp.para_text(para, links=_links())
    assert "`cpu_mask_mod() <../design/cpu__mask_8c.html#a9f>`__" in text
    assert "../api/" not in text


def test_api_tag_file_still_goes_to_the_api_document():
    para = ET.fromstring(f"<para>Calls {_ref(API_TAG, 'k_fifo_get()', 'group__f_1ga1')}.</para>")
    assert "<../api/group__f.html#ga1>`__" in dp.para_text(para, links=_links())


def test_tag_path_is_compared_normalised():
    para = ET.fromstring(f"<para>{_ref('/deploy/html//design/./doxygen.tag')}</para>")
    assert "<../design/cpu__mask_8c.html#a9f>`__" in dp.para_text(para, links=_links())


def test_unknown_tag_file_falls_back_to_the_api_document():
    para = ET.fromstring(f"<para>{_ref('/elsewhere/doxygen.tag')}</para>")
    assert "<../api/cpu__mask_8c.html#a9f>`__" in dp.para_text(para, links=_links())


def test_without_tags_every_tag_file_reference_goes_to_the_api_document():
    # The behaviour a caller that passes no map keeps.
    para = ET.fromstring(f"<para>{_ref(DD_TAG)}</para>")
    text = dp.para_text(para, links=dp.RefLinks(api=API, local=SPEC))
    assert "<../api/cpu__mask_8c.html#a9f>`__" in text


def test_see_also_follows_the_tag_file():
    see = ET.fromstring(
        f"<simplesect kind='see'><para>{_ref(DD_TAG)}</para>"
        f"<para>{_ref(API_TAG, 'k_fifo_get()', 'group__f_1ga1')}</para></simplesect>"
    )
    line = dp.see_to_rst(see, API, SPEC, TAGS)
    assert "<../design/cpu__mask_8c.html#a9f>`__" in line
    assert "<../api/group__f.html#ga1>`__" in line


def test_parse_memberdef_routes_brief_details_see_and_body():
    ref = _ref(DD_TAG)
    md = ET.fromstring(
        "<memberdef kind='function' id='group__s_1a1'><name>test_x</name>"
        f"<briefdescription><para>Verify {ref}.</para></briefdescription>"
        f"<detaileddescription><para>Details {ref}.</para>"
        f"<para><simplesect kind='see'><para>{ref}</para></simplesect></para>"
        "</detaileddescription>"
        "<inbodydescription><para><simplesect kind='par'><title>Act</title>"
        f"<para>Call {ref}.</para></simplesect></para></inbodydescription>"
        "<location file='t.c' line='1'/></memberdef>"
    )
    info = dp.parse_memberdef(md, "group__s", SPEC, API, TAGS)
    link = "<../design/cpu__mask_8c.html#a9f>`__"
    assert link in info["brief"]
    assert any(link in line for line in info["detail_lines"])
    assert link in info["see_rst"]
    assert any(link in line for sect in info["body_sections"] for line in sect)


# ---------------------------------------------------------------------------
# test_module: the map as seen from a page
# ---------------------------------------------------------------------------


def test_tag_dirs_prefix_relative_urls_only():
    dirs = tm._tag_dirs(
        {"/d/a.tag": "../dox-api", "/d/b.tag": "https://example.org/api", "/d/c.tag": "/abs"},
        "../../",
    )
    assert dirs == {
        "/d/a.tag": "../../../dox-api",
        "/d/b.tag": "https://example.org/api",
        "/d/c.tag": "/abs",
    }
    assert tm._tag_dirs(None, "../") == {}


# ---------------------------------------------------------------------------
# docrefs: the map from the registry
# ---------------------------------------------------------------------------

REGISTRY = {
    "groups": [{"id": "g", "title": "G"}],
    "documents": {
        "spec": {"kind": "sphinx", "group": "g", "builders": ["html"]},
        "requirements": {
            "kind": "sphinx", "group": "g", "builders": ["html"],
            "needs": {"source": "json"}, "doxygen_tag": {"types": ["req"]},
        },
        "dox-api": {"kind": "doxygen", "group": "g"},
        "dox-design": {"kind": "doxygen", "group": "g"},
        "dox-testspec": {"kind": "doxygen", "group": "g"},
        "upstream": {
            "kind": "doxygen-external", "group": "g",
            "remote-url": "https://example.org/doxygen/index.html",
            "remote-tagfile": "https://example.org/doxygen/doxygen.tag",
        },
    },
}


def test_tag_urls_names_each_tag_file_with_its_document():
    deploy = Path("/b/deploy")
    rel_urls = {"spec": ".", "requirements": "../requirements", "dox-api": "../dox-api",
                "dox-design": "../dox-design", "dox-testspec": "../dox-testspec"}
    urls = docrefs.tag_urls(REGISTRY["documents"], deploy, rel_urls)
    assert urls == {
        "/b/deploy/html/dox-api/doxygen.tag": "../dox-api",
        "/b/deploy/html/dox-design/doxygen.tag": "../dox-design",
        "/b/deploy/html/dox-testspec/doxygen.tag": "../dox-testspec",
        "/b/deploy/html/requirements/needs.tag": "../requirements",
        "/b/deploy/html/upstream/doxygen.tag": "https://example.org/doxygen",
    }


def test_tag_urls_keys_are_the_paths_tagfiles_gives_doxygen(tmp_path):
    # Doxygen writes external= exactly as TAGFILES names the file.
    registry = tmp_path / "documents.yaml"
    registry.write_text(yaml.safe_dump(REGISTRY))
    deploy = tmp_path / "deploy"
    entries = docrefs.tagfiles("dox-testspec", deploy, registry=registry).split()
    given = {entry.split("=", 1)[0] for entry in entries}
    rel_urls = {d: "x" for d in REGISTRY["documents"] if d != "upstream"}
    assert given <= set(docrefs.tag_urls(REGISTRY["documents"], deploy, rel_urls))
    assert f"{(deploy / 'html/dox-design/doxygen.tag').as_posix()}" in given
