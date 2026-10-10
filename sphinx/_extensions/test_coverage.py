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
    need_titles,
)
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import ViewList
from doxygen_parser import SourcePages
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

#: At most this many test cases are named for one group of other tests.
_OTHER_TESTS_SHOWN = 10

#: The function whose body the directive reads, by body form.
_BODY_NAME = {"impl": "z_impl_{}", "vrfy": "z_vrfy_{}", "def": "{}", "inline": "{}"}
_BODY_FORM = {"impl": "implementation", "vrfy": "verifier", "def": "definition",
              "inline": "static inline"}

#: The roles of the body table cells: each gives an inline node with the
#: role name as its class, for ``zdocs-needs.css``. The place of a body is a
#: paragraph of class ``zd-adq-loc``.
CELL_ROLES = ("zd-adq-ok", "zd-adq-miss", "zd-adq-none")

#: The engine fields that the body shows when the consumer does not declare them.
_BODY_FALLBACK = (("verdict", "Verdict"), ("evidence", "Evidence"),
                  ("coverage_run", "Coverage run"))


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


def _symbol_hits(impls):
    """``"k_sem_init: own 11, any 11"`` per symbol, joined with ``"; "``."""
    own, any_, order = Counter(), Counter(), []
    for d in impls:
        if d["sym"] not in order:
            order.append(d["sym"])
        own[d["sym"]] += d["own"]
        any_[d["sym"]] += d["any"]
    return "; ".join(f"{s}: own {own[s]}, any {any_[s]}" for s in order)


def _code_list(names):
    """```a``, ``b`` and ``c```."""
    names = [f"``{n}``" for n in names]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _symbol_states(impls):
    """``{symbol: (has a body, a test of the run ran it, an own test ran it)}``."""
    states = {}
    for d in impls:
        body, seen, hit = states.get(d["sym"], (False, False, False))
        states[d["sym"]] = (body or d["file"] is not None, seen or d["any"] > 0,
                            hit or d["own"] > 0)
    return states


def adequacy_summary(res):
    """One sentence (RST) that says why the verdict of ``res`` is what it is."""
    verdict = res["verdict"]
    states = _symbol_states(res["impls"])
    judged = [s for s, (_, seen, _) in states.items() if seen]
    missed = [s for s in judged if not states[s][2]]
    not_judged = [s for s in states if s not in judged]
    if verdict == "no-impl":
        return "No symbol satisfies this requirement."
    if verdict == "unresolved":
        verb = "has" if len(states) == 1 else "have"
        return (f"{_code_list(list(states))} {verb} no function body in the files "
                f"that the directive searched.")
    if verdict == "no-cov":
        return "The run has no coverage data for the own tests."
    if verdict == "unattributed":
        return ("No test of the run runs a body of the satisfying symbols. Coverage "
                "cannot judge the link.")
    if verdict == "partial":
        return (f"The own tests run {len(judged) - len(missed)} of the {len(judged)} "
                f"symbols that coverage can judge. Only other tests run "
                f"{_code_list(missed)}.")
    if verdict == "broken":
        return f"Only other tests run {_code_list(missed)}. The own tests never do."
    # true
    if not not_judged:
        return {1: "The own tests run the satisfying symbol.",
                2: "The own tests run both satisfying symbols."}.get(
            len(judged), f"The own tests run all {len(judged)} satisfying symbols.")
    what = "the one symbol" if len(judged) == 1 else f"all {len(judged)} symbols"
    return (f"The own tests run {what} that coverage can judge. Coverage cannot "
            f"judge {_code_list(not_judged)}.")


def _own_cell(d):
    if d["any"] == 0:
        return ":zd-adq-none:`no test ran it`"
    role = "zd-adq-ok" if d["own"] else "zd-adq-miss"
    return f":{role}:`{d['own']} of {d['any']} lines`"


