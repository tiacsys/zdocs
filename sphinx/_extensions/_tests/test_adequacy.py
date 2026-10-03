# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Coverage adequacy: the oracle fixtures (Phase 4 order 002, part 1).

Each case has a verdict that is known in advance. The fixture is a git
repository with a small kernel tree, a twister.json, a test_matrix.json and the
needs of the spec (test cases, implementation needs). The test builds it in
``tmp_path`` because a nested repository cannot live in the engine's own tree.

Requirements, one per verdict and one per body form:

========== ================== ===================================== ============
Requirement Satisfied by       Verified by (what its tests cover)    Verdict
========== ================== ===================================== ============
R-VRFY     k_obj_init         TSPEC-1: the z_vrfy body only         true
R-IMPL     k_impl_only        TSPEC-2: the z_impl body              true
R-DEF      k_plain            TSPEC-3: the plain definition         true
R-INLINE   k_inline           TSPEC-4: the header static inline     true
R-MACRO    k_macro            TSPEC-3                               unresolved
R-PARTIAL  k_plain, k_inline  TSPEC-3: k_plain only                 partial
R-BROKEN   k_plain            TSPEC-5: none of it (TSPEC-3 does)    broken
R-UNATTR   k_boot             TSPEC-5 (no test covers k_boot)       unattributed
R-NOIMPL   —                  TSPEC-5                               no-impl
R-NOCOV    k_plain            TSPEC-6: ran, no matrix entry         no-cov
R-PREFIX   k_plain            TSPEC-9 (scenario demo, test_hit)     broken
R-PARAM    k_plain            TSPEC-10, two parameter values        true
R-NOTRUN   k_plain            TSPEC-7: not in the run               not assessed
========== ================== ===================================== ============

R-PREFIX is the prefix trap: TSPEC-8 is ``test_hit`` in scenario ``demo.usage``
and covers k_plain; its key ``demo_usage_test_hit`` starts with the slug of
scenario ``demo``. A reader that parses keys by prefix can give that coverage
to TSPEC-9. Keys built from (scenario, function) do not.
"""

import json
import subprocess
from pathlib import Path

import adequacy as A
import pytest
import test_coverage as tc
from rst_builders import _DEFAULT_NEED_NAMES

OBJ_C = """\
#include <zephyr/kernel.h>

int z_impl_k_obj_init(struct k_obj *o)
{
	o->x = 0;
	return 0;
}

static inline int z_vrfy_k_obj_init(struct k_obj *o)
{
	K_OOPS(o == NULL);
	return z_impl_k_obj_init(o);
}

int z_impl_k_impl_only(int v)
{
	return v + 1;
}
"""

PLAIN_C = """\
void k_plain(void)
{
	do_something();
}

