# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""symbolneeds — one need per API symbol carrying a Doxygen ``\\satisfies``.

The fixture is real Doxygen 1.16.1 XML (fixtures/doxygen-symbols/Doxyfile):
three grouped symbols and one ungrouped function with ``\\satisfies``, one
grouped function without, and a macro satisfying ``REQ-QUEUE-99``, which no
``\\requirement`` defines. Doxygen warned about that one, and still wrote a
``requirement_REQ-QUEUE-99`` refid, indistinguishable from a real one.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import doxygen_parser as dp
import pytest
import rst_builders as rb
import symbol_needs as sn
from conftest import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import docrefs  # noqa: E402

_ROOTS = Path(__file__).parent / "roots"
XML = FIXTURES / "doxygen-symbols"


def _member(name, compound="group__queue__apis"):
    root = ET.parse(XML / f"{compound}.xml").getroot()
    return next(md for md in root.iter("memberdef") if md.findtext("name") == name)


def _ids(lines):
    return [line.split(":id:")[1].strip() for line in lines if line.strip().startswith(":id:")]


# ---------------------------------------------------------------------------
# doxygen_parser
# ---------------------------------------------------------------------------


def test_satisfies_uids_in_source_order():
    assert dp.requirement_uids(_member("k_queue_append"), "satisfies") == [
        "REQ-QUEUE-1",
        "REQ-QUEUE-2",
    ]


def test_satisfies_is_not_read_as_verifies():
    assert dp.parse_memberdef(_member("k_queue_append"), "group__queue__apis", "", "")[
        "req_ids"
    ] == []


def test_parse_symbol():
    info = dp.parse_symbol(_member("k_queue_init"), "../api")
    assert info["name"] == "k_queue_init"
    assert info["kind"] == "function"
    assert info["satisfies"] == ["REQ-QUEUE-1"]
    assert info["brief"] == "Initialize a queue."
    assert info["source_file"] == "queue.h (line 19)"
    assert info["doxygen_url"] == (
        "../api/group__queue__apis.html#ga7119309c1016c8ac5ea22768916c4b8a"
    )


def test_an_ungrouped_symbol_links_to_its_file_page():
    info = dp.parse_symbol(_member("k_queue_is_empty", "queue_8h"), "api")
    assert info["doxygen_url"].startswith("api/queue_8h.html#")


# ---------------------------------------------------------------------------
# rst_builders
# ---------------------------------------------------------------------------


def test_symbol_need_uses_the_role_names():
    info = dp.parse_symbol(_member("k_queue_append"), "api")
    default = rb.build_symbol_need_rst(info)
    assert default.startswith(".. impl:: k_queue_append\n   :id: IMPL-k_queue_append\n")
    assert "   :satisfies: REQ-QUEUE-1; REQ-QUEUE-2" in default

    renamed = rb.build_symbol_need_rst(
        info, {"implementation": "code_unit", "satisfies": "realises"}
    )
    assert renamed.startswith(".. code_unit:: k_queue_append\n   :id: CODE_UNIT-k_queue_append\n")
    assert "   :realises: REQ-QUEUE-1; REQ-QUEUE-2" in renamed


def test_symbol_need_body_has_kind_link_and_file():
    rst = rb.build_symbol_need_rst(dp.parse_symbol(_member("K_QUEUE_MAX"), "api"))
    assert "`Define K_QUEUE_MAX <api/group__queue__apis.html#" in rst
    assert "**Declared in:** ``queue.h (line 39)``" in rst


# ---------------------------------------------------------------------------
# symbol_needs_rst
# ---------------------------------------------------------------------------


def test_every_annotated_symbol_once_sectioned_by_compound():
    lines = sn.symbol_needs_rst(XML, "api")
    assert _ids(lines) == [
        "IMPL-k_queue_is_empty",  # index.xml lists the file first
        "IMPL-k_queue_init",
        "IMPL-k_queue_append",
        "IMPL-K_QUEUE_MAX",
    ]
    assert "Queue APIs" in lines and "queue.h" in lines
    assert not any("k_queue_cancel_wait" in line for line in lines)


def test_one_group():
    lines = sn.symbol_needs_rst(XML, "api", group="queue_apis")
    assert _ids(lines) == ["IMPL-k_queue_init", "IMPL-k_queue_append", "IMPL-K_QUEUE_MAX"]
    assert "Queue APIs" not in lines  # the author places a group; no heading


