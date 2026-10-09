# Copyright (c) 2026 inovex GmbH
# Copyright The Zephyr Project Contributors
#
# SPDX-License-Identifier: Apache-2.0

"""Coverage adequacy: do the own tests of a requirement run the code that satisfies it.

This module has no Sphinx dependency. A ``verifies`` link and a ``satisfies``
link are claims. A per-test coverage run (``west twister --coverage-per-test``)
checks them against execution. For each requirement, the module finds the
bodies of the satisfying symbols in the sources of the run commit. Then it
compares their lines with the lines that the own verifying tests covered.

The port starts from ``doc/_scripts/traceability_app.py`` by Anas (zephyr
collab-safety 0cc56a35003). `Source`, `resolve_impl_symbols` and the verdicts
(`evidence`, `adequacy`) are close to the original. The keys are the keys of
zdocs:

* A requirement gets its verifying test cases through the ``verifies`` link
  of the case needs.
* A requirement gets its satisfying symbols through the ``satisfies`` link of
  the implementation needs (``<TYPE>-<symbol>``, `rst_builders.symbol_need_id`).
* A test case gets its matrix keys through the ``twister.json`` of the run.
  Each twister case goes to its spec case by (suite, function), as a test
  result does. The key is built from (scenario, C function name), as twister
  writes it. The module does not parse keys, because scenario names are
  prefixes of other scenario names (``kernel.lifo``, ``kernel.lifo.usage``).

Two changes from the original correct errors:

* File patterns use glob rules in both modes: ``**/`` is zero or more
  directories, and ``*`` stays in one directory. The original used
  ``fnmatch`` on the ``git ls-tree`` output. There, ``**/`` needs at least one
  directory, so ``include/zephyr/sys/**/*.h`` did not find ``sys/slist.h``.
* The run commit comes from ``zephyr.sha`` beside the twister output first.
  Then it comes from ``environment.zephyr_version``.

One change from the original is a setting: the files that hold the bodies.
`IMPL_PATTERNS` is the set of the original and the default. A consumer gives
its own set to `assess` (``testcoverage_impl_files`` in Sphinx).

The verdicts are the verdicts of the original:

``true``
    Every symbol that coverage can judge has a body that the own tests ran.
``partial``
    Some of these symbols have such a body, others do not.
``broken``
    Other tests of the run reach the code. The own tests never do.
``unattributed``
    No test of the run covers any body, so coverage cannot judge the link.
``unresolved``
    Satisfying symbols exist, but none maps to a body (a macro).
``no-impl``
    No symbol satisfies the requirement.
``no-cov``
    The verifying tests have no coverage data in this run.
"""

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from rst_builders import _need_name, symbol_need_id
from twister_reader import SpecLookup, split_case_name

__all__ = [
    "VERDICTS",
    "matrix_key",
    "IMPL_PATTERNS",
    "keep_prefixes",
    "load_matrix",
    "run_commit",
    "run_name",
    "Source",
    "resolve_impl_symbols",
    "CoverageRun",
    "load_coverage_run",
    "collect_links",
    "evidence",
    "adequacy",
    "assess",
    "line_ranges",
]

#: In the order a report lists them: the findings first.
VERDICTS = ("broken", "partial", "unattributed", "unresolved", "no-cov", "no-impl", "true")

# Test-result rollup precedence (worst wins for reporting a test's state).
_FAIL = {"failed", "error"}
_SKIP = {"skipped", "blocked", "not run", "filtered"}

#: Where the original looks for bodies. The default of ``impl_files``.
IMPL_PATTERNS = (
    "kernel/*.c",
    "kernel/**/*.c",
    "include/zephyr/kernel.h",
    "include/zephyr/kernel/**/*.h",
    "include/zephyr/sys/**/*.h",
)

#: Files the matrix is read for (the original's ``keep``). `keep_prefixes`
#: adds the fixed start of each pattern of ``impl_files``.
_KEEP = ("kernel/", "include/", "lib/", "tests/")