void k_boot(void)
{
	early_init();
}
"""

# A direct child of include/zephyr/sys/: `sys/**/*.h` must find it.
INLINE_H = """\
static inline int k_inline(int x)
{
	return x * 2;
}
"""

KERNEL_H = """\
int k_obj_init(struct k_obj *o);
#define k_macro(x) k_plain()
"""


def _lines(text, first, last):
    """The 1-based line numbers of ``first`` .. ``last`` (by content) in ``text``."""
    rows = text.split("\n")
    a = next(i for i, r in enumerate(rows) if first in r) + 1
    b = next(i for i, r in enumerate(rows) if i >= a and last in r) + 1
    return a, b


# Line numbers at the commit.
VRFY = _lines(OBJ_C, "z_vrfy_k_obj_init", "}")
IMPL = _lines(OBJ_C, "int z_impl_k_obj_init", "}")
IMPL_ONLY = _lines(OBJ_C, "z_impl_k_impl_only", "}")
PLAIN = _lines(PLAIN_C, "void k_plain", "}")
BOOT = _lines(PLAIN_C, "void k_boot", "}")
INLINE = _lines(INLINE_H, "k_inline", "}")

CASES = {  # id: (suite, C function, scenario or None, verifies)
    "TSPEC-1": ("s1", "test_obj_init", "demo", ["R-VRFY"]),
    "TSPEC-2": ("s1", "test_impl_only", "demo", ["R-IMPL"]),
    "TSPEC-3": ("s1", "test_plain", "demo", ["R-DEF", "R-MACRO", "R-PARTIAL"]),
    "TSPEC-4": ("s1", "test_inline", "demo", ["R-INLINE"]),
    "TSPEC-5": ("s1", "test_other", "demo", ["R-BROKEN", "R-UNATTR", "R-NOIMPL"]),
    "TSPEC-6": ("s1", "test_nocov", "demo", ["R-NOCOV"]),
    "TSPEC-7": ("s1", "test_notrun", None, ["R-NOTRUN"]),
    "TSPEC-8": ("s2", "test_hit", "demo.usage", []),
    "TSPEC-9": ("s1", "test_hit", "demo", ["R-PREFIX"]),
    "TSPEC-10": ("s1", "test_param_case", "demo", ["R-PARAM"]),
}
SATISFIES = {
    "k_obj_init": ["R-VRFY"],
    "k_impl_only": ["R-IMPL"],
    "k_plain": ["R-DEF", "R-PARTIAL", "R-BROKEN", "R-NOCOV", "R-PREFIX", "R-PARAM", "R-NOTRUN"],
    "k_inline": ["R-INLINE", "R-PARTIAL"],
    "k_macro": ["R-MACRO"],
    "k_boot": ["R-UNATTR"],
}
REQS = sorted({r for c in CASES.values() for r in c[3]})

EXPECTED = {
    "R-VRFY": "true",
    "R-IMPL": "true",
    "R-DEF": "true",
    "R-INLINE": "true",
    "R-MACRO": "unresolved",
    "R-PARTIAL": "partial",
    "R-BROKEN": "broken",
    "R-UNATTR": "unattributed",
    "R-NOIMPL": "no-impl",
    "R-NOCOV": "no-cov",
    "R-PREFIX": "broken",
    "R-PARAM": "true",
}


def _span(ab, pick=None):
    a, b = ab
    return list(range(a, b + 1)) if pick is None else [a + i for i in pick]


def _matrix():
    """by_test for the fixture: per key, the lines it covers."""
    return {
        "demo_test_obj_init": {"kernel/obj.c": _span(VRFY, [0, 1, 2])},
        "demo_test_impl_only": {"kernel/obj.c": _span(IMPL_ONLY)},
        "demo_test_plain": {"kernel/plain.c": _span(PLAIN)},
        "demo_test_inline": {"include/zephyr/sys/k_inline.h": _span(INLINE)},
        # Covers something, but none of the bodies.
        "demo_test_other": {"kernel/obj.c": [1]},
        "demo_usage_test_hit": {"kernel/plain.c": _span(PLAIN, [0, 2])},
        "demo_test_hit": {"kernel/obj.c": [1]},
        "demo_test_param_case": {"kernel/plain.c": _span(PLAIN, [2])},
        # A test outside the tree's filter is dropped.
        "demo_test_plain_lib": {"../modules/x.c": [1]},
    }


def _write_matrix(path, by_test):
    by_line = {}
    for key, files in by_test.items():
        for f, lines in files.items():
            for ln in lines:
                by_line.setdefault(f, {}).setdefault(str(ln), []).append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"by_test": by_test, "by_line": by_line}))


def _twister():
    suites = {}
    for cid, (suite, fn, scenario, _) in CASES.items():
        if scenario is None:
            continue
        ts = suites.setdefault(scenario, {"name": scenario, "platform": "demo_board",
                                          "path": "tests/demo", "testcases": []})
        bare = fn[len("test_"):]
        if cid == "TSPEC-10":
            for n in (0, 1):
                ts["testcases"].append({"identifier": f"{scenario}.{bare}[cases/{n}]",
                                        "status": "passed"})
            continue
        status = "failed" if cid == "TSPEC-5" else "passed"
        ts["testcases"].append({"identifier": f"{scenario}.{suite}.{bare}", "status": status})
    return {"environment": {"zephyr_version": "v1.0.0-1-gdeadbee"},
            "testsuites": list(suites.values())}


def _needs():
    needs = {}
    for cid, (suite, fn, _, verifies) in CASES.items():
        needs[cid] = {"id": cid, "type": "test_case", "title": fn, "test_function": fn,
                      "suite": suite, "test_module": "tests/demo", "verifies": verifies}
    for sym, reqs in SATISFIES.items():
        needs[f"IMPL-{sym}"] = {"id": f"IMPL-{sym}", "type": "impl", "title": sym,
                                "satisfies": reqs}
    for r in REQS:
        needs[r] = {"id": r, "type": "req", "title": r}
    return {"current_version": "1.0", "versions": {"1.0": {"needs": needs}}}


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def tree(tmp_path):
    """``(root, sha, run_dir, needs_json)``: a committed tree, then a working tree 20 lines off."""
    root = tmp_path / "zephyr"
    files = {
        "kernel/obj.c": OBJ_C,
        "kernel/plain.c": PLAIN_C,
        "include/zephyr/sys/k_inline.h": INLINE_H,
        "include/zephyr/kernel.h": KERNEL_H,
        "lib/unrelated.c": "void k_plain(void)\n{\n}\n",  # not a searched path
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "run")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                         capture_output=True, text=True).stdout.strip()
    # The working tree moves on after the run: every body 20 lines further down.
    for rel in ("kernel/obj.c", "kernel/plain.c", "include/zephyr/sys/k_inline.h"):
        (root / rel).write_text("\n" * 20 + files[rel])

    run_dir = tmp_path / "cov-run"
    run_dir.mkdir()
    (run_dir / "twister.json").write_text(json.dumps(_twister()))
    (run_dir / "zephyr.sha").write_text(sha + "\n")
    _write_matrix(run_dir / "coverage" / "test_matrix.json", _matrix())
    needs_json = tmp_path / "needs.json"
    needs_json.write_text(json.dumps(_needs()))
    return root, sha, run_dir, needs_json


def _assess(tree, ref="commit", name=None):
    root, sha, run_dir, needs_json = tree
    spec, verified_by, satisfied_by, ids = A.collect_links([needs_json])
    run, inputs = A.load_coverage_run(run_dir, spec, root, name=name)
    source = A.Source(root, run.sha if ref == "commit" else None)
    results, impl_loc = A.assess(run, verified_by, satisfied_by, source, ids)
    return run, results, impl_loc, inputs


# ---------------------------------------------------------------------------
# One fixture per verdict and per body form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("req, verdict", sorted(EXPECTED.items()))
def test_verdict(tree, req, verdict):
    _, results, _, _ = _assess(tree)
    assert results[req]["verdict"] == verdict


def test_a_requirement_whose_tests_did_not_run_is_not_assessed(tree):
    _, results, _, _ = _assess(tree)
    assert set(results) == set(EXPECTED)
    assert "R-NOTRUN" not in results


def test_body_forms(tree):
    _, _, loc, _ = _assess(tree)
    assert [(b["variant"], b["a"], b["b"]) for b in loc["k_obj_init"]] == [
        ("impl", *IMPL), ("vrfy", *VRFY),
    ]
    assert [(b["variant"], b["file"]) for b in loc["k_impl_only"]] == [("impl", "kernel/obj.c")]
    # lib/ is not searched: one plain definition only.
    assert [(b["variant"], b["file"], b["a"], b["b"]) for b in loc["k_plain"]] == [
        ("def", "kernel/plain.c", *PLAIN),
    ]
    assert [(b["variant"], b["file"]) for b in loc["k_inline"]] == [
        ("inline", "include/zephyr/sys/k_inline.h"),
    ]
    # A macro and a prototype have no body.
    assert "k_macro" not in loc


def test_a_user_mode_test_reaches_only_the_verifier(tree):
    _, results, _, _ = _assess(tree)
    by_variant = {d["variant"]: d for d in results["R-VRFY"]["impls"]}
    assert by_variant["impl"]["own"] == 0
    assert by_variant["vrfy"]["own_tests"] == {"TSPEC-1": _span(VRFY, [0, 1, 2])}


def test_partial_and_broken_name_the_tests_that_do_reach_the_code(tree):
    _, results, _, _ = _assess(tree)
    inline = next(d for d in results["R-PARTIAL"]["impls"] if d["sym"] == "k_inline")
    assert (inline["own"], inline["any"]) == (0, len(_span(INLINE)))
    assert set(inline["other_tests"]) == {"demo_test_inline"}
    broken = results["R-BROKEN"]["impls"][0]
    assert set(broken["other_tests"]) == {
        "demo_test_plain", "demo_usage_test_hit", "demo_test_param_case",
    }


def test_keys_are_built_from_scenario_and_function(tree):
    run, results, _, _ = _assess(tree)
    assert run.cases["TSPEC-8"]["keys"] == ["demo_usage_test_hit"]
    assert run.cases["TSPEC-9"]["keys"] == ["demo_test_hit"]
    assert results["R-PREFIX"]["impls"][0]["own"] == 0


def test_parameter_values_share_one_key(tree):
    run, results, _, _ = _assess(tree)
    assert run.cases["TSPEC-10"] == {"statuses": ["passed", "passed"],
                                     "keys": ["demo_test_param_case"]}
    assert results["R-PARAM"]["evidence"] == "passing"


def test_evidence(tree):
    _, results, _, _ = _assess(tree)
    assert results["R-BROKEN"]["evidence"] == "failing"
    assert results["R-DEF"]["evidence"] == "passing"
    run = A.CoverageRun("r", None, {}, {}, {}, {"C": {"statuses": ["skipped"], "keys": []}}, [])
    assert A.evidence([], run) == "untested"
    assert A.evidence(["X"], run) == "no-run"
    assert A.evidence(["C"], run) == "skipped"


def test_matrix_keeps_the_tree_files_only(tree):
    by_test, by_line = A.load_matrix(tree[2] / "coverage" / "test_matrix.json")
    assert by_test["demo_test_plain_lib"] == {}
    assert "../modules/x.c" not in by_line


# ---------------------------------------------------------------------------
# Sources at the run commit
# ---------------------------------------------------------------------------


def test_sources_come_from_the_run_commit(tree):
    root, sha, _, _ = tree
    run, results, loc, inputs = _assess(tree)
    assert run.sha == sha
    assert loc["k_plain"][0]["a"] == PLAIN[0]
    assert {r: v["verdict"] for r, v in results.items()} == EXPECTED
    assert [p.name for p in inputs] == ["twister.json", "test_matrix.json", "zephyr.sha"]


def test_the_working_tree_gives_other_lines_and_other_verdicts(tree):
    # The control: the same run read against the moved working tree.
    _, results, loc, _ = _assess(tree, ref="working tree")
    assert loc["k_plain"][0]["a"] == PLAIN[0] + 20
    assert results["R-DEF"]["verdict"] == "unattributed"


def test_run_commit_falls_back_to_zephyr_version(tree, tmp_path):
    root, sha, run_dir, _ = tree
    (run_dir / "zephyr.sha").unlink()
    assert A.run_commit(run_dir, {"zephyr_version": f"v1.0.0-3-g{sha[:12]}"}, root) == sha
    assert A.run_commit(run_dir, {"zephyr_version": "v1.0.0-3-gdeadbee"}, root) is None
    (run_dir / "zephyr.sha").write_text("0" * 40)
    assert A.run_commit(run_dir, {}, root) is None


def test_run_name_is_the_tag_on_the_commit_else_the_directory(tree):
    root, sha, run_dir, _ = tree
    assert A.run_name(run_dir, sha, root) == "cov-run"
    _git(root, "tag", "z-run")
    _git(root, "tag", "a.run/1")
    assert A.run_name(run_dir, sha, root) == "a-run-1"
    run, _, _, _ = _assess(tree, name="given")
    assert run.name == "given"


def test_glob_patterns_take_zero_or_more_directories():
    rx = A._glob_regex("include/zephyr/sys/**/*.h")
    assert rx.match("include/zephyr/sys/slist.h")
    assert rx.match("include/zephyr/sys/a/b/x.h")
    assert not rx.match("include/zephyr/sysx.h")
    assert not A._glob_regex("kernel/*.c").match("kernel/sub/x.c")


def test_matrix_key():
    assert A.matrix_key("kernel.semaphore", "test_sem_init_validity") == (
        "kernel_semaphore_test_sem_init_validity"
    )
    assert A.matrix_key("kernel.lifo.usage", "test_x", suite="s") == "kernel_lifo_usage_s_test_x"


def test_line_ranges():
    assert A.line_ranges([45, 51, 57, 58, 62]) == "45, 51, 57-58, 62"
    assert A.line_ranges([]) == ""


# ---------------------------------------------------------------------------
# The directive
# ---------------------------------------------------------------------------


def test_adequacy_rst_sets_the_declared_fields_under_the_consumers_names(tree):
    run, results, _, _ = _assess(tree)
    names = {**_DEFAULT_NEED_NAMES, "adequacy": "judgement", "assesses": "judges",
             "verdict": "outcome"}
    rst = "\n".join(tc.build_adequacy_rst("R-VRFY", results["R-VRFY"], run, names, {"verdict"}))
    assert ".. judgement:: Adequacy of R-VRFY" in rst
    assert "   :id: ADQ-cov-run/R-VRFY" in rst
    assert "   :judges: R-VRFY" in rst
    assert "   :outcome: true" in rst
    assert ":evidence:" not in rst  # not declared
    assert ":layout:" not in rst
    with_layout = tc.build_adequacy_rst("R-VRFY", results["R-VRFY"], run, names, (), "Q", "adq")
    assert "   :layout: adq" in with_layout and "   :id: Q-cov-run/R-VRFY" in with_layout
    assert f"own :need:`TSPEC-1`: lines {VRFY[0]}-{VRFY[0] + 2}" in rst


_CONF = """\
import sys
sys.path.insert(0, {ext!r})
extensions = ["sphinx_needs", "test_module"]
master_doc = "index"
exclude_patterns = ["_build"]
needs_types = [
    dict(directive=d, title=d, prefix=d.upper() + "_", color="#FFF", style="node")
    for d in ("adequacy", "test_case", "impl", "req")
]
_s = {{"schema": {{"type": "string"}}, "nullable": True}}
needs_fields = {{"verdict": _s, "evidence": _s, "coverage_run": _s,
                "judged_symbols": _s, "symbol_hits": _s,
                "test_function": _s, "suite": _s, "test_module": _s}}
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"
needs_links = {{
    "assesses": {{"incoming": "assessed by", "outgoing": "assesses"}},
    "verifies": {{"incoming": "verified by", "outgoing": "verifies"}},
    "satisfies": {{"incoming": "satisfied by", "outgoing": "satisfies"}},
}}
needs_external_needs = [{{"json_path": {needs!r}, "base_url": "http://localhost/",
                         "version": "1.0"}}]