def _other_groups(d, run):
    """The other tests of body ``d`` as ``[(line ranges, [case refs])]``.

    A case once, however many matrix keys it has; a key that no spec case has
    stays a literal. The cases that ran the same lines form one group: the
    largest group first, then by the first case.
    """
    groups = {}
    for key, hit in d["other_tests"].items():
        refs = groups.setdefault(line_ranges(hit), [])
        for case in sorted(run.case_of_key.get(key, ())) or [None]:
            ref = f":need:`{case}`" if case else f"``{key}``"
            if ref not in refs:
                refs.append(ref)
    groups = [(r, sorted(c, key=_natural)) for r, c in groups.items()]
    return sorted(groups, key=lambda g: (-len(g[1]), _natural(g[1][0])))


def _other_count(d, run):
    return len({c for key in d["other_tests"] for c in run.case_of_key.get(key, ()) or [key]})


def build_adequacy_rst(req, res, run, need_names=None, fields=(), prefix="ADQ", layout="",
                       title=None, body_url=None):
    """RST lines for the adequacy need of ``req`` (``res`` from `adequacy.assess`).

    ``layout``: the sphinx-needs layout of the need, if not empty. ``title``:
    the title of the requirement; the need has it as its own title. Without it,
    the title is ``Adequacy of <req>``.

    The body says why the verdict is what it is. A table gives each body of a
    satisfying symbol: the lines that the own tests ran, of the lines that any
    test of the run ran, and the number of other test cases that ran it. For
    a body that the own tests never run, the body names the other tests that
    do. A field that the consumer does not declare is in the body too.

    ``body_url(file, line)``: the source listing of a body at its first line,
    or ``""``; the place of the body links to it.
    """
    values = {
        "verdict": res["verdict"],
        "evidence": res["evidence"],
        "coverage_run": run.name,
        "judged_symbols": "; ".join(res["symbols"]),
        "symbol_hits": _symbol_hits(res["impls"]),
    }
    lines = [
        f".. {_need_name(need_names, 'adequacy')}:: {title or f'Adequacy of {req}'}",
        f"   :id: {adequacy_need_id(run.name, req, prefix)}",
        f"   :{_need_name(need_names, 'assesses')}: {req}",
    ]
    for role in ADEQUACY_FIELD_ROLES:
        if role in fields and values[role]:
            lines.append(f"   :{_need_name(need_names, role)}: {values[role]}")
    if layout:
        lines.append(f"   :layout: {layout}")
    lines += ["", f"   {adequacy_summary(res)}", ""]
    bodies = [d for d in res["impls"] if d["file"]]
    if bodies:
        lines += [
            "   .. list-table::",
            "      :header-rows: 1",
            "      :class: zd-adq-bodies",
            "",
            "      * - Body",
            "        - Own tests ran",
            "        - Other tests",
        ]
        for d in bodies:
            name = _BODY_NAME[d["variant"]].format(d["sym"])
            others = _other_count(d, run)
            others = f"{others} test case{'s' if others != 1 else ''}" if others else "none"
            place = f"{d['file']}:{d['a']}-{d['b']}"
            url = body_url(d["file"], d["a"]) if body_url else ""
            place = f"`{place} <{url}>`__" if url else place
            lines += [
                f"      * - ``{name}``",
                "",
                "          .. rst-class:: zd-adq-loc",
                "",
                f"          {_BODY_FORM[d['variant']]}, {place}",
                f"        - {_own_cell(d)}",
                f"        - {others}",
            ]
        lines.append("")
    no_body = [s for s, (body, _, _) in _symbol_states(res["impls"]).items() if not body]
    if bodies and no_body:
        lines += [f"   No body found: {_code_list(no_body)}.", ""]
    # Who runs the code that the own tests miss: where a @verifies can go.
    for d in bodies:
        if d["own"] or not d["other_tests"]:
            continue
        name = _BODY_NAME[d["variant"]].format(d["sym"])
        lines += [f"   Other tests that run ``{name}``:", ""]
        for ranges, refs in _other_groups(d, run):
            more = len(refs) - _OTHER_TESTS_SHOWN
            tail = f" and {more} more" if more > 0 else ""
            lines.append(f"   * lines {ranges}: {', '.join(refs[:_OTHER_TESTS_SHOWN])}{tail}")
        lines.append("")
    cases = ", ".join(f":need:`{c}`" for c in res["cases"])
    lines += ["   .. container:: need-refs", "", f"      **Verifying tests:** {cases}", ""]
    for role, label in _BODY_FALLBACK:
        if role not in fields:
            lines += [f"      **{label}:** {values[role]}", ""]
    return lines


