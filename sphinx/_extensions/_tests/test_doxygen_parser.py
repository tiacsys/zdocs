# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import xml.etree.ElementTree as ET

import doxygen_parser as dp
import pytest
from conftest import FIXTURES

# ---------------------------------------------------------------------------
# elem_text
# ---------------------------------------------------------------------------

def test_elem_text_simple():
    el = ET.fromstring("<root>hello</root>")
    assert dp.elem_text(el) == "hello"


def test_elem_text_nested():
    el = ET.fromstring("<root>foo <child>bar</child> baz</root>")
    assert dp.elem_text(el) == "foo bar baz"


# ---------------------------------------------------------------------------
# para_text
# ---------------------------------------------------------------------------

def test_para_text_computeroutput_func_ref():
    para = ET.fromstring(
        "<para>Call <computeroutput>"
        "<ref kindref='member'>foo()</ref>"
        "</computeroutput> here.</para>"
    )
    result = dp.para_text(para)
    assert ":c:func:`foo`" in result


def test_para_text_computeroutput_macro():
    # A macro ending in () must NOT become :c:func: — no <ref> child means plain code
    para = ET.fromstring("<para>Use <computeroutput>K_FIFO_DEFINE()</computeroutput>.</para>")
    result = dp.para_text(para)
    assert "``K_FIFO_DEFINE()``" in result
    assert ":c:func:" not in result


def test_para_text_computeroutput_plain():
    para = ET.fromstring("<para>Use <computeroutput>CONFIG_FOO</computeroutput>.</para>")
    result = dp.para_text(para)
    assert "``CONFIG_FOO``" in result


def test_para_text_skips_parameterlist():
    para = ET.fromstring(
        "<para>Brief text."
        "<parameterlist kind='param'>"
        "<parameteritem>"
        "<parameternamelist><parametername>x</parametername></parameternamelist>"
        "<parameterdescription><para>an integer</para></parameterdescription>"
        "</parameteritem>"
        "</parameterlist>"
        "</para>"
    )
    result = dp.para_text(para)
    assert "Brief text" in result
    assert "integer" not in result


# ---------------------------------------------------------------------------
# list_to_rst_lines
# ---------------------------------------------------------------------------

# A list item with two <para> children is TWO paragraphs, and RST needs a blank
# line between them to stay two. These used to assert the continuation on the very
# next line, which renders as one wrapped paragraph — the indent was right and the
# paragraph break was silently lost. The indent assertions are unchanged; only the
# index moved.

def test_list_to_rst_lines_continuation_indent_ordered():
    ol = ET.fromstring(
        "<orderedlist>"
        "<listitem><para>first</para><para>continuation</para></listitem>"
        "</orderedlist>"
    )
    lines = dp.list_to_rst_lines(ol, "#.")
    assert lines[0] == "#. first"
    assert lines[1] == ""  # the paragraph break, emitted as a blank line
    assert lines[2] == "   continuation"  # 3 spaces: len("#.") + 1


def test_list_to_rst_lines_continuation_indent_unordered():
    il = ET.fromstring(
        "<itemizedlist>"
        "<listitem><para>first</para><para>continuation</para></listitem>"
        "</itemizedlist>"
    )
    lines = dp.list_to_rst_lines(il, "-")
    assert lines[0] == "- first"
    assert lines[1] == ""
    assert lines[2] == "  continuation"  # 2 spaces: len("-") + 1


def test_list_to_rst_lines_nested_list_is_indented_and_blank_separated():
    """A list inside a list item survives, with the blank lines RST needs."""
    il = ET.fromstring(
        "<itemizedlist><listitem><para>outer"
        "<itemizedlist><listitem><para>inner</para></listitem></itemizedlist>"
        "</para></listitem></itemizedlist>"
    )
    assert dp.list_to_rst_lines(il, "-") == ["- outer", "", "  - inner"]


# ---------------------------------------------------------------------------
# para_rst_lines
# ---------------------------------------------------------------------------

def test_para_rst_lines_list_only():
    para = ET.fromstring(
        "<para><itemizedlist>"
        "<listitem><para>Return success</para></listitem>"
        "<listitem><para>Return failure</para></listitem>"
        "</itemizedlist></para>"
    )
    assert dp.para_rst_lines(para) == ["- Return success", "- Return failure"]


def test_para_rst_lines_text_then_list_in_one_para():
    """Prose and a list in the SAME <para>: both, separated by a blank line.

    The previous list/else ladder rendered one or the other, so the prose was
    dropped whenever a paragraph also contained a list.
    """
    para = ET.fromstring(
        "<para>Test steps:<itemizedlist>"
        "<listitem><para>Return success</para></listitem>"
        "</itemizedlist></para>"
    )
    assert dp.para_rst_lines(para) == ["Test steps:", "", "- Return success"]


