# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Twister output parsing — no Sphinx dependency."""

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# `_need_name` resolves an engine ROLE ("case", "verifies", ...) to a
# consumer-configured NAME (zdocs step 26, zdocs-design-twister.md §12).
# `rst_builders.py` carries the same "no Sphinx, no app.config" rule this
# module follows — the mapping is passed in by the caller, never read from
# config here — so importing its pure helper does not violate that rule.
from rst_builders import _need_name, _values_summary

__all__ = [
    "split_case_name",
    "parse_twister_results",
    "normalise_test_path",
    "scenario_selected",
    "testsuite_paths",
    "testcase_statuses",
    "fold_parameterized_results",
    "SpecLookup",
    "load_spec_lookup",
    "find_handler_log",
    "find_build_config",
    "read_kconfig",
    "UnparseableCondition",
    "evaluate_condition",
    "depends_met",
    "skip_class",
    "load_twister_meta",
]


def _elem_text(elem):
    """Collapse all text nodes in elem into a single whitespace-normalised string."""
    if elem is None:
        return ""
    return " ".join("".join(elem.itertext()).split())


def normalise_test_path(path):
    """A testsuite path in one spelling: forward slashes, no ``./``, no trailing ``/``.

    Twister writes ``path`` relative to ZEPHYR_BASE with forward slashes; a
    consumer typing the same directory may add a trailing slash or a leading
    ``./``, or come from a Windows checkout. None of that changes which
    directory it is.
    """
    p = str(path).replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def testsuite_paths(twister_meta):
    """``{(platform, scenario): normalised path}`` from a loaded twister.json.

    twister_report.xml carries no path, only the scenario (``classname``) per
    platform, so the path a result came from is found here, by the same pair.
    """
    return {
        (ts.get("platform", ""), ts.get("name", "")): normalise_test_path(ts.get("path", ""))
        for ts in twister_meta.get("testsuites", [])
    }


def scenario_selected(
    platform, scenario, module_filter=None, exact=False, path_filter=None, suite_paths=None
):
    """Whether a (platform, scenario) run belongs to the report being built.

    ``module_filter`` matches the scenario name, as a dotted prefix (or exactly
    with ``exact``). ``path_filter`` matches the testsuite directory exactly,
    looked up in ``suite_paths`` (see `testsuite_paths`). With both, a run must
    satisfy both. With neither, every run is selected.

    The scenario prefix alone is not a module: upstream scenario names do not
    follow the directory layout (``kernel.timer`` is tests/kernel/timer/timer_api,
    and prefixes ``kernel.timer.error_case`` from timer_error_case), so only
    the path identifies a module's results reliably.
    """
    if module_filter:
        if exact:
            if scenario != module_filter:
                return False
        elif not (scenario == module_filter or scenario.startswith(module_filter + ".")):
            return False
    if path_filter is not None:
        path = (suite_paths or {}).get((platform, scenario))
        if path is None or path != normalise_test_path(path_filter):
            return False
    return True


def split_case_name(name, scenario):
    """``(suite, function, instance)`` of twister test case ``name`` in ``scenario``.

    Twister names a case ``<scenario>.<suite>.<fn>``, with ztest's ``test_``
    stripped from ``fn`` (and so from ``function`` here). A parameterized test
    (ZTEST_P) reports one case per value as ``<scenario>.<fn>[<instantiation>/
    <value>]``: no suite segment (``suite`` is ``""``), and the value may
    contain anything, dots included, so it is split off before the name is.
    ``instance`` is the part in brackets, or ``None``.
    """
    base, instance = name, None
    if name.endswith("]") and "[" in name:
        cut = name.index("[")
        base, instance = name[:cut], name[cut + 1 : -1]
    suffix = base[len(scenario) + 1 :] if base.startswith(scenario + ".") else base
    parts = suffix.rsplit(".", 1)
    suite = parts[0] if len(parts) == 2 else ""
    function = parts[-1]
    if function.startswith("test_"):
        function = function[5:]
    return suite, function, instance


