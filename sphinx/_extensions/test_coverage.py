# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: the testcoverage directive (coverage adequacy as needs).

``.. testcoverage::`` reads a per-test coverage run (`adequacy`) and emits one
adequacy need per requirement that the run can assess. Each need links to its
requirement (link role ``assesses``) and carries the verdict. The directive
also writes a summary of the run and the distribution of the verdicts.
"""

import re
from collections import Counter
from pathlib import Path

from adequacy import (
    IMPL_PATTERNS,
    VERDICTS,
    Source,
    assess,
    collect_links,
    line_ranges,
    load_coverage_run,
)
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import ViewList
from input_tracking import _note_input
from needs_fields import field_type
from rst_builders import _need_name

from sphinx.util import logging

logger = logging.getLogger(__name__)

#: The adequacy field roles (`testcoverage_need_fields`).
ADEQUACY_FIELD_ROLES = ("verdict", "evidence", "coverage_run", "judged_symbols", "symbol_hits")

#: What each verdict says, for the distribution table.
VERDICT_MEANING = {
    "broken": "Tests of the run reach the code. The requirement's own tests never do.",
    "partial": "The own tests run some of the satisfying symbols, not all.",
    "unattributed": "No test of the run covers any body. Coverage cannot judge the link.",
    "unresolved": "No satisfying symbol maps to a body (a macro).",
    "no-cov": "The verifying tests have no coverage data in this run.",
    "no-impl": "No symbol satisfies the requirement.",
    "true": "The own tests run every symbol that coverage can judge.",
}

#: At most this many other tests are named for one body.
_OTHER_TESTS_SHOWN = 10


def _need_names(config):
    """The role->name mapping of every vocabulary the directive reads or writes."""
    names = {}
    for key in (
        "testmodule_need_types", "testmodule_need_links",
        "symbolneeds_need_types", "symbolneeds_need_links",
        "testcoverage_need_types", "testcoverage_need_links", "testcoverage_need_fields",
    ):
        names.update(getattr(config, key, {}) or {})
    return names


def adequacy_need_id(run, req, prefix="ADQ"):
    """``<prefix>-<run>/<req>``, the id of ``req``'s adequacy need in ``run``."""
    return f"{prefix}-{run}/{req}"


def _natural(uid):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", uid)]


def _need_ref(key, run):
    """A matrix key as the case needs it stands for, else as a literal."""
    cases = sorted(run.case_of_key.get(key, ()))
    return ", ".join(f":need:`{c}`" for c in cases) if cases else f"``{key}``"


def _symbol_hits(impls):
    """``"k_sem_init: own 11, any 11"`` per symbol, joined with ``"; "``."""
    own, any_, order = Counter(), Counter(), []
    for d in impls:
        if d["sym"] not in order:
            order.append(d["sym"])
        own[d["sym"]] += d["own"]
        any_[d["sym"]] += d["any"]
    return "; ".join(f"{s}: own {own[s]}, any {any_[s]}" for s in order)