def test_para_rst_lines_ordered_list_marker():
    para = ET.fromstring(
        "<para><orderedlist><listitem><para>step one</para></listitem></orderedlist></para>"
    )
    assert dp.para_rst_lines(para) == ["#. step one"]


def test_para_rst_lines_structural_children_stay_excluded():
    """params, see-also and xrefsects are rendered by other code, not here."""
    para = ET.fromstring(
        "<para>Prose."
        "<parameterlist kind='param'><parameteritem>"
        "<parameternamelist><parametername>n</parametername></parameternamelist>"
        "<parameterdescription><para>a count</para></parameterdescription>"
        "</parameteritem></parameterlist>"
        "<simplesect kind='see'><para>other()</para></simplesect>"
        "<xrefsect id='testids_1a'><xreftitle>Test ID</xreftitle>"
        "<xrefdescription><para>TC_X</para></xrefdescription></xrefsect>"
        "</para>"
    )
    assert dp.para_rst_lines(para) == ["Prose."]


# ---------------------------------------------------------------------------
# see_to_rst
# ---------------------------------------------------------------------------

def test_see_to_rst_ref_resolved():
    see = ET.fromstring(
        "<simplesect kind='see'><para>"
        "<ref refid='group__queue__api_1abc' external='path/to/tagfile.xml' kindref='member'>"
        "k_queue_init"
        "</ref>"
        "</para></simplesect>"
    )
    result = dp.see_to_rst(see, "/api/html")
    assert "k_queue_init" in result
    assert "/api/html/group__queue__api.html#abc" in result


def test_see_to_rst_ref_unresolved():
    see = ET.fromstring(
        "<simplesect kind='see'><para>"
        "<ref refid='group__queue__api_1abc' kindref='member'>k_queue_init</ref>"
        "</para></simplesect>"
    )
    result = dp.see_to_rst(see, "/api/html")
    assert ":c:func:`k_queue_init`" in result


# ---------------------------------------------------------------------------
# parse_memberdef
# ---------------------------------------------------------------------------

def _make_memberdef(extra_xrefsects="", inbody="", member_extra=""):
    return ET.fromstring(
        f"<memberdef kind='function' id='group__queue__api_1a001'>"
        f"<name>test_queue_put</name>"
        f"<briefdescription><para>Test queue put.</para></briefdescription>"
        f"<detaileddescription><para>{extra_xrefsects}</para></detaileddescription>"
        f"<inbodydescription>{inbody}</inbodydescription>"
        f"{member_extra}"
        f"<location file='test_queue.c' line='42' bodyfile='test_queue.c' bodystart='42'/>"
        f"</memberdef>"
    )


def _verifies(*uids):
    """Doxygen 1.16's native `\\verifies` output: a <verifies> child of the
    memberdef, one <requirement> per UID, the UID only in its refid."""
    reqs = "".join(f"<requirement refid='requirement_{uid}'/>" for uid in uids)
    return f"<verifies>{reqs}</verifies>"