def parse_twister_results(
    xml_path, module_filter=None, exact=False, path_filter=None, suite_paths=None
):
    """Parse twister_report.xml into a list of result dicts.

    The 'function' field has any leading 'test_' prefix stripped so it matches
    the keys used in spec_lookup. Results are selected as `scenario_selected`
    describes; ``path_filter`` needs ``suite_paths`` from the run's twister.json.
    """
    root = ET.parse(xml_path).getroot()
    results = []
    for ts in root.findall("testsuite"):
        platform = ts.get("name", "")
        for tc in ts.findall("testcase"):
            classname = tc.get("classname", "")
            if not scenario_selected(
                platform, classname, module_filter, exact, path_filter, suite_paths
            ):
                continue
            name = tc.get("name", "")
            scenario = classname
            suite, function, instance = split_case_name(name, scenario)
            failure = tc.find("failure")
            error = tc.find("error")
            skipped = tc.find("skipped")
            if failure is not None:
                status, reason = "failed", failure.get("message", "") or _elem_text(failure)
            elif error is not None:
                status, reason = "error", error.get("message", "") or _elem_text(error)
            elif skipped is not None:
                status, reason = "skipped", skipped.get("message", "") or _elem_text(skipped)
            else:
                status, reason = "passed", ""
            if instance is not None and status in ("failed", "error"):
                # Twister gives every value the suite's own message ("Testsuite
                # failed"); the assertion is in the element's text.
                reason = _assertion_text(failure if failure is not None else error) or reason
            result = {
                "platform": platform,
                "scenario": scenario,
                "suite": suite,
                "function": function,
                "twister_id": name,
                "time": tc.get("time", ""),
                "status": status,
                "reason": reason,
            }
            if instance is not None:
                result["instance"] = instance
            results.append(result)
    return results


_ZTEST_MARKER = re.compile(r"^\s*(START|PASS|FAIL|SKIP) - ")


def _assertion_text(elem):
    """The text of a failure element without ztest's START/PASS/FAIL marker lines."""
    lines = (elem.text or "").splitlines() if elem is not None else []
    kept = [line.strip() for line in lines if line.strip() and not _ZTEST_MARKER.match(line)]
    return " ".join(kept)


def testcase_statuses(twister_meta):
    """``{(platform, testcase identifier): status}`` from a loaded twister.json.

    twister.json keeps statuses the JUnit XML cannot express — ``blocked`` in
    particular, which the XML reports as a failure.
    """
    return {
        (ts.get("platform", ""), tc.get("identifier", "")): tc.get("status", "")
        for ts in twister_meta.get("testsuites", [])
        for tc in ts.get("testcases", [])
    }


def _attach_values(aggregate, instances, twister_statuses):
    """Make ``aggregate`` the result of its parameter values.

    The verdict comes from the values: failed if any failed, error if any
    errored, skipped if all were skipped, else passed. Twister's own status for
    the aggregate is kept in ``twister_status`` when it disagrees: ztest
    summarises a partly failing ZTEST_P as FLAKY, which twister does not
    recognise and reports as ``blocked`` (twister.json) or "Testsuite failed"
    (the XML).
    """
    values = [
        {"value": r["instance"], "status": r["status"], "reason": r["reason"], "time": r["time"]}
        for r in instances
    ]
    statuses = {v["status"] for v in values}
    if "failed" in statuses:
        verdict = "failed"
    elif "error" in statuses:
        verdict = "error"
    elif statuses == {"skipped"}:
        verdict = "skipped"
    else:
        verdict = "passed"
    reported = aggregate.get("status", "")
    if twister_statuses:
        reported = twister_statuses.get((aggregate["platform"], aggregate["twister_id"]), reported)
    aggregate["values"] = values
    aggregate["twister_status"] = reported if reported and reported != verdict else ""
    aggregate["status"] = verdict
    aggregate["reason"] = "" if verdict == "passed" else _values_summary(values)
    if not aggregate.get("time"):
        aggregate["time"] = f"{sum(float(v['time'] or 0) for v in values):.2f}"


def fold_parameterized_results(results, spec_lookup=None, twister_statuses=None):
    """Attach each parameterized test's value results to its aggregate result.

    Twister reports a ZTEST_P function once as the aggregate
    ``<scenario>.<suite>.<fn>`` (from ztest's summary) and once per value as
    ``<scenario>.<fn>[<instantiation>/<value>]`` (see `parse_twister_results`,
    which marks the latter with ``instance``). The spec has one test case for
    the function, so the values belong to the aggregate of the same run
    (platform and scenario), found by the function name.

    A run without an aggregate gets one, with the suite taken from the
    aggregates of other runs of the same scenario and function if they name
    exactly one, else from the spec (``spec_lookup``) if exactly one case
    carries the function.

    Returns ``(results, unmatched)``: the results without the value entries,
    and the function names whose values could not be attached, once each.
    """
    plain, by_run = [], {}
    for r in results:
        if r.get("instance") is None:
            plain.append(r)
        else:
            by_run.setdefault((r["platform"], r["scenario"], r["function"]), []).append(r)
    if not by_run:
        return results, []

    aggregates = {}
    for r in plain:
        aggregates.setdefault((r["platform"], r["scenario"], r["function"]), []).append(r)

    unmatched = []
    for (platform, scenario, fn), instances in by_run.items():
        hits = aggregates.get((platform, scenario, fn), [])
        if len(hits) == 1:
            aggregate = hits[0]
        elif hits:
            aggregate = None  # several suites share the name in this run
        else:
            aggregate = _synthesized_aggregate(
                platform, scenario, fn, aggregates, spec_lookup
            )
            if aggregate is not None:
                plain.append(aggregate)
        if aggregate is None:
            if fn not in unmatched:
                unmatched.append(fn)
            continue
        _attach_values(aggregate, instances, twister_statuses)
    return plain, unmatched