def build_coverage_rst(
    results, run, source, impl_loc, need_names=None, fields=(), prefix="ADQ", layout="",
    impl_files=IMPL_PATTERNS, titles=None, body_url=None,
):
    """RST lines for the whole directive: run summary, distribution, needs by verdict.

    ``impl_files``: the body files that the run searched, for the summary.
    ``titles``: the title of each requirement, for the title of its need.
    ``body_url``: see `build_adequacy_rst`.
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
                req, results[req], run, need_names, fields, prefix, layout,
                (titles or {}).get(req), body_url,
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

    def _body_url(self, env):
        """``(file, line) -> URL`` of the first source listing that has the file,
        of the Doxygen documents in ``testcoverage_source_docs``, in that order,
        and the `SourcePages` it reads (their inputs are noted after the use)."""
        app, config = env.app, env.app.config
        docs = getattr(config, "zdocs_doxygen_docs", {}) or {}
        page_prefix = "../" * (len(Path(env.docname).parts) - 1)
        cache = app.__dict__.setdefault("_testcoverage_source_pages", {})
        listings = []
        for doc_id in getattr(config, "testcoverage_source_docs", []) or []:
            doc = docs.get(doc_id)
            if doc is None:
                logger.warning(
                    f"testcoverage: testcoverage_source_docs names '{doc_id}', "
                    f"which is no kind: doxygen document of the registry"
                )
                continue
            if doc_id not in cache:
                cache[doc_id] = SourcePages(doc["xml_dir"])
            listings.append((cache[doc_id], page_prefix + doc["html_url"]))

        def body_url(path, line):
            for pages, html_dir in listings:
                url = pages.url(html_dir, path, line, tail=True)
                if url:
                    return url
            return ""

        return (body_url if listings else None), [pages for pages, _ in listings]

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
        body_url, source_pages = self._body_url(env)
        lines = build_coverage_rst(
            results, run, source, impl_loc, need_names, fields,
            getattr(config, "testcoverage_id_prefix", "ADQ"),
            self.options.get("layout", "").strip(),
            impl_files,
            need_titles(json_paths),
            body_url,
        )
        # The listings are shared by all documents: this notes the files that
        # the lookups of all documents so far read, a superset of this one's.
        for pages in source_pages:
            for path in sorted(pages.inputs):
                _note_input(env, path)
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


def _cell_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    return [nodes.inline(rawtext, text, classes=[name])], []


def setup(app):
    for role in CELL_ROLES:
        app.add_role(role, _cell_role)
    # The per-test coverage run directory (ZDOCS_COVERAGE_OUT): twister.json,
    # coverage/test_matrix.json and zephyr.sha.
    app.add_config_value("coverage_output_dir", "", "env")
    app.add_config_value("testcoverage_id_prefix", "ADQ", "env")
    # Glob patterns of the files that hold the bodies, relative to testmodule_root.
    app.add_config_value("testcoverage_impl_files", list(IMPL_PATTERNS), "env")
    # The Doxygen documents (registry ids) whose source listings the place of
    # a body links to: the first that has the file.
    app.add_config_value("testcoverage_source_docs", [], "env")
    app.add_config_value("zdocs_doxygen_docs", {}, "env")
    app.add_config_value("testcoverage_need_types", {"adequacy": "adequacy"}, "env")
    app.add_config_value("testcoverage_need_links", {"assesses": "assesses"}, "env")
    # Field roles -> names. A field is set only where the consumer declares it.
    app.add_config_value(
        "testcoverage_need_fields", {role: role for role in ADEQUACY_FIELD_ROLES}, "env"
    )
    app.add_directive("testcoverage", TestCoverageDirective)
    app.setup_extension("input_tracking")
    return {"version": "0.1", "parallel_read_safe": True}
