# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Twister output parsing — no Sphinx dependency."""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

# `_need_name` resolves an engine ROLE ("case", "verifies", ...) to a
# consumer-configured NAME (zdocs step 26, zdocs-design-twister.md §12).
# `rst_builders.py` carries the same "no Sphinx, no app.config" rule this
# module follows — the mapping is passed in by the caller, never read from
# config here — so importing its pure helper does not violate that rule.
from rst_builders import _need_name

__all__ = [
    "parse_twister_results",
    "normalise_test_path",
    "scenario_selected",
    "testsuite_paths",
    "SpecLookup",
    "load_spec_lookup",
    "find_handler_log",
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
            suffix = name[len(scenario) + 1 :] if name.startswith(scenario + ".") else name
            parts = suffix.rsplit(".", 1)
            suite = parts[0] if len(parts) == 2 else ""
            function = parts[-1]
            if function.startswith("test_"):
                function = function[5:]
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
            results.append(
                {
                    "platform": platform,
                    "scenario": scenario,
                    "suite": suite,
                    "function": function,
                    "twister_id": name,
                    "time": tc.get("time", ""),
                    "status": status,
                    "reason": reason,
                }
            )
    return results


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
        }
        for need_id, need in needs.items()
        if need.get("type") == case_type and need.get("test_function")
    )


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


def load_twister_meta(json_path):
    """Load and validate twister.json; return the dict."""
    with open(json_path) as f:
        data = json.load(f)
    if "environment" not in data:
        raise RuntimeError(f"load_twister_meta: missing 'environment' key in {json_path}")
    if "testsuites" not in data:
        raise RuntimeError(f"load_twister_meta: missing 'testsuites' key in {json_path}")
    return data