def build_adequacy_rst(req, res, run, need_names=None, fields=(), prefix="ADQ", layout=""):
    """RST lines for the adequacy need of ``req`` (``res`` from `adequacy.assess`).

    ``layout``: the sphinx-needs layout of the need, if not empty.
    """
    values = {
        "verdict": res["verdict"],
        "evidence": res["evidence"],
        "coverage_run": run.name,
        "judged_symbols": "; ".join(res["symbols"]),
        "symbol_hits": _symbol_hits(res["impls"]),
    }
    lines = [
        f".. {_need_name(need_names, 'adequacy')}:: Adequacy of {req}",
        f"   :id: {adequacy_need_id(run.name, req, prefix)}",
        f"   :{_need_name(need_names, 'assesses')}: {req}",
    ]
    for role in ADEQUACY_FIELD_ROLES:
        if role in fields and values[role]:
            lines.append(f"   :{_need_name(need_names, role)}: {values[role]}")
    if layout:
        lines.append(f"   :layout: {layout}")
    lines += [
        "",
        f"   Verdict ``{res['verdict']}``, evidence ``{res['evidence']}``, "
        f"coverage run ``{run.name}``.",
        "",
    ]
    cases = ", ".join(f":need:`{c}`" for c in res["cases"])
    lines += [f"   Verifying test cases: {cases}.", ""]
    if not res["impls"]:
        lines += ["   No symbol satisfies this requirement.", ""]
        return lines
    lines += [
        "   .. list-table:: Satisfying symbols",
        "      :header-rows: 1",
        "      :widths: 20 10 30 10 10",
        "",
        "      * - Symbol",
        "        - Body",
        "        - Location",
        "        - Own lines",
        "        - Any lines",
    ]
    for d in res["impls"]:
        loc = f"``{d['file']}:{d['a']}-{d['b']}``" if d["file"] else "no body found"
        lines += [
            f"      * - ``{d['sym']}``",
            f"        - {d['variant'] or '—'}",
            f"        - {loc}",
            f"        - {d['own']}",
            f"        - {d['any']}",
        ]
    lines.append("")
    for d in res["impls"]:
        if not d["file"] or not (d["own_tests"] or d["other_tests"]):
            continue
        lines += [f"   ``{d['sym']}`` ({d['variant']}, ``{d['file']}:{d['a']}-{d['b']}``):", ""]
        for case, hit in d["own_tests"].items():
            lines.append(f"   * own :need:`{case}`: lines {line_ranges(hit)}")
        others = list(d["other_tests"].items())
        for key, hit in others[:_OTHER_TESTS_SHOWN]:
            lines.append(f"   * other {_need_ref(key, run)}: lines {line_ranges(hit)}")
        if len(others) > _OTHER_TESTS_SHOWN:
            lines.append(f"   * and {len(others) - _OTHER_TESTS_SHOWN} other tests")
        lines.append("")
    return lines


def build_coverage_rst(
    results, run, source, impl_loc, need_names=None, fields=(), prefix="ADQ", layout="",
    impl_files=IMPL_PATTERNS,
):
    """RST lines for the whole directive: run summary, distribution, needs by verdict.

    ``impl_files``: the body files that the run searched, for the summary.
    """
    counts = Counter(r["verdict"] for r in results.values())
    symbols = sorted({s for r in results.values() for s in r["symbols"]})
    lines = [
        ".. list-table:: Coverage run",
        "   :header-rows: 0",
        "   :widths: 30 70",
        "",
        "   * - Run",
        f"     - ``{run.name}``",
        "   * - Sources read at",
        f"     - ``{source.describe()}``",
        "   * - Files searched for bodies",
        "     - " + ", ".join(f"``{p}``" for p in impl_files),
        "   * - Tests in the coverage matrix",
        f"     - {len(run.by_test)}",
        "   * - Spec test cases the run ran",
        f"     - {len(run.cases)}",
        "   * - Requirements assessed",
        f"     - {len(results)}",
        "   * - Satisfying symbols (with a body)",
        f"     - {len(symbols)} ({sum(1 for s in symbols if s in impl_loc)})",
        "",
        ".. list-table:: Verdicts",
        "   :header-rows: 1",
        "   :widths: 15 10 75",
        "",
        "   * - Verdict",
        "     - Requirements",
        "     - Meaning",
    ]
    for v in VERDICTS:
        lines += [f"   * - ``{v}``", f"     - {counts.get(v, 0)}", f"     - {VERDICT_MEANING[v]}"]
    lines.append("")
    for v in VERDICTS:
        reqs = sorted((r for r, res in results.items() if res["verdict"] == v), key=_natural)
        if not reqs:
            continue
        heading = f"Verdict {v}"
        lines += [heading, "-" * len(heading), ""]
        for req in reqs:
            lines += build_adequacy_rst(
                req, results[req], run, need_names, fields, prefix, layout
            )
    return lines