def _synthesized_aggregate(platform, scenario, fn, aggregates, spec_lookup):
    suites = {
        r["suite"]
        for (_p, sc, f), rs in aggregates.items()
        if sc == scenario and f == fn
        for r in rs
    }
    if len(suites) == 1:
        suite = suites.pop()
    elif not suites and spec_lookup is not None and (info := spec_lookup.find("", fn)):
        suite = info.get("suite", "")
    else:
        return None
    return {
        "platform": platform,
        "scenario": scenario,
        "suite": suite,
        "function": fn,
        "twister_id": f"{scenario}.{suite}.{fn}",
        "time": "",
        "status": "",
        "reason": "",
    }


class SpecLookup:
    """The spec's test cases, found by the (suite, function) of a twister result.

    ZTEST function names are not unique across suites (some 300 are reused in
    the Zephyr test tree), so the suite is part of the key. Each entry is a dict
    with at least `id`, `suite` and `test_function`.

    A result's function has ztest's ``test_`` prefix stripped, while the spec
    records the C name as written, so both spellings are tried. When the
    result's suite has no such case, the bare function name is used instead —
    but only if exactly one case carries it. `candidates()` returns every
    match, so an ambiguous one (several suites, or one (suite, function) pair
    documented in several test modules) is visible to the caller; `find()`
    returns a case only when there is exactly one.
    """

    def __init__(self, entries=()):
        self._by_key = {}
        self._by_name = {}
        for info in entries:
            fn = info["test_function"]
            self._by_key.setdefault((info.get("suite", ""), fn), []).append(info)
            self._by_name.setdefault(fn, []).append(info)

    def candidates(self, suite, fn):
        names = (fn, "test_" + fn)
        for name in names:
            if (suite, name) in self._by_key:
                return self._by_key[(suite, name)]
        for name in names:
            if name in self._by_name:
                return self._by_name[name]
        return []

    def find(self, suite, fn):
        hits = self.candidates(suite, fn)
        return hits[0] if len(hits) == 1 else None


def load_spec_lookup(json_path, need_names=None):
    """Read spec needs.json; return a SpecLookup of its test cases.

    `need_names` is the same role->name mapping `rst_builders.py` emitters
    take (`testmodule_need_types`/`testmodule_need_links`, merged by the
    caller) — the "case" role's need type and the "verifies" role's link
    name are both consumer-configurable (step 26), and this lookup must
    filter/read by whatever names the consumer's spec needs actually carry,
    not the engine's own defaults. Passing nothing preserves the original
    literal behaviour, which is what the unchanged unit tests pin.
    """
    with open(json_path) as f:
        data = json.load(f)
    versions = data.get("versions", {})
    if not versions:
        raise RuntimeError(f"testreport: no versions key in {json_path}")
    current = data.get("current_version") or next(iter(versions))
    needs = versions.get(current, {}).get("needs", {})
    case_type = _need_name(need_names, "case")
    verifies_link = _need_name(need_names, "verifies")
    return SpecLookup(
        {
            "id": need_id,
            "test_function": need["test_function"],
            "test_module": need.get("test_module", ""),
            "suite": need.get("suite", ""),
            "suite_title": need.get("suite_title", ""),
            "req_ids": need.get(verifies_link, []),
            "depends_on": _conditions(need.get("depends_on")),
        }
        for need_id, need in needs.items()
        if need.get("type") == case_type and need.get("test_function")
    )


def _conditions(value):
    """A need's ``depends_on`` as a list of conditions.

    zdocs writes it as a string with the conditions joined by ``"; "``; a
    consumer that declares it as an array gets a list from sphinx-needs.
    """
    if not value:
        return []
    if isinstance(value, str):
        return [c.strip() for c in value.split("; ") if c.strip()]
    return [str(c).strip() for c in value if str(c).strip()]