def test_an_unknown_group_yields_nothing():
    assert sn.symbol_needs_rst(XML, "api", group="no_such_group") == []


def test_every_read_file_is_reported_as_input():
    seen = []
    sn.symbol_needs_rst(XML, "api", note_input=seen.append)
    assert {Path(p).name for p in seen} == {
        "queue_8h.xml",
        "req_8dox.xml",
        "group__queue__apis.xml",
    }


# ---------------------------------------------------------------------------
# Directive: the link, its backlink, and a dangling target
# ---------------------------------------------------------------------------


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-symbolneeds"))
def test_symbols_satisfy_requirements_across_pages(app, warning):
    app.build()
    needs = json.loads((Path(app.outdir) / "needs.json").read_text())
    needs = needs["versions"][needs["current_version"]]["needs"]
    assert needs["IMPL-k_queue_append"]["type"] == "impl"
    assert needs["IMPL-k_queue_append"]["satisfies"] == ["REQ-QUEUE-1", "REQ-QUEUE-2"]
    assert sorted(needs["REQ-QUEUE-1"]["satisfies_back"]) == [
        "IMPL-k_queue_append",
        "IMPL-k_queue_init",
    ]
    assert "satisfied by" in (Path(app.outdir) / "requirements.html").read_text()


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-symbolneeds"))
def test_a_satisfies_target_that_is_no_requirement_warns(app, warning):
    # The refid Doxygen wrote for REQ-QUEUE-99 looks like any other; the
    # missing need is what gives it away, and it must not pass silently.
    app.build()
    text = warning.getvalue()
    assert "IMPL-K_QUEUE_MAX" in text and "REQ-QUEUE-99" in text
    assert "unknown outgoing link" in text


# ---------------------------------------------------------------------------
# Registry: symbol_needs:
# ---------------------------------------------------------------------------

REGISTRY = """\
groups:
  - id: reference
    title: Reference
documents:
  api-doc:
    kind: sphinx
    group: reference
    builders: [html]
    needs:
      source: json
    symbol_needs:
      doxygen_source: dox-api
  dox-api:
    kind: doxygen
    group: reference
"""


def _registry(tmp_path, text=REGISTRY):
    path = tmp_path / "documents.yaml"
    path.write_text(text)
    return path


def test_load_resolves_the_block(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "deploy" / "html" / "api-doc"))
    refs = docrefs.load("api-doc", _registry(tmp_path))
    assert refs.symbol_needs == {
        "xml_dir": str((tmp_path / "deploy" / "xml" / "dox-api").resolve()),
        "doxygen_url": "../dox-api",
    }
    assert docrefs.load("dox-api", _registry(tmp_path)).symbol_needs is None


def test_manifest_names_the_doxygen_source(tmp_path):
    manifest = docrefs.manifest(_registry(tmp_path))
    entries = {e["id"]: e["symbol_needs_doxygen_source"] for e in manifest}
    assert entries == {"api-doc": "dox-api", "dox-api": None}


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ("      doxygen_source: dox-api\n", "      doxygen_src: dox-api\n", "unknown key"),
        (
            "    symbol_needs:\n      doxygen_source: dox-api\n",
            "    symbol_needs: true\n",
            "mapping",
        ),
        ("doxygen_source: dox-api", "doxygen_source: nowhere", "does not exist"),
        ("doxygen_source: dox-api", "doxygen_source: api-doc", "not 'doxygen'"),
    ],
)
def test_invalid_blocks_fail_validation(tmp_path, before, after, message):
    assert before in REGISTRY
    with pytest.raises(ValueError, match=message):
        docrefs.manifest(_registry(tmp_path, REGISTRY.replace(before, after)))


def test_the_block_needs_a_doxygen_source(tmp_path):
    text = REGISTRY.replace("      doxygen_source: dox-api\n", "      {}\n").replace(
        "    symbol_needs:\n      {}\n", "    symbol_needs: {}\n"
    )
    with pytest.raises(ValueError, match="without 'doxygen_source:'"):
        docrefs.manifest(_registry(tmp_path, text))


def test_only_a_sphinx_document_emits_symbol_needs(tmp_path):
    text = REGISTRY.replace(
        "  dox-api:\n    kind: doxygen\n",
        "  dox-api:\n    kind: doxygen\n    symbol_needs:\n      doxygen_source: dox-api\n",
    )
    with pytest.raises(ValueError, match="only a 'kind: sphinx' document"):
        docrefs.manifest(_registry(tmp_path, text))
