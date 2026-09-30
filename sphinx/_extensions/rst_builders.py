# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""RST string builders — no Sphinx dependency."""

# This file emits sphinx-needs directive/link names for the `case` /
# `procedure` / `result` / `implementation` need-type roles and the `verifies`
# / `result_of` / `covers` / `satisfies` link roles via the `need_names`
# role->name mapping (zdocs step 26, zdocs-design-twister.md §12), defaulting
# to the literal names below when a role is absent from the mapping.
import logging
import re
from collections import Counter
from pathlib import Path

import yaml

__all__ = [
    "slugify",
    "build_need_rst",
    "build_procedure_need_rst",
    "build_result_rst",
    "build_symbol_need_rst",
    "build_scenario_table",
]

logger = logging.getLogger(__name__)


def slugify(s):
    """Replace non-alphanumeric runs with '-' and strip leading/trailing dashes."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-")


# Engine ROLES -> today's literal sphinx-needs NAMES. A consumer overrides
# any subset of these via `testmodule_need_types` / `testmodule_need_links`
# (merged by the caller into the single `need_names` dict threaded through
# below); a role missing from `need_names` falls back to its default here.
_DEFAULT_NEED_NAMES = {
    "case": "test_case",
    "procedure": "test_procedure",
    "result": "test_result",
    "verifies": "verifies",
    "result_of": "result_of",
    "covers": "covers",
    # symbolneeds: an API symbol, and the requirements it satisfies.
    "implementation": "impl",
    "satisfies": "satisfies",
    # testreport: result FIELDS, named by the consumer too
    # (`testreport_need_fields`). Whether the build met the case's
    # depends_on, and why a skipped result was skipped.
    "depends_met": "depends_met",
    "skip_class": "skip_class",
}

#: The result-field roles `build_result_rst` can set (see its ``fields``).
RESULT_FIELD_ROLES = ("depends_met", "skip_class")


def _need_name(need_names, role):
    """Resolve a need-type/link ROLE to its consumer-configured NAME."""
    if need_names and role in need_names:
        return need_names[role]
    return _DEFAULT_NEED_NAMES[role]


def _depends_on_rst(info, depends_field):
    """``(option lines, body lines)`` for a need's Kconfig conditions.

    The body line always renders, labelled as the consumer's alias titles the
    xrefitem ("Depends on"), because a consumer's need layout decides which
    fields show. The ``depends_on`` field is set only when ``depends_field``
    says the consumer declared it: an undeclared option is an "Unknown option"
    warning per need. The conditions are joined with ``"; "``, which no Kconfig
    expression contains.
    """
    conditions = info.get("depends_on") or []
    if not conditions:
        return [], []
    options = [f"   :depends_on: {'; '.join(conditions)}"] if depends_field else []
    label = info.get("depends_label") or "Depends on"
    body = [f"   **{label}:** " + "; ".join(f"``{c}``" for c in conditions), ""]
    return options, body


def build_need_rst(
    info, suite_name, module_path="", suite_title="", need_names=None, depends_field=False,
    id_scope=None,
):
    """Build the RST block for a single test_case need.

    ``depends_field``: set the ``depends_on`` field (see `_depends_on_rst`).
    ``id_scope``: what the fallback id ``testspec-<scope>-<function>`` is scoped
    by — the suite's Doxygen group name, which differs from ``suite_name`` under
    a `testmodule_suite_qualifier`; defaults to ``suite_name``.
    """
    name = info["name"]
    test_id = info["test_id"]
    req_ids = info["req_ids"]
    status = info["status"]
    source_file = info["source_file"]
    doxygen_url = info["doxygen_url"]
    brief = info["brief"]
    detail_lines = info.get("detail_lines", [])
    see_rst = info["see_rst"]
    body_sections = info["body_sections"]

    stem = name[5:] if name.startswith("test_") else name
    title = stem.replace("_", " ")

    if test_id:
        need_id = test_id
    else:
        scope = id_scope or suite_name
        need_id = f"testspec-{scope}-{name}"
        logger.warning(f"testmodule: {scope}/{name} has no @testid annotation")

    lines = [f".. {_need_name(need_names, 'case')}:: {title}"]
    lines.append(f"   :id: {need_id}")
    lines.append(f"   :test_function: {name}")
    if module_path:
        lines.append(f"   :test_module: {module_path}")
    lines.append(f"   :suite: {suite_name}")
    if suite_title:
        lines.append(f"   :suite_title: {suite_title}")
    lines.append(f"   :status: {status}")
    if req_ids:
        lines.append(f"   :{_need_name(need_names, 'verifies')}: {'; '.join(req_ids)}")
    depends_options, depends_body = _depends_on_rst(info, depends_field)
    lines += depends_options
    lines.append("")

    if brief:
        lines.append("   .. rst-class:: need-brief")
        lines.append("")
        lines.append(f"   {brief}")
        lines.append("")

    # Indented PER LINE, blank lines preserved as blanks — `detail_lines` is RST
    # lines (prose and lists), not one string per paragraph. Same shape as
    # `body_sections` below; indenting only the first line of a block would turn
    # a bullet list into a docutils "unexpected unindent".
    if detail_lines:
        for dline in detail_lines:
            lines.append(f"   {dline}" if dline else "")
        lines.append("")

    for section_lines in body_sections:
        for sline in section_lines:
            lines.append(f"   {sline}" if sline else "")
        lines.append("")

    lines += depends_body

    if source_file and doxygen_url:
        lines.append(f"   **Source:** `{source_file} <{doxygen_url}>`__")
        lines.append("")
    elif source_file:
        lines.append(f"   **Source:** {source_file}")
        lines.append("")

    if see_rst:
        lines.append(f"   {see_rst}")
        lines.append("")

    return "\n".join(lines)


def build_procedure_need_rst(
    memberdef,
    proc_compound_id,
    proc_group_name,
    testspec_html_dir,
    api_html_dir,
    need_names=None,
    tag_dirs=None,
):
    """Build a test_procedure needs item for one shared test procedure.

    ``tag_dirs``: where a tag-file reference links (`doxygen_parser.RefLinks.tags`).
    """
    from doxygen_parser import (
        RefLinks,
        detail_rst_lines,
        extract_params,
        para_text,
        see_to_rst,
    )

    name = memberdef.findtext("name", "").strip()
    need_id = f"test-proc-{proc_group_name}-{name}"

    # No links here: the brief is only used as the title, which is not parsed.
    brief = para_text(memberdef.find(".//briefdescription/para"))
    title = (brief[:90] + "…") if len(brief) > 90 else brief
    if not title:
        title = name

    loc = memberdef.find("location")
    source_file = ""
    if loc is not None:
        fpath = loc.get("bodyfile") or loc.get("file", "")
        line = loc.get("bodystart") or loc.get("line", "")
        if fpath:
            source_file = f"{Path(fpath).name} (line {line})"

    member_id = memberdef.get("id", "")
    prefix = proc_compound_id + "_1"
    anchor = member_id[len(prefix) :] if member_id.startswith(prefix) else member_id
    doxygen_url = f"{testspec_html_dir}/{proc_compound_id}.html#{anchor}"

    dd = memberdef.find("detaileddescription")
    detail_lines = []
    params = []
    see_rst_str = ""
    if dd is not None:
        links = RefLinks(api=api_html_dir, local=testspec_html_dir, tags=tag_dirs)
        params = extract_params(dd, links)
        # Was a second, hand-rolled copy of the same paragraph walk, carrying the
        # same list-dropping defect. One helper now, so a fix lands in both.
        detail_lines = detail_rst_lines(dd, links)
        # Every see section, not only the first: see `see_to_rst`.
        see_sects = dd.findall(".//simplesect[@kind='see']")
        if see_sects:
            see_rst_str = see_to_rst(see_sects, api_html_dir, testspec_html_dir, tag_dirs)

    lines = []
    lines.append(f".. {_need_name(need_names, 'procedure')}:: {title}")
    lines.append(f"   :id: {need_id}")
    lines.append("   :status: active")
    lines.append("")

    if detail_lines:
        for dline in detail_lines:
            lines.append(f"   {dline}" if dline else "")
        lines.append("")

    if params:
        for pname, pdesc in params:
            lines.append(f"   :``{pname}``: {pdesc}")
        lines.append("")

    if source_file and doxygen_url:
        lines.append(
            f"   **Source:** :c:func:`{name}` — `{source_file} <{doxygen_url}>`__"
        )
        lines.append("")

    if see_rst_str:
        lines.append(f"   {see_rst_str}")
        lines.append("")

    return "\n".join(lines)


def build_result_rst(r, spec_id, test_module, req_ids=None, need_names=None, fields=()):
    """Build RST block for one test_result need.

    ``fields``: the result-field roles (`RESULT_FIELD_ROLES`) to set, under
    their names from ``need_names``, where ``r`` has a value for them — the
    ones the consumer declared; an undeclared option warns per need.
    """
    need_id = f"TR-{slugify(r['platform'])}-{slugify(r['scenario'])}-{spec_id}"
    fn = r["function"]
    title = (fn[5:] if fn.startswith("test_") else fn).replace("_", " ")
    lines = [
        f".. {_need_name(need_names, 'result')}:: {title}",
        f"   :id: {need_id}",
        f"   :status: {r['status']}",
    ]
    if test_module:
        lines.append(f"   :test_module: {test_module}")
    lines += [
        f"   :platform: {r['platform']}",
        f"   :scenario: {r['scenario']}",
        f"   :twister_id: {r['twister_id']}",
        f"   :execution_time: {r['time']}",
        f"   :{_need_name(need_names, 'result_of')}: {spec_id}",
    ]
    if req_ids:
        lines.append(f"   :{_need_name(need_names, 'covers')}: {'; '.join(req_ids)}")
    if r["reason"]:
        lines.append(f"   :reason: {r['reason']}")
    for role in RESULT_FIELD_ROLES:
        if role in fields and r.get(role):
            lines.append(f"   :{_need_name(need_names, role)}: {r[role]}")
    lines.append("")
    if r.get("values"):
        lines += _values_rst(r)
    return "\n".join(lines)


def _values_summary(values):
    """``"9 values: 8 passed, 1 failed"`` for a parameterized test's values."""
    counts = Counter(v["status"] for v in values)
    order = ["passed", "failed", "error", "skipped"]
    parts = [f"{counts[k]} {k}" for k in order if counts[k]]
    parts += [f"{n} {k}" for k, n in sorted(counts.items()) if k not in order]
    return f"{len(values)} values: {', '.join(parts)}"


