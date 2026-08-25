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
    "load_spec_lookup",
    "find_handler_log",
    "load_twister_meta",
]


def _elem_text(elem):
    """Collapse all text nodes in elem into a single whitespace-normalised string."""
    if elem is None:
        return ""
    return " ".join("".join(elem.itertext()).split())


def parse_twister_results(xml_path, module_filter=None, exact=False):
    """Parse twister_report.xml into a list of result dicts.

    The 'function' field has any leading 'test_' prefix stripped so it matches
    the keys used in spec_lookup.
    """
    root = ET.parse(xml_path).getroot()
    results = []
    for ts in root.findall("testsuite"):
        platform = ts.get("name", "")
        for tc in ts.findall("testcase"):
            classname = tc.get("classname", "")
            if module_filter:
                if exact:
                    if classname != module_filter:
                        continue
                elif not (classname == module_filter or classname.startswith(module_filter + ".")):
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


def load_spec_lookup(json_path, need_names=None):
    """Read spec needs.json; return {test_function: {id, test_module, suite, req_ids}}.

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
    lookup = {}
    for need_id, need in needs.items():
        if need.get("type") != case_type:
            continue
        fn = need.get("test_function", "")
        if fn:
            lookup[fn] = {
                "id": need_id,
                "test_module": need.get("test_module", ""),
                "suite": need.get("suite", ""),
                "suite_title": need.get("suite_title", ""),
                "req_ids": need.get(verifies_link, []),
            }
    return lookup


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