class TestCoverageDirective(Directive):
    """Emit one adequacy need per requirement that a per-test coverage run can assess.

    Usage::

        .. testcoverage::
           :run: my-run
           :layout: adequacy

    The optional argument is the run directory. Without it, the directive reads
    ``coverage_output_dir`` (``ZDOCS_COVERAGE_OUT``). ``:run:`` names the run in
    the need ids. Without it, the name is the first tag on the run commit, or
    else the name of the run directory. ``:layout:`` sets the sphinx-needs
    layout of each need. ``testcoverage_impl_files`` sets the files that hold
    the bodies of the satisfying symbols.
    """

    required_arguments = 0
    optional_arguments = 1
    has_content = False
    option_spec = {"run": directives.unchanged, "layout": directives.unchanged}

    def _paragraph(self, text):
        return [nodes.paragraph(text=text)]

    def run(self):
        env = self.state.document.settings.env
        app = env.app
        config = app.config
        run_dir = (self.arguments[0].strip() if self.arguments else "") or getattr(
            config, "coverage_output_dir", ""
        )
        if not run_dir:
            return self._paragraph("[testcoverage: no coverage run configured]")
        run_dir = Path(run_dir)
        for name in ("twister.json", "coverage/test_matrix.json", "zephyr.sha"):
            _note_input(env, run_dir / name)
        if not (run_dir / "coverage" / "test_matrix.json").is_file():
            logger.warning(f"testcoverage: no coverage/test_matrix.json in {run_dir}")
            return self._paragraph(
                f"[testcoverage: coverage matrix not found in {run_dir.name}]"
            )

        need_names = _need_names(config)
        json_paths = [
            e["json_path"] for e in getattr(config, "needs_external_needs", []) or []
            if e.get("json_path")
        ]
        spec_json = getattr(config, "testspec_needs_json", "")
        if spec_json:
            json_paths.append(spec_json)
        json_paths = [p for p in dict.fromkeys(json_paths) if Path(p).is_file()]
        for p in json_paths:
            _note_input(env, p)

        root = getattr(config, "testmodule_root", "") or env.srcdir
        impl_files = tuple(getattr(config, "testcoverage_impl_files", None) or IMPL_PATTERNS)
        try:
            spec_lookup, verified_by, satisfied_by, ids = collect_links(json_paths, need_names)
            run, _ = load_coverage_run(
                run_dir, spec_lookup, root, name=self.options.get("run", "").strip() or None,
                impl_files=impl_files,
            )
        except Exception as exc:
            logger.warning(f"testcoverage: cannot read the coverage run {run_dir}: {exc}")
            return self._paragraph(f"[testcoverage: cannot read {run_dir.name}]")
        if not run.sha:
            logger.warning(
                f"testcoverage: the commit of {run_dir} is not in {root}; the sources "
                f"come from the working tree, and line ranges can be wrong for files "
                f"changed since the run"
            )
        source = Source(root, run.sha)
        results, impl_loc = assess(run, verified_by, satisfied_by, source, ids, impl_files)
        if not results:
            return self._paragraph("[testcoverage: the run ran no verifying test case]")

        fields = {
            role for role in ADEQUACY_FIELD_ROLES
            if field_type(env, _need_name(need_names, role)) is not None
        }
        lines = build_coverage_rst(
            results, run, source, impl_loc, need_names, fields,
            getattr(config, "testcoverage_id_prefix", "ADQ"),
            self.options.get("layout", "").strip(),
            impl_files,
        )
        dump_dir = getattr(config, "dump_generated_rst", "")
        if dump_dir:
            out = Path(dump_dir)
            out.mkdir(parents=True, exist_ok=True)
            doc_slug = env.docname.replace("/", "__")
            (out / f"{doc_slug}__testcoverage__{run.name}.rst").write_text(
                "\n".join(lines), encoding="utf-8"
            )
        container = nodes.container()
        self.state.nested_parse(
            ViewList(lines, source="<generated>"), self.content_offset, container,
            match_titles=True,
        )
        return container.children


def setup(app):
    # The per-test coverage run directory (ZDOCS_COVERAGE_OUT): twister.json,
    # coverage/test_matrix.json and zephyr.sha.
    app.add_config_value("coverage_output_dir", "", "env")
    app.add_config_value("testcoverage_id_prefix", "ADQ", "env")
    # Glob patterns of the files that hold the bodies, relative to testmodule_root.
    app.add_config_value("testcoverage_impl_files", list(IMPL_PATTERNS), "env")
    app.add_config_value("testcoverage_need_types", {"adequacy": "adequacy"}, "env")
    app.add_config_value("testcoverage_need_links", {"assesses": "assesses"}, "env")
    # Field roles -> names. A field is set only where the consumer declares it.
    app.add_config_value(
        "testcoverage_need_fields", {role: role for role in ADEQUACY_FIELD_ROLES}, "env"
    )
    app.add_directive("testcoverage", TestCoverageDirective)
    app.setup_extension("input_tracking")
    return {"version": "0.1", "parallel_read_safe": True}