_RST_INLINE = re.compile(r"([\\`*_|\[\]<>])")


def _rst_text(text):
    """``text`` as literal RST prose: inline markup characters escaped."""
    return _RST_INLINE.sub(r"\\\1", " ".join(str(text).split()))


def _values_rst(r):
    """The body of a parameterized test's result: counts, then what did not pass.

    Passed values are counted, not listed; a run of hundreds of values would
    otherwise bury the one that failed.
    """
    values = r["values"]
    summary = _values_summary(values) + "."
    if r.get("twister_status"):
        summary += f" Twister reported the test as ``{r['twister_status']}``."
    lines = [f"   {summary}", ""]
    others = [v for v in values if v["status"] != "passed"]
    if others:
        lines += [
            "   .. list-table:: Values not passed",
            "      :header-rows: 1",
            "      :widths: 30 15 55",
            "",
            "      * - Value",
            "        - Status",
            "        - Reason",
        ]
        for v in others:
            lines += [
                f"      * - {_rst_text(v['value'])}",
                f"        - {v['status']}",
                f"        - {_rst_text(v['reason']) if v['reason'] else '—'}",
            ]
        lines.append("")
    return lines


def symbol_need_id(name, need_names=None):
    """The need id of API symbol ``name``: ``<TYPE>-<name>``, e.g. ``IMPL-k_queue_init``.

    Prefixed with the consumer's own name for the need type, so the id says
    what the need is in the project's vocabulary, and a symbol's need can never
    collide with a requirement or test case of the same spelling.
    """
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", _need_name(need_names, "implementation")).upper()
    return f"{prefix}-{name}"