def _out_dir_segment(test_path):
    """Convert a twister.json ``path`` into the output-directory segment.

    `twister.json` reports each testsuite's ``path`` RELATIVE TO ZEPHYR_BASE
    (`twisterlib/testsuite.py`: ``source_dir_rel = os.path.relpath(suite_path,
    canonical_zephyr_base)``). A testsuite root outside the zephyr repository —
    which is where every downstream project keeps its own tests — therefore
    reports something like ``../acme/tests/doc-trace``, while the directory
    twister WROTE carries no such prefix.

    This is twister's own transformation, not a guess: `twisterlib/
    testinstance.py`'s ``TestInstance.__init__`` builds the output path from
    ``source_dir_rel.rsplit(os.pardir + os.path.sep, 1)[-1]`` — "keep only the
    part after the last ``../``" — under a comment saying exactly that. Joining
    the reported path verbatim resolves ABOVE the platform/toolchain directory
    and finds nothing, so every handler log is reported missing and the report
    page renders a "handler.log not found" line instead of the execution log.
    """
    return str(test_path).rsplit(os.pardir + os.sep, 1)[-1]


def find_handler_log(twister_out_dir, platform, toolchain, test_path, scenario_name):
    """Return the Path to handler.log for a (platform, scenario) run, or None."""
    platform_slug = platform.replace("/", "_")
    toolchain_slug = toolchain.replace("/", "_")
    run_dir = Path(twister_out_dir) / platform_slug / toolchain_slug
    base = run_dir / _out_dir_segment(test_path)
    exact = base / scenario_name / "handler.log"
    if exact.exists():
        return exact
    candidates = sorted(base.glob("*/handler.log")) if base.exists() else []
    if len(candidates) == 1:
        return candidates[0]
    for c in candidates:
        if scenario_name.startswith(c.parent.name):
            return c
    # `twister --detailed-test-id` takes the OTHER branch of the same `if` in
    # TestInstance.__init__ and omits the path segment entirely: the run
    # directory is <out>/<platform>/<toolchain>/<testsuite name>, where the name
    # is itself path-qualified. Tried last so the non-detailed layout above,
    # including its stale-directory fallbacks, keeps precedence.
    flat = run_dir / scenario_name / "handler.log"
    if flat.exists():
        return flat
    return None


def find_build_config(twister_out_dir, platform, toolchain, test_path, scenario_name):
    """Return the Path to the Kconfig ``.config`` of a (platform, scenario) build, or None.

    Twister keeps each build under the run directory `find_handler_log`
    describes, with the build's ``zephyr/.config`` in it. Unlike the log, the
    configuration is looked up only where twister puts it (the path layout,
    or the flat ``--detailed-test-id`` one): a ``.config`` of another scenario
    would answer for a build it did not come from.
    """
    run_dir = Path(twister_out_dir) / platform.replace("/", "_") / toolchain.replace("/", "_")
    for base in (run_dir / _out_dir_segment(test_path) / scenario_name, run_dir / scenario_name):
        config = base / "zephyr" / ".config"
        if config.is_file():
            return config
    return None


_KCONFIG_SET = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=")


def read_kconfig(path):
    """The Kconfig symbols a ``.config`` sets, as a set of names.

    A symbol is set when it has a value (``=y``, ``=m``, a number, a string);
    ``# CONFIG_X is not set`` and a symbol that is absent are not.
    """
    symbols = set()
    for line in Path(path).read_text(errors="replace").splitlines():
        if m := _KCONFIG_SET.match(line):
            symbols.add(m.group(1))
    return symbols


class UnparseableCondition(ValueError):
    """A ``depends_on`` condition outside the grammar `evaluate_condition` reads."""


_CONDITION_TOKEN = re.compile(r"\s*(&&|\|\||!|\(|\)|defined\b|CONFIG_[A-Za-z0-9_]+\b)")


def _tokens(condition):
    tokens, pos = [], 0
    text = condition.strip()
    while pos < len(text):
        m = _CONDITION_TOKEN.match(text, pos)
        if not m:
            raise UnparseableCondition(condition)
        tokens.append(m.group(1))
        pos = m.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return tokens