coverage_output_dir = {run!r}
testmodule_root = {root!r}
needs_build_json = True
suppress_warnings = ["config.cache"]
"""


def test_directive_emits_one_adequacy_need_per_requirement(tree, make_app, tmp_path):
    root, _, run_dir, needs_json = tree
    src = tmp_path / "doc"
    src.mkdir()
    (src / "conf.py").write_text(_CONF.format(
        ext=str(Path(A.__file__).parent), needs=str(needs_json), run=str(run_dir),
        root=str(root),
    ))
    (src / "index.rst").write_text("Adequacy\n########\n\n.. testcoverage::\n")
    app = make_app("html", srcdir=src)
    app.build()
    data = json.loads((Path(app.outdir) / "needs.json").read_text())
    needs = next(iter(data["versions"].values()))["needs"]
    adq = {n["id"]: n for n in needs.values() if n["type"] == "adequacy"}
    assert {i.split("/", 1)[1]: n["verdict"] for i, n in adq.items()} == EXPECTED
    five = adq["ADQ-cov-run/R-PARTIAL"]
    assert five["assesses"] == ["R-PARTIAL"]
    assert five["judged_symbols"] == "k_inline; k_plain"
    assert five["coverage_run"] == "cov-run"
    log = app._warning.getvalue()
    assert "WARNING" not in log, log
    html = (Path(app.outdir) / "index.html").read_text()
    assert "Verdict broken" in html and 'id="ADQ-cov-run/R-VRFY"' in html


def test_directive_without_a_run_says_so(make_app, tmp_path):
    src = tmp_path / "doc"
    src.mkdir()
    (src / "conf.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(Path(A.__file__).parent)!r})\n"
        "extensions = ['sphinx_needs', 'test_module']\n"
    )
    (src / "index.rst").write_text("X\n#\n\n.. testcoverage::\n")
    app = make_app("html", srcdir=src)
    app.build()
    assert "no coverage run configured" in (Path(app.outdir) / "index.html").read_text()
    assert "WARNING" not in app._warning.getvalue()