def build_symbol_need_rst(info, need_names=None, depends_field=False):
    """Build the RST block for one API symbol's need (the ``implementation`` role).

    ``info`` is a `doxygen_parser.parse_symbol` result. The requirements it
    satisfies become the ``satisfies`` link, so each requirement's page lists
    the symbol under the link's incoming name, beside its verifying test cases.
    The kind, declaration and Doxygen page go in the body, where no field has
    to be declared for them. ``depends_field``: set the ``depends_on`` field
    (see `_depends_on_rst`).
    """
    name = info["name"]
    lines = [
        f".. {_need_name(need_names, 'implementation')}:: {name}",
        f"   :id: {symbol_need_id(name, need_names)}",
    ]
    if info["satisfies"]:
        lines.append(f"   :{_need_name(need_names, 'satisfies')}: {'; '.join(info['satisfies'])}")
    depends_options, depends_body = _depends_on_rst(info, depends_field)
    lines += depends_options
    lines.append("")

    kind = info["kind"] or "symbol"
    head = f"{kind.capitalize()} ``{name}``"
    if info["doxygen_url"]:
        head = f"`{kind.capitalize()} {name} <{info['doxygen_url']}>`__"
    lines += [f"   {head}" + (f" — {info['brief']}" if info["brief"] else ""), ""]
    lines += depends_body
    if info["source_file"]:
        lines += [f"   **Declared in:** ``{info['source_file']}``", ""]
    return "\n".join(lines)


def build_scenario_table(testcase_yaml_path):
    """Return RST lines for a list-table of scenarios from testcase.yaml."""
    try:
        with open(testcase_yaml_path) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        logger.warning(f"testmodule: could not read {testcase_yaml_path}: {e}")
        return []

    scenarios = data.get("tests", {})
    if not scenarios:
        return []

    heading = "Test Scenarios"
    lines = [
        heading,
        "-" * len(heading),
        "",
        ".. list-table:: Test Scenarios",
        "   :header-rows: 1",
        "   :widths: 30 25 45",
        "",
        "   * - Scenario",
        "     - Tags",
        "     - Extra config",
    ]
    for scenario_name, scenario_data in scenarios.items():
        tags = ", ".join(scenario_data.get("tags", []))
        extra = ", ".join(scenario_data.get("extra_configs", []))
        lines.append(f"   * - ``{scenario_name}``")
        lines.append(f"     - {tags}")
        lines.append(f"     - {extra or '—'}")
    lines.append("")
    return lines