#: A body ends at the first column-0 ``}`` within this many lines.
_MAX_BODY = 500


def _slug(name):
    """A coverage test name as twister writes it (coverage.py, ``TN:``)."""
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def matrix_key(scenario, function, suite=None):
    """The ``test_matrix.json`` key of C function ``function`` in ``scenario``.

    Twister names a per-test tracefile ``<scenario>.<test>``. If two suites of
    one scenario have the same test name, it uses ``<scenario>.<suite>.<test>``.
    The key is that name, with ``_`` for each character outside
    ``[A-Za-z0-9_]``. Give ``suite`` for the second form. ``function`` keeps
    its ``test_`` prefix.
    """
    name = f"{scenario}.{suite}.{function}" if suite else f"{scenario}.{function}"
    return _slug(name)


# --- test_matrix.json ---------------------------------------------------------


def keep_prefixes(impl_files=IMPL_PATTERNS):
    """`_KEEP` and the fixed start of each pattern, up to its last ``/`` before a wildcard.

    A body file must be in the matrix that `load_matrix` keeps, so that its
    lines can count as covered. ``arch/**/*.c`` adds ``arch/``. A pattern with
    a wildcard in its first part adds nothing, so that the matrix does not keep
    files outside the tree (``../modules/...``).
    """
    out = list(_KEEP)
    for pat in impl_files:
        fixed = re.split(r"[*?]", pat, maxsplit=1)[0]
        if fixed != pat:
            fixed = fixed[: fixed.rfind("/") + 1]
        if fixed and not fixed.startswith(("/", "../")) and not fixed.startswith(tuple(out)):
            out.append(fixed)
    return tuple(out)


def load_matrix(matrix_path, keep=_KEEP):
    """``(by_test, by_line)`` of a ``test_matrix.json``, for the files under ``keep``.

    * ``by_test[key] = {file: set of covered lines}``
    * ``by_line[file] = {line (int): [keys]}``

    ``keep``: path prefixes (`_KEEP`, or `keep_prefixes` of the body files).
    """
    data = json.loads(Path(matrix_path).read_text())
    by_test = {}
    for key, files in data.get("by_test", {}).items():
        by_test[key] = {
            f: {int(x) for x in lines} for f, lines in files.items() if f.startswith(keep)
        }
    by_line = {
        f: {int(ln): list(keys) for ln, keys in lines.items()}
        for f, lines in data.get("by_line", {}).items()
        if f.startswith(keep)
    }
    return by_test, by_line


# --- the run's commit and name ------------------------------------------------


def _git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, errors="replace"
    )


def run_commit(run_dir, environment, root):
    """The commit that the run built, as a full sha in ``root``, or ``None``.

    The first source is ``zephyr.sha`` beside the twister output. The second
    source is the ``-g<hash>`` of ``environment.zephyr_version`` in twister.json.
    """
    candidates = []
    sha_file = Path(run_dir) / "zephyr.sha"
    if sha_file.is_file():
        candidates.append(sha_file.read_text().strip())
    m = re.search(r"-g([0-9a-f]{7,})$", (environment or {}).get("zephyr_version", "") or "")
    if m:
        candidates.append(m.group(1))
    for ref in candidates:
        if not ref:
            continue
        r = _git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
        if r.returncode == 0:
            return r.stdout.strip()
    return None


def run_name(run_dir, sha, root):
    """The name of the run: the first tag (sorted) on its commit.

    If the commit has no tag, the name is the name of the run directory. Each
    run of characters outside ``[A-Za-z0-9_-]`` becomes one ``-``.
    """
    name = ""
    if sha:
        r = _git(root, "tag", "--points-at", sha)
        tags = sorted(t for t in r.stdout.split() if t) if r.returncode == 0 else []
        name = tags[0] if tags else ""
    name = name or Path(run_dir).resolve().name
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")


# --- source access at the coverage build's commit -------------------------------