def evaluate_condition(condition, symbols):
    """Whether Kconfig ``condition`` holds for the set ``symbols`` (`read_kconfig`).

    The grammar: ``CONFIG_X`` and ``defined(CONFIG_X)`` (or ``defined CONFIG_X``)
    are true iff the symbol is set; ``!``, ``&&``, ``||`` (in C's precedence)
    and parentheses combine them. Anything else — another macro,
    ``IS_ENABLED()``, a comparison, a number — raises `UnparseableCondition`:
    its value in the build is not known from ``.config`` alone.
    """
    tokens = _tokens(condition)
    if not tokens:
        raise UnparseableCondition(condition)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take(expected=None):
        nonlocal pos
        tok = peek()
        if tok is None or (expected is not None and tok != expected):
            raise UnparseableCondition(condition)
        pos += 1
        return tok

    def primary():
        tok = take()
        if tok == "!":
            return not primary()
        if tok == "(":
            value = disjunction()
            take(")")
            return value
        if tok == "defined":
            if peek() == "(":
                take("(")
                name = take()
                take(")")
            else:
                name = take()
            if not name.startswith("CONFIG_"):
                raise UnparseableCondition(condition)
            return name in symbols
        if tok.startswith("CONFIG_"):
            return tok in symbols
        raise UnparseableCondition(condition)

    def conjunction():
        value = primary()
        while peek() == "&&":
            take()
            rhs = primary()
            value = value and rhs
        return value

    def disjunction():
        value = conjunction()
        while peek() == "||":
            take()
            rhs = conjunction()
            value = value or rhs
        return value

    result = disjunction()
    if pos != len(tokens):
        raise UnparseableCondition(condition)
    return result


#: `depends_met` values.
MET, NOT_MET, UNKNOWN = "yes", "no", "n/a"


def depends_met(conditions, symbols):
    """``(value, unparseable)`` for a test case's ``depends_on`` in one build.

    ``conditions`` are the case's conditions, all of which must hold (the
    ``"; "`` of ``depends_on`` is an and); ``symbols`` is the build's set
    Kconfig symbols, or None when its ``.config`` was not found. The value is
    ``"yes"`` or ``"no"``, or ``"n/a"`` when the case has no condition, the
    build has no ``.config``, or a condition is outside `evaluate_condition`'s
    grammar — then ``unparseable`` lists those conditions, and no value is
    guessed, even when another condition is false.
    """
    conditions = [c for c in (conditions or []) if c]
    if not conditions or symbols is None:
        return UNKNOWN, []
    values, unparseable = [], []
    for condition in conditions:
        try:
            values.append(evaluate_condition(condition, symbols))
        except UnparseableCondition:
            unparseable.append(condition)
    if unparseable:
        return UNKNOWN, unparseable
    return (MET if all(values) else NOT_MET), []


#: `skip_class` values.
SKIP_CONFIG, SKIP_PLATFORM, SKIP_BUILD_ONLY, SKIP_UNEXPLAINED = (
    "config", "platform", "build-only", "unexplained",
)

#: ztest's own skip (``ztest_test_skip()``), as twister reports it.
_ZTEST_SKIP = "ztest skip"
#: A build twister did not run (``build_only``; twister.json: "Test was built only").
_BUILD_ONLY = re.compile(r"^(test was )?built only$", re.IGNORECASE)
#: The platform could not take the build: a memory region overflowed, or
#: twister filtered the platform out.
_PLATFORM = re.compile(r"\b(RAM|FLASH|ROM) overflow\b|\bplatform\b", re.IGNORECASE)


def _skip_reason(result):
    """The skip reason of a result; for a parameterized test, its values' common one."""
    values = result.get("values")
    if values:
        reasons = {v.get("reason", "") for v in values if v.get("status") == "skipped"}
        if len(reasons) == 1:
            return reasons.pop()
    return result.get("reason", "")


def skip_class(result, met):
    """The class of a skipped result (None for any other), given its `depends_met`.

    ``build-only``: twister built the test but did not run it. ``platform``:
    the platform could not take it (a memory region overflowed, or it was
    filtered by platform). ``config``: ztest skipped it and the case's
    ``depends_on`` is false in the build. ``unexplained``: anything else,
    including a ztest skip whose condition holds, cannot be evaluated, or is
    not recorded.
    """
    if result.get("status") != "skipped":
        return None
    reason = " ".join(_skip_reason(result).split())
    if _BUILD_ONLY.match(reason):
        return SKIP_BUILD_ONLY
    if _PLATFORM.search(reason):
        return SKIP_PLATFORM
    if reason == _ZTEST_SKIP and met == NOT_MET:
        return SKIP_CONFIG
    return SKIP_UNEXPLAINED


def load_twister_meta(json_path):
    """Load and validate twister.json; return the dict."""
    with open(json_path) as f:
        data = json.load(f)
    if "environment" not in data:
        raise RuntimeError(f"load_twister_meta: missing 'environment' key in {json_path}")
    if "testsuites" not in data:
        raise RuntimeError(f"load_twister_meta: missing 'testsuites' key in {json_path}")
    return data