def test_parse_memberdef_extracts_testid():
    xref = (
        "<xrefsect id='testids_1testids'>"
        "<xreftitle>Test ID</xreftitle>"
        "<xrefdescription><para>TSPEC-QUEUE-API-001</para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(extra_xrefsects=xref)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["test_id"] == "TSPEC-QUEUE-API-001"


def test_parse_memberdef_extracts_reqrefs():
    xref = (
        "<xrefsect id='reqrefs_1reqrefs'>"
        "<xreftitle>Requirement Refs</xreftitle>"
        "<xrefdescription><para>zep-srs-20-1</para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(extra_xrefsects=xref)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert "zep-srs-20-1" in info["req_ids"]


def test_parse_memberdef_reads_autolinked_xrefitem_values():
    # With a needs tag in TAGFILES, Doxygen autolinks an identifier-shaped UID
    # inside the xrefitem; the value must survive the <ref> wrapper.
    xref = (
        "<xrefsect id='testids_1testids'>"
        "<xreftitle>Test ID</xreftitle>"
        "<xrefdescription><para><ref refid='x' kindref='member'>TC_ONE</ref> "
        "</para></xrefdescription>"
        "</xrefsect>"
        "<xrefsect id='reqrefs_1reqrefs'>"
        "<xreftitle>Requirement Refs</xreftitle>"
        "<xrefdescription><para><ref refid='requirements_1DUTY_001' "
        "kindref='member'>DUTY_001</ref> </para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(extra_xrefsects=xref)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["test_id"] == "TC_ONE"
    assert info["req_ids"] == ["DUTY_001"]


def test_parse_memberdef_extracts_native_verifies():
    md = _make_memberdef(member_extra=_verifies("ZEP-SRS-20-6", "ZEP-SRS-20-7"))
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["req_ids"] == ["ZEP-SRS-20-6", "ZEP-SRS-20-7"]


def test_parse_memberdef_native_verifies_and_reqrefs_coexist():
    # Both paths are live during the migration (D2); a UID named by both is
    # listed once.
    xref = (
        "<xrefsect id='reqrefs_1reqrefs'>"
        "<xreftitle>Requirement Refs</xreftitle>"
        "<xrefdescription><para>ZEP-SRS-20-1</para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(
        extra_xrefsects=xref, member_extra=_verifies("ZEP-SRS-20-1", "ZEP-SRS-20-2")
    )
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["req_ids"] == ["ZEP-SRS-20-1", "ZEP-SRS-20-2"]


def test_parse_memberdef_ignores_verifies_of_other_kinds():
    # Only <requirement> children carry a UID; anything else Doxygen may put
    # there is not a requirement link.
    md = _make_memberdef(member_extra="<verifies><ref refid='x'>x</ref></verifies>")
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["req_ids"] == []


def test_parse_memberdef_active_status():
    xref = (
        "<xrefsect id='test_active_1test_active'>"
        "<xreftitle>Active</xreftitle>"
        "<xrefdescription><para></para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(extra_xrefsects=xref)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["status"] == "active"


def test_parse_memberdef_no_testid():
    md = _make_memberdef()
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["test_id"] == ""


def test_parse_memberdef_extracts_detail_lines():
    xml = ET.fromstring(
        "<memberdef kind='function' id='group__queue__api_1a001'>"
        "<name>test_queue_put</name>"
        "<briefdescription><para>Brief line.</para></briefdescription>"
        "<detaileddescription>"
        "<para>First detail paragraph.</para>"
        "<para>Second detail paragraph.</para>"
        "<para><xrefsect id='testids_1testids'><xreftitle>Test ID</xreftitle>"
        "<xrefdescription><para>TSPEC-QUEUE-API-001</para></xrefdescription>"
        "</xrefsect></para>"
        "</detaileddescription>"
        "<inbodydescription/>"
        "<location file='f.c' line='1' bodyfile='f.c' bodystart='1'/>"
        "</memberdef>"
    )
    info = dp.parse_memberdef(xml, "group__queue__api", "/testspec/html", "/api/html")
    # Lines, with the paragraph break between them; the xrefsect paragraph
    # contributes nothing, because the test id is read from it separately.
    assert info["detail_lines"] == [
        "First detail paragraph.",
        "",
        "Second detail paragraph.",
    ]
    assert info["test_id"] == "TSPEC-QUEUE-API-001"


def test_parse_memberdef_finds_xrefsects_nested_in_a_trailing_list():
    """`@testid`/`@reqref`/`@draft` survive a `@details` that ends with a list.

    Doxygen puts the trailing xrefsects in a top-level <para> only when the prose
    ends with prose. End it with a bullet list — the label-then-list shape real
    annotated ztest source uses — and it nests them inside the LAST LIST ITEM
    instead: `detaileddescription/para/itemizedlist/listitem/para/xrefsect`. The
    old `para/xrefsect` search found nothing there, so the need silently lost its
    id (falling back to `testspec-<suite>-<fn>`), its requirement links, its
    status and its see-also — four fields, decided by where a blank line went.

    This XML is not constructed: it is the shape doxygen 1.16.1 emitted for the
    ACME fixture once its `@details` gained a list.
    """
    xml = ET.fromstring(
        "<memberdef kind='function' id='group__q_1a1'>"
        "<name>test_widget</name>"
        "<detaileddescription>"
        "<para>Expected result:</para>"
        "<para><itemizedlist><listitem>"
        "<para>a value consistent with the maximum</para>"
        "<para>"
        "<xrefsect id='reqrefs_1_r1'><xreftitle>Requirement</xreftitle>"
        "<xrefdescription><para>DUTY_001</para></xrefdescription></xrefsect>"
        "<simplesect kind='see'><para>"
        "<ref refid='group__w_1gabc' kindref='member'>acme_widget_init</ref>"
        "</para></simplesect>"
        "<xrefsect id='testids_1_t1'><xreftitle>Test ID</xreftitle>"
        "<xrefdescription><para>ACME-WIDGET-PROBE-001</para></xrefdescription></xrefsect>"
        "<xrefsect id='test_active_1_a1'><xreftitle>Status</xreftitle>"
        "<xrefdescription/></xrefsect>"
        "</para>"
        "</listitem></itemizedlist></para>"
        "</detaileddescription>"
        "<inbodydescription/>"
        "<location file='f.c' line='1' bodyfile='f.c' bodystart='1'/>"
        "</memberdef>"
    )
    info = dp.parse_memberdef(xml, "group__q", "/testspec/html", "/api/html")
    assert info["test_id"] == "ACME-WIDGET-PROBE-001"
    assert info["req_ids"] == ["DUTY_001"]
    assert info["status"] == "active"
    assert "acme_widget_init" in info["see_rst"]
    # ...and the xrefsect/see content must NOT leak into the prose as well.
    assert info["detail_lines"] == [
        "Expected result:",
        "",
        "- a value consistent with the maximum",
    ]


def test_parse_memberdef_keeps_authored_lists_in_details():
    """The reported defect: `Test steps:` published with nothing under it.

    Doxygen emits the label and its bullets as two SIBLING <para> elements, so a
    text-only read of each paragraph kept every label and dropped every list. The
    content was in the XML the whole time — doxygen's own HTML rendered it — and
    only the engine's Sphinx path lost it.
    """
    xml = ET.fromstring(
        "<memberdef kind='function' id='group__q_1a1'>"
        "<name>test_passing</name>"
        "<detaileddescription>"
        "<para>Test steps:</para>"
        "<para><itemizedlist><listitem><para>Return success</para></listitem>"
        "</itemizedlist></para>"
        "<para>Expected result:</para>"
        "<para><itemizedlist><listitem><para>Success</para></listitem>"
        "</itemizedlist></para>"
        "</detaileddescription>"
        "<inbodydescription/>"
        "<location file='f.c' line='1' bodyfile='f.c' bodystart='1'/>"
        "</memberdef>"
    )
    info = dp.parse_memberdef(xml, "group__q", "/testspec/html", "/api/html")
    assert info["detail_lines"] == [
        "Test steps:",
        "",
        "- Return success",
        "",
        "Expected result:",
        "",
        "- Success",
    ]


def test_parse_memberdef_arrange_sections():
    inbody = (
        "<para>"
        "<simplesect kind='par'>"
        "<title>Arrange</title>"
        "<para>Set up the queue.</para>"
        "</simplesect>"
        "</para>"
    )
    md = _make_memberdef(inbody=inbody)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert len(info["body_sections"]) == 1
    assert any("Arrange" in line for line in info["body_sections"][0])


# ---------------------------------------------------------------------------
# load_group_index
# ---------------------------------------------------------------------------

def test_load_group_index_maps_names():
    idx = dp.load_group_index(FIXTURES / "doxygen")
    assert idx.get("queue_api") == "group__queue__api"
    assert idx.get("queue_procedures") == "group__queue__procedures"


def test_load_group_index_missing_file_raises():
    with pytest.raises(RuntimeError):
        dp.load_group_index(FIXTURES / "doxygen" / "nonexistent")


# ---------------------------------------------------------------------------
# extract_params
# ---------------------------------------------------------------------------

def test_extract_params_basic():
    dd = ET.fromstring(
        "<detaileddescription><para>"
        "<parameterlist kind='param'>"
        "<parameteritem>"
        "<parameternamelist><parametername>queue</parametername></parameternamelist>"
        "<parameterdescription><para>the queue pointer</para></parameterdescription>"
        "</parameteritem>"
        "</parameterlist>"
        "</para></detaileddescription>"
    )
    params = dp.extract_params(dd)
    assert len(params) == 1
    assert params[0][0] == "queue"
    assert "queue pointer" in params[0][1]


# ---------------------------------------------------------------------------
# symbol links in prose (brief, details, test steps, Arrange/Act/Assert)
#
# The see-also line linked a symbol into the Doxygen HTML; the same symbol in
# the prose became a :c:func: role, which nothing in the test documents can
# resolve, so it rendered as code with no link and no warning.
# ---------------------------------------------------------------------------

API = "../api"
SPEC = "../testspec"
EXT_REF = (
    "<ref refid='group__fifo__apis_1ga1e2c' kindref='member' "
    "external='/deploy/html/api/doxygen.tag'>k_fifo_get()</ref>"
)
LOCAL_REF = "<ref refid='group__procs_1ga3f93' kindref='member'>get_scratch_packet()</ref>"


def test_para_text_links_external_symbol_into_api_doxygen():
    para = ET.fromstring(f"<para>Call {EXT_REF} now.</para>")
    text = dp.para_text(para, links=dp.RefLinks(api=API, local=SPEC))
    assert "`k_fifo_get() <../api/group__fifo__apis.html#ga1e2c>`__" in text
    assert ":c:func:" not in text


def test_para_text_links_local_symbol_into_testspec_doxygen():
    para = ET.fromstring(f"<para>Call {LOCAL_REF}.</para>")
    text = dp.para_text(para, links=dp.RefLinks(api=API, local=SPEC))
    assert "`get_scratch_packet() <../testspec/group__procs.html#ga3f93>`__" in text


def test_para_text_without_links_is_unchanged():
    para = ET.fromstring(f"<para>Call {EXT_REF}.</para>")
    assert dp.para_text(para) == "Call :c:func:`k_fifo_get`."


def test_parse_memberdef_links_symbols_in_brief_details_and_body():
    md = ET.fromstring(
        "<memberdef kind='function' id='group__s_1a1'><name>test_x</name>"
        f"<briefdescription><para>Verify {EXT_REF}.</para></briefdescription>"
        f"<detaileddescription><para>Details {EXT_REF}.</para></detaileddescription>"
        "<inbodydescription><para><simplesect kind='par'><title>Act</title>"
        f"<para><orderedlist><listitem><para>Call {EXT_REF}.</para></listitem></orderedlist></para>"
        "</simplesect></para></inbodydescription>"
        "<location file='t.c' line='1'/></memberdef>"
    )
    info = dp.parse_memberdef(md, "group__s", SPEC, API)
    link = "<../api/group__fifo__apis.html#ga1e2c>`__"
    assert link in info["brief"]
    assert any(link in line for line in info["detail_lines"])
    assert any(link in line for sect in info["body_sections"] for line in sect)


def test_see_to_rst_links_local_symbol_when_testspec_dir_given():
    see = ET.fromstring(f"<simplesect kind='see'><para>{LOCAL_REF}</para></simplesect>")
    assert "../testspec/group__procs.html#ga3f93" in dp.see_to_rst(see, API, SPEC)


# ---------------------------------------------------------------------------
# see_to_rst: text that is not in a <ref>
#
# `@see irq_offload()` gives no <ref> when no Doxygen project documents the
# symbol. see_to_rst read only the <ref> elements, so the see section gave no
# line, and the reference was lost.
# ---------------------------------------------------------------------------

def _see(body):
    return ET.fromstring(f"<simplesect kind='see'><para>{body}</para></simplesect>")


def test_see_to_rst_renders_text_without_ref_as_literal():
    assert dp.see_to_rst(_see("irq_offload()"), API, SPEC) == "**See also:** ``irq_offload()``"


def test_see_to_rst_keeps_refs_and_the_text_between_them_in_order():
    line = dp.see_to_rst(_see(f"atomic_set(), {EXT_REF}, printk() "), API, SPEC)
    assert line == (
        "**See also:** ``atomic_set()``, "
        "`k_fifo_get() <../api/group__fifo__apis.html#ga1e2c>`__, ``printk()``"
    )


def test_see_to_rst_separators_between_refs_give_no_item():
    """A line with only linked refs is the same as before."""
    line = dp.see_to_rst(_see(f"{EXT_REF}, {LOCAL_REF}."), API, SPEC)
    assert line == (
        "**See also:** `k_fifo_get() <../api/group__fifo__apis.html#ga1e2c>`__, "
        "`get_scratch_packet() <../testspec/group__procs.html#ga3f93>`__"
    )


def test_see_to_rst_a_comma_in_parentheses_does_not_divide_items():
    assert dp.see_to_rst(_see("k_foo(a, b), k_bar()"), API) == (
        "**See also:** ``k_foo(a, b)``, ``k_bar()``"
    )


def test_see_to_rst_links_a_ref_inside_computeroutput():
    line = dp.see_to_rst(_see(f"<computeroutput>{EXT_REF}</computeroutput>"), API, SPEC)
    assert line == "**See also:** `k_fifo_get() <../api/group__fifo__apis.html#ga1e2c>`__"


def test_see_to_rst_empty_section_gives_no_line():
    assert dp.see_to_rst(_see(" , "), API, SPEC) == ""


def test_see_to_rst_space_after_a_call_divides_items():
    assert dp.see_to_rst(_see("k_stats_query() k_stats_reset()"), API) == (
        "**See also:** ``k_stats_query()``, ``k_stats_reset()``"
    )
