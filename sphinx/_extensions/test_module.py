# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: testmodule and testreport directives (Route B — sphinx-needs)."""
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import ViewList
from doxygen_parser import detail_rst_lines, load_group_index, parse_memberdef
from rst_builders import (
    _need_name,
    build_need_rst,
    build_procedure_need_rst,
    build_result_rst,
    build_scenario_table,
)
from sphinx.util import logging
from twister_reader import (
    find_handler_log,
    load_spec_lookup,
    load_twister_meta,
    parse_twister_results,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _maybe_dump_rst(app, docname: str, directive: str, arg: str, rst_text: str) -> None:
    dump_dir = getattr(app.config, "dump_generated_rst", "")
    if not dump_dir:
        return
    out = Path(dump_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc_slug = docname.replace("/", "__")
    arg_slug = arg.replace("/", "_").replace(".", "_")
    out_file = out / f"{doc_slug}__{directive}__{arg_slug}.rst"
    out_file.write_text(rst_text, encoding="utf-8")
    logger.debug(f"{directive}: dumped generated RST → {out_file}")


def _render_rst(rst_lines, state, content_offset, match_titles=False):
    """Parse a list of RST lines into docutils nodes via nested_parse."""
    vl = ViewList(rst_lines, source="<generated>")
    container = nodes.container()
    state.nested_parse(vl, content_offset, container, match_titles=match_titles)
    return container.children


def _display_name(path_str: str, fallback: str = "not configured") -> str:
    """The bare filename of `path_str`, for a RENDERED (published) node.

    A soft-fail node's own `logger.warning(...)` keeps the full absolute path
    unchanged — that is a build-log detail, meant for whoever is debugging the
    build on this machine. The PARAGRAPH NODE this helper feeds is a published
    artifact, though, and a report that has legitimately not been produced yet
    (design note §7 — docs and test execution are separate pipeline stages) is
    a normal state, not a build-host detail to leak: nothing about where this
    repo happens to be checked out or built belongs on a page a reader may
    view long after the build tree is gone. This is the same D9 shape
    `test_04_paths.py::test_no_host_paths_in_the_published_documents` exists
    to catch generally; it just took until step 28b's report directives for a
    soft-fail message to be the one carrying it.

    `path_str` may be empty (an unconfigured config value, not merely a path
    that does not exist) — `fallback` covers that case rather than rendering
    an empty pair of quotes.
    """
    return Path(path_str).name if path_str else fallback


def _need_names_from_config(app):
    """Merge testmodule_need_types/testmodule_need_links into the single
    role->name dict the rst_builders emitters expect as `need_names`.

    Uses getattr rather than direct attribute access: a handful of the
    soft-fail unit tests drive the directives against lightweight
    SimpleNamespace stand-ins for `app.config` that only set the keys their
    own scenario needs, and this helper is now called earlier in
    TestReportDirective.run() (before load_spec_lookup) than it used to be —
    a real Sphinx `app.config` always has both values via `add_config_value`,
    so this only changes behaviour for those stand-ins, not for a real build.
    """
    return {**getattr(app.config, "testmodule_need_types", {}),
            **getattr(app.config, "testmodule_need_links", {})}


# ---------------------------------------------------------------------------
# testmodule helpers
# ---------------------------------------------------------------------------

def _check_no_ztest_members(proc_cdef: ET.Element) -> None:
    """Warn if a procedure group contains ZTEST-annotated functions."""
    proc_name = proc_cdef.findtext("compoundname", "")
    for md in proc_cdef.findall("sectiondef/memberdef[@kind='function']"):
        fn_name = md.findtext("name", "")
        dd = md.find("detaileddescription")
        if dd is not None:
            for x in dd.findall("para/xrefsect"):
                if "testids" in x.get("id", ""):
                    logger.warning(
                        f"testmodule: procedure group '{proc_name}' contains "
                        f"ZTEST-annotated function '{fn_name}' — check @ingroup annotations"
                    )


def _classify_inner_groups(module_cdef: ET.Element, xml_dir: Path):
    """Split inner groups into (suite_refids, proc_refids) by compoundname suffix."""
    suite_refids, proc_refids = [], []
    for ig in module_cdef.findall("innergroup"):
        refid = ig.get("refid")
        ig_xml = xml_dir / f"{refid}.xml"
        if not ig_xml.exists():
            logger.warning(f"testmodule: inner group XML not found: {ig_xml}")
            continue
        ig_cdef = ET.parse(ig_xml).getroot().find("compounddef")
        if ig_cdef.findtext("compoundname", "").endswith("_procedures"):
            proc_refids.append(refid)
        else:
            suite_refids.append(refid)
    return suite_refids, proc_refids


def _build_suite_rst(
    suite_refid, xml_dir, testspec_html_dir, api_html_dir, module_path, need_names=None
):
    """Build RST lines for one test suite group (section heading + test_case needs)."""
    suite_xml = xml_dir / f"{suite_refid}.xml"
    if not suite_xml.exists():
        logger.warning(f"testmodule: suite XML not found: {suite_xml}")
        return []
    suite_cdef = ET.parse(suite_xml).getroot().find("compounddef")
    suite_name = suite_cdef.findtext("compoundname", suite_refid)
    compound_id = suite_cdef.get("id", suite_refid)
    suite_title = suite_cdef.findtext("title", suite_name)

    lines = [suite_title, "-" * len(suite_title), ""]
    group_prose = detail_rst_lines(suite_cdef.find("detaileddescription"))
    if group_prose:
        lines.extend(group_prose)
        lines.append("")
    for memberdef in suite_cdef.findall(".//memberdef[@kind='function']"):
        info = parse_memberdef(memberdef, compound_id, testspec_html_dir, api_html_dir)
        if not info["name"]:
            continue
        lines.extend(
            build_need_rst(
                info, suite_name, module_path, suite_title, need_names=need_names
            ).splitlines()
        )
        lines.append("")
    return lines


def _build_proc_group_rst(proc_refid, xml_dir, testspec_html_dir, api_html_dir, need_names=None):
    """Build RST lines for one procedure group (section heading + test_procedure needs)."""
    proc_xml = xml_dir / f"{proc_refid}.xml"
    proc_cdef = ET.parse(proc_xml).getroot().find("compounddef")
    proc_compound_id = proc_cdef.get("id", proc_refid)
    proc_group_name = proc_cdef.findtext("compoundname", proc_refid)
    proc_heading = proc_cdef.findtext("title", "Shared Test Procedures")

    _check_no_ztest_members(proc_cdef)

    lines = [proc_heading, "-" * len(proc_heading), ""]
    group_prose = detail_rst_lines(proc_cdef.find("detaileddescription"))
    if group_prose:
        lines.extend(group_prose)
        lines.append("")
    for md in proc_cdef.findall(".//memberdef[@kind='function']"):
        lines.extend(
            build_procedure_need_rst(
                md, proc_compound_id, proc_group_name, testspec_html_dir, api_html_dir,
                need_names=need_names,
            ).splitlines()
        )
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# testreport helpers
# ---------------------------------------------------------------------------

def _group_results(results):
    """Group twister results by (suite, function); return (suite_order, func_order, grouped)."""
    suite_order, func_order, grouped, seen = [], {}, {}, set()
    for r in results:
        s, fn = r["suite"], r["function"]
        if s not in func_order:
            suite_order.append(s)
            func_order[s] = []
        if (s, fn) not in seen:
            func_order[s].append(fn)
            seen.add((s, fn))
        grouped.setdefault((s, fn), []).append(r)
    for key in grouped:
        grouped[key].sort(key=lambda r: (r["platform"], r["scenario"]))
    return suite_order, func_order, grouped


def _build_results_rst(suite_order, func_order, grouped, spec_lookup, need_names=None):
    """Build RST lines for all test_result needs, grouped into one section per suite."""
    lines = []
    for suite in suite_order:
        suite_title = next(
            (
                (spec_lookup.get(fn) or spec_lookup.get("test_" + fn) or {}).get("suite_title")
                for fn in func_order[suite]
                if (spec_lookup.get(fn) or spec_lookup.get("test_" + fn) or {}).get("suite_title")
            ),
            None,
        )
        heading = suite_title or suite.replace("_", " ").title()
        lines += [heading, "-" * len(heading), ""]
        for fn in func_order[suite]:
            info = spec_lookup.get(fn) or spec_lookup.get("test_" + fn)
            if info is None:
                logger.warning(f"testreport: '{fn}' not in spec needs.json — skipped")
                continue
            for r in grouped[(suite, fn)]:
                lines += build_result_rst(
                    r, info["id"], info["test_module"], info.get("req_ids"), need_names=need_names
                ).splitlines()
                lines.append("")
    return lines


def _build_summary_table_rst(grouped, spec_lookup, need_names=None):
    """Build RST lines for the result summary needtable."""
    modules = sorted({
        (spec_lookup.get(fn) or spec_lookup.get("test_" + fn) or {}).get("test_module", "")
        for _, fn in grouped
    } - {""})
    result_type = _need_name(need_names, "result")
    tbl_filter = (
        f'type == "{result_type}" and test_module == "{modules[0]}"'
        if len(modules) == 1
        else f'type == "{result_type}"'
    )
    heading = "Result summary"
    return [
        "----", "",
        heading, "-" * len(heading), "",
        ".. needtable::",
        f"   :filter: {tbl_filter}",
        f"   :columns: id, title, test_module, platform, scenario, status, "
        f"execution_time, {_need_name(need_names, 'result_of')}",
        "   :style: table",
        "",
    ]


def _build_exec_logs_rst(twister_out_dir, module_filter):
    """Build RST lines for the execution logs section; returns [] when unavailable."""
    twister_json = Path(twister_out_dir) / "twister.json" if twister_out_dir else None
    if not twister_json or not twister_json.exists():
        return []
    try:
        tw = load_twister_meta(twister_json)
    except Exception as exc:
        logger.warning(f"testreport: could not load execution logs: {exc}")
        return []

    log_entries = []
    for ts in tw.get("testsuites", []):
        sname = ts["name"]
        if module_filter and not (
            sname == module_filter or sname.startswith(module_filter + ".")
        ):
            continue
        log_entries.append((sname, ts["platform"], ts.get("path", ""), ts.get("toolchain", "")))
    log_entries.sort()
    if not log_entries:
        return []

    lines = ["----", "", "Execution Logs", "-" * len("Execution Logs"), ""]
    for scenario, platform, test_path, toolchain in log_entries:
        sub = f"{scenario} — {platform}"
        lines += [sub, "~" * len(sub), ""]
        log_file = find_handler_log(twister_out_dir, platform, toolchain, test_path, scenario)
        if log_file:
            lines += [".. code-block:: none", ""]
            for line in log_file.read_text(errors="replace").splitlines():
                lines.append("   " + line)
            lines.append("")
        else:
            lines += [
                f"*handler.log not found for* ``{scenario}`` *on* ``{platform}``",
                "",
            ]
    return lines


# ---------------------------------------------------------------------------
# twisterinfo helpers
# ---------------------------------------------------------------------------

def _compute_platform_stats(suites):
    """Compute per-platform pass/fail/skip/error counts.

    Returns (platforms, stats, totals) where stats is a list of
    (platform, passed, failed, skipped, error, total) tuples and
    totals is (total_passed, total_failed, total_skipped, total_error).
    """
    platforms = sorted({s["platform"] for s in suites})
    by_platform = defaultdict(list)
    for s in suites:
        by_platform[s["platform"]].extend(s.get("testcases", []))

    stats, totals = [], [0, 0, 0, 0]
    for plat in platforms:
        counts = Counter(tc.get("status", "") for tc in by_platform[plat])
        p = counts.get("passed", 0)
        f = counts.get("failed", 0)
        s = counts.get("skipped", 0)
        e = counts.get("error", 0)
        totals[0] += p
        totals[1] += f
        totals[2] += s
        totals[3] += e
        stats.append((plat, p, f, s, e, len(by_platform[plat])))
    return platforms, stats, tuple(totals)


def _build_twisterinfo_rst(tw_env, suites, project_name="", project_version=""):
    """Build RST lines for the run-metadata and per-platform summary tables."""
    run_date_raw = tw_env.get("run_date", "")
    try:
        from datetime import datetime, timezone
        run_date = (
            datetime.fromisoformat(run_date_raw)
            .astimezone(timezone.utc)
            .strftime("%Y-%m-%d %H:%M:%S UTC")
        )
    except Exception:
        run_date = run_date_raw

    scenarios = sorted({s["name"] for s in suites})
    platforms, stats, (tp, tf, ts, te) = _compute_platform_stats(suites)
    total = tp + tf + ts + te
    total_str = (
        f"{total} (passed: {tp}"
        + (f", failed: {tf}" if tf else "")
        + (f", skipped: {ts}" if ts else "")
        + (f", error: {te}" if te else "")
        + ")"
    )

    lines = [
        ".. list-table:: Test Run Metadata",
        "   :header-rows: 0",
        "   :widths: 25 75",
        "",
        "   * - Run date",
        f"     - {run_date}",
        # Version under test. The VALUE comes from twister's own JSON
        # (`zephyr_version` is a key in twister's output schema, not branding —
        # reading it is no different from reading `testsuites`), so this row
        # stays consistent with every other row in this table, all of which
        # report facts about the run. A consumer that wants its own version
        # string instead can set `twisterinfo_project_version`; the LABEL is
        # likewise the consumer's via `twisterinfo_project_name`, which is what
        # de-branding this row actually required. Sourcing the value from
        # config alone dropped twister's reported version entirely.
        f"   * - {project_name + ' version' if project_name else 'Version under test'}",
        f"     - ``{project_version or tw_env.get('zephyr_version', '—')}``",
        "   * - Toolchain",
        f"     - {tw_env.get('toolchain', '—')}",
        "   * - Host OS",
        f"     - {tw_env.get('os', '—')}",
        "   * - Test scenarios",
        f"     - {', '.join(f'``{s}``' for s in scenarios)}",
        "   * - Platforms",
        f"     - {', '.join(f'``{p}``' for p in platforms)}",
        "   * - Total test cases",
        f"     - {total_str}",
        "",
        ".. list-table:: Results per Platform",
        "   :header-rows: 1",
        "   :widths: 50 15 15 10 10",
        "",
        "   * - Platform",
        "     - Passed",
        "     - Failed",
        "     - Skipped",
        "     - Total",
    ]
    for plat, p, f, s, e, total_plat in stats:
        lines += [
            f"   * - ``{plat}``",
            f"     - {p}",
            f"     - {f + e}",
            f"     - {s}",
            f"     - {total_plat}",
        ]
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# TestModuleDirective
# ---------------------------------------------------------------------------

class TestModuleDirective(Directive):
    """
    Emit sphinx-needs test_case nodes for all ZTEST functions in a module group.

    Usage::

        .. testmodule:: kernel_queue_module
           :module: tests/kernel/queue
    """

    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {
        "module": directives.unchanged,
    }

    def run(self):
        group_name = self.arguments[0].strip()
        module_path = self.options.get("module", "").strip("/")
        env = self.state.document.settings.env
        app = env.app

        xml_dir = Path(app.config.testmodule_xml_dir)
        if not xml_dir.is_dir():
            return [self.state_machine.reporter.error(
                f"testmodule: testmodule_xml_dir not found: {xml_dir}",
                nodes.literal_block(group_name, group_name),
                line=self.lineno,
            )]

        page_depth = len(Path(env.docname).parts) - 1
        page_prefix = "../" * page_depth
        testspec_html_dir = page_prefix + app.config.testspec_doxygen_url
        api_html_dir = page_prefix + app.config.api_doxygen_url
        # testmodule_root is supplied by the engine (zdocs_conf.py, defaulting
        # to ZDOCS_PROJECT_BASE) — no ZEPHYR_BASE fallback: that was a
        # project-specific env var name in a generic engine (decision 5).
        module_root = app.config.testmodule_root

        if not hasattr(env, "_testmodule_group_index"):
            try:
                env._testmodule_group_index = load_group_index(xml_dir)
            except RuntimeError as exc:
                logger.warning(str(exc))
                return [nodes.paragraph(text=str(exc))]

        module_refid = env._testmodule_group_index.get(group_name)
        if module_refid is None:
            logger.warning(f"testmodule: Doxygen group '{group_name}' not found in index.xml")
            return [
                nodes.paragraph(text=f"[testmodule: group '{group_name}' not in Doxygen index]")
            ]

        module_group_xml = xml_dir / f"{module_refid}.xml"
        if not module_group_xml.exists():
            logger.warning(
                f"testmodule: XML file not found for group '{group_name}': {module_group_xml}"
            )
            return [nodes.paragraph(text=f"[testmodule: XML missing for '{group_name}']")]

        module_cdef = ET.parse(module_group_xml).getroot().find("compounddef")
        suite_refids, proc_refids = _classify_inner_groups(module_cdef, xml_dir)

        need_names = _need_names_from_config(app)
        scenario_lines = build_scenario_table(Path(module_root) / module_path / "testcase.yaml")
        all_rst = list(scenario_lines)
        for suite_refid in suite_refids:
            all_rst += _build_suite_rst(
                suite_refid, xml_dir, testspec_html_dir, api_html_dir, module_path,
                need_names=need_names,
            )
        for proc_refid in proc_refids:
            all_rst += _build_proc_group_rst(
                proc_refid, xml_dir, testspec_html_dir, api_html_dir, need_names=need_names,
            )

        _maybe_dump_rst(app, env.docname, "testmodule", group_name, "\n".join(all_rst))
        return _render_rst(all_rst, self.state, self.content_offset, match_titles=True)


# ---------------------------------------------------------------------------
# TestReportDirective
# ---------------------------------------------------------------------------

class TestReportDirective(Directive):
    """
    Emit sphinx-needs test_result nodes from a twister_report.xml.

    Usage::

        .. testreport:: twister_report.xml
           :module: kernel.queue
    """

    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {
        "module": directives.unchanged,
    }

    def run(self):
        xml_path = self.arguments[0].strip()
        module_filter = self.options.get("module", "").strip() or None
        env = self.state.document.settings.env
        app = env.app

        if not Path(xml_path).is_absolute():
            base = getattr(app.config, "twister_output_dir", "") or str(
                Path(env.doc2path(env.docname)).parent
            )
            xml_path = str(Path(base) / xml_path)

        spec_json = getattr(app.config, "testspec_needs_json", "")
        if not spec_json:
            # Fallback: first external-needs source (legacy behaviour).
            ext_needs = getattr(app.config, "needs_external_needs", [])
            spec_json = ext_needs[0].get("json_path", "") if ext_needs else ""
        if not spec_json or not Path(spec_json).exists():
            msg = f"[testreport: spec needs.json not found: {spec_json!r}]"
            logger.warning(f"testreport: {msg}")
            # See _display_name's own docstring: the LOG line above keeps the
            # full absolute path (unchanged, on purpose); the PUBLISHED node
            # below must not.
            display_msg = f"[testreport: spec needs.json not found: {_display_name(spec_json)}]"
            return [nodes.paragraph(text=display_msg)]

        # Computed up front (not just below, alongside the RST builders) so
        # the spec lookup filters/reads the need TYPE and the "verifies"
        # LINK by the consumer's own configured names (step 26) rather than
        # the engine's literal defaults — the bug this step exists to fix.
        need_names = _need_names_from_config(app)
        try:
            spec_lookup = load_spec_lookup(spec_json, need_names=need_names)
        except Exception as exc:
            logger.warning(str(exc))
            return [nodes.paragraph(text=str(exc))]

        if not Path(xml_path).exists():
            msg = f"[testreport: twister XML not found: {xml_path}]"
            logger.warning(f"testreport: {msg}")
            # See _display_name's own docstring: the LOG line above keeps the
            # full absolute path (unchanged, on purpose); the PUBLISHED node
            # below must not.
            display_msg = f"[testreport: twister XML not found: {_display_name(xml_path)}]"
            return [nodes.paragraph(text=display_msg)]

        try:
            results = parse_twister_results(xml_path, module_filter)
        except Exception as exc:
            logger.warning(str(exc))
            return [nodes.paragraph(text=str(exc))]

        if not results:
            return [nodes.paragraph(text="[testreport: no matching results]")]

        suite_order, func_order, grouped = _group_results(results)
        twister_out_dir = getattr(app.config, "twister_output_dir", "")
        all_rst = (
            _build_results_rst(suite_order, func_order, grouped, spec_lookup, need_names=need_names)
            + _build_summary_table_rst(grouped, spec_lookup, need_names=need_names)
            + _build_exec_logs_rst(twister_out_dir, module_filter)
        )

        _maybe_dump_rst(app, env.docname, "testreport", module_filter or "", "\n".join(all_rst))
        return _render_rst(all_rst, self.state, self.content_offset, match_titles=True)


# ---------------------------------------------------------------------------
# TwisterInfoDirective
# ---------------------------------------------------------------------------

class TwisterInfoDirective(Directive):
    """Emit a run-metadata block and per-platform summary table from twister.json.

    Usage::

        .. twisterinfo:: twister.json
    """

    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {}

    def run(self):
        json_path = self.arguments[0].strip()
        env = self.state.document.settings.env
        app = env.app

        if not Path(json_path).is_absolute():
            base = getattr(app.config, "twister_output_dir", "") or str(
                Path(env.doc2path(env.docname)).parent
            )
            json_path = str(Path(base) / json_path)

        if not Path(json_path).exists():
            msg = f"[twisterinfo: twister.json not found: {json_path!r}]"
            logger.warning(f"twisterinfo: {msg}")
            # See _display_name's own docstring: the LOG line above keeps the
            # full absolute path (unchanged, on purpose); the PUBLISHED node
            # below must not.
            display_msg = f"[twisterinfo: twister.json not found: {_display_name(json_path)}]"
            return [nodes.paragraph(text=display_msg)]

        try:
            data = load_twister_meta(json_path)
        except Exception as exc:
            logger.warning(f"twisterinfo: cannot read {json_path}: {exc}")
            return [nodes.paragraph(text=str(exc))]

        lines = _build_twisterinfo_rst(
            data.get("environment", {}),
            data.get("testsuites", []),
            project_name=getattr(app.config, "twisterinfo_project_name", ""),
            project_version=getattr(app.config, "twisterinfo_project_version", ""),
        )
        _maybe_dump_rst(app, env.docname, "twisterinfo", Path(json_path).name, "\n".join(lines))
        return _render_rst(lines, self.state, self.content_offset)


# ---------------------------------------------------------------------------
# Extension setup
# ---------------------------------------------------------------------------

def setup(app):
    app.add_config_value("testmodule_xml_dir", "", "env")
    app.add_config_value("testspec_needs_json", "", "env")
    app.add_config_value("testspec_doxygen_url", "", "env")
    app.add_config_value("api_doxygen_url", "", "env")
    # requirements_url deliberately NOT registered (decision 4): it was
    # computed at conf_test_common.py:56 and consumed nowhere in any of the
    # four modules — deleted outright, not migrated and left unset.
    app.add_config_value("twister_output_dir", "", "env")
    app.add_config_value("testmodule_root", "", "env")
    app.add_config_value("twisterinfo_project_name", "", "env")
    app.add_config_value("twisterinfo_project_version", "", "env")
    app.add_config_value("dump_generated_rst", "", "env")
    app.add_config_value(
        "testmodule_need_types",
        {"case": "test_case", "procedure": "test_procedure", "result": "test_result"},
        "env",
    )
    app.add_config_value(
        "testmodule_need_links",
        {"verifies": "verifies", "result_of": "result_of", "covers": "covers"},
        "env",
    )
    app.add_directive("testmodule", TestModuleDirective)
    app.add_directive("testreport", TestReportDirective)
    app.add_directive("twisterinfo", TwisterInfoDirective)
    return {"version": "0.2", "parallel_read_safe": True}