def _glob_regex(pattern):
    """A regex for a glob ``pattern``: ``**/`` is zero or more directories, ``*`` is in one."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


class Source:
    """Reads the files of the tree at the commit of the coverage run.

    Coverage line numbers are correct only for the sources of the build that
    made them. With ``ref`` (the run commit, `run_commit`), `read` uses
    ``git show <ref>:<path>``. The line ranges are then correct also after
    the working tree changes. Without ``ref``, `read` uses the working tree
    under ``root``, and the caller warns.
    """

    def __init__(self, root, ref=None):
        self.root = Path(root)
        self.ref = ref
        self._ls = None

    def describe(self):
        return self.ref or "working tree"

    def list(self, patterns):
        """The relative paths that match one of the glob patterns."""
        regexes = [_glob_regex(p) for p in patterns]
        if not self.ref:
            files = (
                p.relative_to(self.root).as_posix()
                for pat in patterns
                for p in self.root.glob(pat)
                if p.is_file()
            )
        else:
            if self._ls is None:
                r = _git(self.root, "ls-tree", "-r", "--name-only", self.ref)
                if r.returncode != 0:
                    raise RuntimeError(f"git ls-tree {self.ref} failed in {self.root}: {r.stderr}")
                self._ls = r.stdout.split("\n")
            files = self._ls
        return sorted({f for f in files if any(rx.match(f) for rx in regexes)})

    def read(self, rel):
        """The text of the file at the ref, or None."""
        if not self.ref:
            p = (self.root / rel).resolve()
            if not str(p).startswith(str(self.root.resolve())) or not p.is_file():
                return None
            return p.read_text(errors="replace")
        r = _git(self.root, "show", f"{self.ref}:{rel}")
        return r.stdout if r.returncode == 0 else None


# --- implementation symbol resolution -----------------------------------------

#: The identifier before the first ``(`` of a line. The pattern of the
#: original can match only this identifier: its ``[\w \t\*]*`` stops at ``(``.
_CALLEE = re.compile(r"[^(]*?\b(\w+)\s*\(")


def resolve_impl_symbols(source, symbols, impl_files=IMPL_PATTERNS):
    """The function bodies of the satisfying symbols (best effort).

    A system call has more than one body. ``z_impl_<sym>`` is the
    implementation in supervisor mode. ``z_vrfy_<sym>`` is the verifier that a
    ZTEST_USER test reaches instead. The verifier can do the operation itself
    and never call the z_impl body (z_vrfy_k_thread_create does this). The
    function collects all bodies. A test that runs one of them runs the
    implementation.

    A definition starts at column 0 (``static [ALWAYS_INLINE] inline`` is
    permitted), and its line does not end in ``;``. Its body ends at the first
    ``}`` in column 0, in 500 lines or less. In a header, only a ``static``
    line counts: other lines are prototypes or macros. So a macro has no body.
    A header is a ``.h`` file anywhere in the tree (``kernel/include/`` too).

    ``impl_files``: the glob patterns of the files to search (`IMPL_PATTERNS`).

    Returns {sym: [{"file", "a", "b", "variant"}, ...]}.
    """
    sources = {}
    for rel in source.list(impl_files):
        text = source.read(rel)
        if text is not None:
            sources[rel] = text.split("\n")

    # Candidate lines by the identifier before their first "(". The patterns
    # of a symbol then run on a small number of lines, not on each line of the
    # tree. The full pattern decides.
    candidates = defaultdict(list)
    for f, lines in sources.items():
        in_header = f.endswith(".h")
        for i, ln in enumerate(lines):
            if ln.rstrip().endswith(";"):
                continue
            # in headers only accept static-inline bodies (anything else
            # is a prototype or macro), in .c files anything definition-like
            if in_header and not ln.lstrip().startswith("static"):
                continue
            m = _CALLEE.match(ln)
            if m:
                candidates[m.group(1)].append((f, i))

    resolved = {}
    for sym in symbols:
        variants = [(f"z_impl_{sym}", "impl"), (f"z_vrfy_{sym}", "vrfy"), (sym, "def")]
        bodies = []
        for n, variant in variants:
            p = re.compile(
                r"^(static +(ALWAYS_INLINE +|__?always_inline +)?inline +)?"
                r"[A-Za-z_][\w \t\*]*\b" + re.escape(n) + r"\s*\("
            )
            for f, i in candidates.get(n, ()):
                lines = sources[f]
                if not p.match(lines[i]):
                    continue
                stop = min(i + _MAX_BODY, len(lines))
                end = next((j + 1 for j in range(i + 1, stop) if lines[j] == "}"), None)
                if end:
                    bodies.append({
                        "file": f, "a": i + 1, "b": end,
                        "variant": "inline" if f.endswith(".h") else variant,
                    })
        if bodies:
            # stable order: impl first, then vrfy, inline, plain definitions
            order = {"impl": 0, "vrfy": 1, "inline": 2, "def": 3}
            bodies.sort(key=lambda x: (order[x["variant"]], x["file"], x["a"]))
            resolved[sym] = bodies
    return resolved


# --- the coverage run ------------------------------------------------------------


class CoverageRun:
    """One per-test coverage run, joined to the test cases of the spec.

    * ``cases[case id] = {"statuses": [...], "keys": [matrix keys]}``, for each
      spec case that twister ran in this run.
    * ``case_of_key[key] = {case ids}``: the reverse map, for the question
      "which tests ran this line".
    * ``unmatched``: the twister cases with no unique spec case (sorted names).
    """

    def __init__(self, name, sha, environment, by_test, by_line, cases, unmatched):
        self.name = name
        self.sha = sha
        self.environment = environment
        self.by_test = by_test
        self.by_line = by_line
        self.cases = cases
        self.unmatched = unmatched
        self.case_of_key = defaultdict(set)
        for cid, c in cases.items():
            for k in c["keys"]:
                self.case_of_key[k].add(cid)


def join_cases(twister, spec_lookup, by_test):
    """``(cases, unmatched)`` for `CoverageRun`, from twister.json and the spec.

    The matrix key of a case comes from the scenario and the C function name
    of the spec (`matrix_key`). The form with the suite is used only if the
    plain key is not in the matrix and is not the plain key of another case.
    The values of a parameterized test share one key, because the per-test
    dump has no value in its tag.
    """
    ran = []  # (scenario, suite, fn, status, name)
    for ts in twister.get("testsuites", []):
        scenario = ts.get("name", "")
        for tc in ts.get("testcases", []):
            name = tc.get("identifier", "")
            suite, fn, _ = split_case_name(name, scenario)
            ran.append((scenario, suite, fn, (tc.get("status") or "").lower(), name))

    cases, unmatched, plain_owned = {}, set(), set()
    joined = []
    for scenario, suite, fn, status, name in ran:
        info = spec_lookup.find(suite, fn)
        if info is None:
            unmatched.add(name)
            continue
        joined.append((scenario, suite, info, status))
        plain_owned.add(matrix_key(scenario, info["test_function"]))
    for scenario, suite, info, status in joined:
        c = cases.setdefault(info["id"], {"statuses": [], "keys": []})
        c["statuses"].append(status)
        key = matrix_key(scenario, info["test_function"])
        if key not in by_test and suite:
            qualified = matrix_key(scenario, info["test_function"], suite)
            if qualified in by_test and qualified not in plain_owned:
                key = qualified
        if key in by_test and key not in c["keys"]:
            c["keys"].append(key)
    return cases, sorted(unmatched)


def load_coverage_run(run_dir, spec_lookup, root, name=None, impl_files=IMPL_PATTERNS):
    """Read a coverage run directory: twister.json, coverage/test_matrix.json, zephyr.sha.

    ``impl_files``: the body files of `resolve_impl_symbols`. The matrix keeps
    their lines (`keep_prefixes`).

    Returns ``(run, inputs)``: the `CoverageRun` and the files that it reads.
    """
    run_dir = Path(run_dir)
    twister_json = run_dir / "twister.json"
    matrix_json = run_dir / "coverage" / "test_matrix.json"
    inputs = [twister_json, matrix_json, run_dir / "zephyr.sha"]
    twister = json.loads(twister_json.read_text())
    by_test, by_line = load_matrix(matrix_json, keep_prefixes(impl_files))
    env = twister.get("environment", {})
    sha = run_commit(run_dir, env, root)
    cases, unmatched = join_cases(twister, spec_lookup, by_test)
    return (
        CoverageRun(name or run_name(run_dir, sha, root), sha, env, by_test, by_line, cases,
                    unmatched),
        inputs,
    )


# --- links from the needs -----------------------------------------------------------


def _needs_of(json_path):
    data = json.loads(Path(json_path).read_text())
    versions = data.get("versions", {})
    current = data.get("current_version") or next(iter(versions), None)
    return versions.get(current, {}).get("needs", {}) if current is not None else {}


def collect_links(json_paths, need_names=None):
    """``(spec_lookup, verified_by, satisfied_by, ids)`` from needs.json files.

    * ``spec_lookup``: a `SpecLookup` of the test cases (type role ``case``).
    * ``verified_by[req] = [case ids]``, through the ``verifies`` role.
    * ``satisfied_by[req] = [symbols]``: the implementation needs (type role
      ``implementation``, ids ``<TYPE>-<symbol>``), through ``satisfies``.
    * ``ids``: each need id in the files. A link target that is not a need
      gets no assessment.

    If several files export one need, it counts once.
    """
    case_type = _need_name(need_names, "case")
    impl_type = _need_name(need_names, "implementation")
    verifies = _need_name(need_names, "verifies")
    satisfies = _need_name(need_names, "satisfies")
    impl_prefix = symbol_need_id("", need_names)
    seen = {}
    for path in json_paths:
        for nid, need in _needs_of(path).items():
            seen.setdefault(nid, need)
    entries, verified_by, satisfied_by = [], defaultdict(list), defaultdict(list)
    for nid, need in seen.items():
        if need.get("type") == case_type and need.get("test_function"):
            entries.append({
                "id": nid,
                "test_function": need["test_function"],
                "test_module": need.get("test_module", ""),
                "suite": need.get("suite", ""),
            })
            for req in need.get(verifies, []) or []:
                verified_by[req].append(nid)
        elif need.get("type") == impl_type and nid.startswith(impl_prefix):
            for req in need.get(satisfies, []) or []:
                satisfied_by[req].append(nid[len(impl_prefix):])
    return SpecLookup(entries), dict(verified_by), dict(satisfied_by), set(seen)


# --- verdicts --------------------------------------------------------------------------


def _rollup(statuses):
    npass = sum(s == "passed" for s in statuses)
    nfail = sum(s in _FAIL for s in statuses)
    nskip = sum(s in _SKIP for s in statuses)
    return ("failing" if nfail else
            "passing" if npass else
            "skipped" if nskip else "no-run")


def evidence(case_ids, run):
    """The state of the verifying cases: untested, no-run, failing, passing or skipped."""
    if not case_ids:
        return "untested"
    roll = [_rollup(run.cases[c]["statuses"]) for c in case_ids if c in run.cases]
    if not roll:
        return "no-run"
    if "failing" in roll:
        return "failing"
    if "passing" in roll:
        return "passing"
    return "skipped"


def adequacy(symbols, case_ids, run, impl_loc):
    """``{"verdict", "impls"}`` of a requirement from its ``symbols`` and ``case_ids``.

    ``impls`` has one entry for each symbol and body, with these keys:

    * ``sym`` and ``variant``.
    * ``file``, ``a`` and ``b``: ``None`` for a symbol with no body.
    * ``own``: the number of body lines that the own tests ran.
    * ``any``: the number of body lines that any test of the run ran.
    * ``own_tests``: ``{case id: [lines]}``.
    * ``other_tests``: ``{matrix key: [lines]}``, for the keys of other tests.
    """
    if not symbols:
        return {"verdict": "no-impl", "impls": []}
    own_keys = [k for c in case_ids if c in run.cases for k in run.cases[c]["keys"]]
    tests_with_cov = [c for c in case_ids if c in run.cases and run.cases[c]["keys"]]
    detail, resolved, adjudicable, own_hits = [], 0, 0, 0
    for sym in sorted(set(symbols)):
        bodies = impl_loc.get(sym)
        if not bodies:
            detail.append({"sym": sym, "variant": None, "file": None, "a": None, "b": None,
                           "own": 0, "any": 0, "own_tests": {}, "other_tests": {}})
            continue
        resolved += 1
        sym_hit = sym_seen = False
        for body in bodies:
            f, a, b = body["file"], body["a"], body["b"]
            fl = run.by_line.get(f, {})
            exec_lines = sorted(ln for ln in fl if a <= ln <= b)
            own, own_tests = set(), {}
            for c in tests_with_cov:
                hit = set()
                for k in run.cases[c]["keys"]:
                    hit.update(ln for ln in run.by_test[k].get(f, ()) if a <= ln <= b)
                if hit:
                    own_tests[c] = sorted(hit)
                own |= hit
            other_tests = defaultdict(set)
            for ln in exec_lines:
                for k in fl[ln]:
                    if k not in own_keys:
                        other_tests[k].add(ln)
            if own:
                sym_hit = True
            if exec_lines:
                sym_seen = True
            detail.append({"sym": sym, "variant": body["variant"], "file": f, "a": a, "b": b,
                           "own": len(own), "any": len(exec_lines), "own_tests": own_tests,
                           "other_tests": {k: sorted(v) for k, v in sorted(other_tests.items())}})
        # If no test of the run covers the bodies of a symbol (boot-time
        # code, inlined code, code that the configuration removes), coverage
        # cannot judge it. It must not count as "broken".
        if sym_seen:
            adjudicable += 1
        if sym_hit:
            own_hits += 1
    if not resolved:
        verdict = "unresolved"
    elif not tests_with_cov:
        verdict = "no-cov"
    elif not adjudicable:
        verdict = "unattributed"
    elif own_hits == adjudicable:
        verdict = "true"
    elif own_hits:
        verdict = "partial"
    else:
        verdict = "broken"
    return {"verdict": verdict, "impls": detail}


def assess(run, verified_by, satisfied_by, source, ids=None, impl_files=IMPL_PATTERNS):
    """The assessment of each requirement in the scope of the run: ``({req: result}, impl_loc)``.

    A requirement is in the scope if twister ran at least one of its verifying
    cases in this run. If ``ids`` is given, the requirement must also be a need.
    Each result has ``verdict`` and ``impls`` (`adequacy`), ``evidence``,
    ``symbols`` and ``cases``. ``impl_files``: the body files
    (`resolve_impl_symbols`).
    """
    reqs = sorted(
        r for r, cs in verified_by.items()
        if any(c in run.cases for c in cs) and (ids is None or r in ids)
    )
    symbols = sorted({s for r in reqs for s in satisfied_by.get(r, [])})
    impl_loc = resolve_impl_symbols(source, symbols, impl_files)
    out = {}
    for r in reqs:
        cases = sorted(set(verified_by[r]))
        syms = sorted(set(satisfied_by.get(r, [])))
        res = adequacy(syms, cases, run, impl_loc)
        res.update(evidence=evidence(cases, run), symbols=syms, cases=cases)
        out[r] = res
    return out, impl_loc


def line_ranges(lines):
    """``"79-81, 84"`` for sorted line numbers."""
    parts, start, prev = [], None, None
    for ln in lines:
        if start is None:
            start = prev = ln
        elif ln == prev + 1:
            prev = ln
        else:
            parts.append(f"{start}-{prev}" if prev != start else f"{start}")
            start = prev = ln
    if start is not None:
        parts.append(f"{start}-{prev}" if prev != start else f"{start}")
    return ", ".join(parts)
