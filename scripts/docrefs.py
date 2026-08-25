# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Central cross-document reference registry for the safety documentation set.

All inter-document links are derived from a single registry file,
``doc/documents.yaml``, so each ``conf.py`` only has to declare its own
identity (implicitly, via its build output directory) and pick up the derived
structures::

    import docrefs
    refs = docrefs.load(registry=DOC_BASE / "doc" / "documents.yaml")

    html_context = {"reference_groups": refs.reference_groups}
    intersphinx_mapping  = refs.intersphinx_mapping      # sphinx docs
    needs_external_needs = refs.needs_external_needs      # sphinx-needs docs
    version_scope        = refs.version_scope            # this doc's git-tag scope
    # doxylink = refs.doxylink                            # requires sphinxcontrib-doxylink

``reference_groups``, ``intersphinx_mapping`` and ``doxylink`` are emitted
unconditionally for every *other* document (no filesystem probing). This
determinism matters for the two-stage build (see ``xref_builder.py``): the
config a document produces is then identical in stage 1 (xref index) and
stage 2 (html), so Sphinx keeps the shared doctree cache valid and the html
build skips re-parsing. A target whose inventory/tag does not exist yet (e.g.
during stage 1) just produces a warning and resolves once stage 2 runs.

``needs_external_needs`` is the exception: sphinx-needs *raises* on a missing
external ``json_path`` (intersphinx and doxylink only warn), so it is gated on
the target's ``needs.json`` actually existing. A sphinx-needs document's config
therefore differs between stages until every peer index is built, so it re-reads
in stage 2 — an acceptable cost limited to the sphinx-needs documents.
"""

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import yaml

#: Filename of the Doxygen tag file every zdocs-built Doxygen document emits,
#: mirroring Sphinx's own fixed ``objects.inv``. Doxygen tag file names are not
#: standardised the way ``objects.inv`` is, so this is purely an engine
#: convention — which is exactly why it is named in one place: the value is
#: shared with ``cmake/doxygen.cmake`` (which WRITES it, via the appended
#: ``GENERATE_TAGFILE``) and ``cmake/registry.cmake`` (which downloads a
#: ``kind: doxygen-external`` peer's remote tag file TO it). Those two must be
#: changed together with this one.
#:
#: This is the LOCAL name only. A ``doxygen-external`` peer's remote tag file
#: is named by its own ``remote-tagfile:`` field and may be called anything;
#: the engine renames it to this on download.
DOXYGEN_TAGFILE = "doxygen.tag"


def _registry(registry):
    """Load, parse and validate the registry YAML.

    ``registry`` is required: this is a generic script, so the caller (a
    conf.py, or the CLI ``--registry`` flag) provides the path to its
    documents.yaml.

    Validation is centralised here so every entry point (conf.py import,
    ``tagfiles``, ``navlinks``) enforces the same rules and hard-errors on any
    problem instead of silently defaulting.
    """
    if not registry:
        raise ValueError("docrefs: a registry path (documents.yaml) is required")
    with open(registry) as f:
        data = yaml.safe_load(f)
    _validate(data)
    return data


#: Group ``mode:`` values (see documents.yaml's per-group field docs):
#:   "exclude_if_selected"    this_doc is excluded from its own group's nav
#:                            links (a page doesn't link to itself). Default
#:                            when a group has no ``mode:``.
#:   "single_doc_title_merge" same exclusion as "exclude_if_selected", for a
#:                            group whose membership always resolves to
#:                            exactly one document (e.g. the landing page) —
#:                            that single link then renders merged into the
#:                            caption instead of a caption + one-item list
#:                            (see the {% if group.links|length == 1 %}
#:                            check in _templates/layout.html).
#:   "always_keep"            every document in the group is always listed,
#:                            including this_doc.
_GROUP_MODES = ("exclude_if_selected", "single_doc_title_merge", "always_keep")

#: Group ``display:`` values (see documents.yaml's per-group field docs):
#:   "disabled_collapsing"      no expand/collapse control; the group is
#:                              always fully shown. Default when a group
#:                              has no ``display:``.
#:   "collapsed_at_opening"     the group is collapsible and starts
#:                              collapsed when the page loads.
#:   "not_collapsed_at_opening" the group is collapsible and starts
#:                              expanded when the page loads.
#:   "no-display"               the group is not shown at all, regardless
#:                              of how many links it would otherwise have.
_GROUP_DISPLAYS = (
    "disabled_collapsing",
    "collapsed_at_opening",
    "not_collapsed_at_opening",
    "no-display",
)

#: Document ``kind:`` values (see documents.yaml's per-document field docs).
_KINDS = ("sphinx", "doxygen", "external", "sphinx-external", "doxygen-external")

#: Allowed keys inside a document's ``testmodule:`` sub-block (step 27). One
#: block name shared by both halves of a spec/report pair — a document uses
#: only the keys its own directives need (see documents.yaml's own
#: ``testmodule:`` comments for the shape). An unknown key here (e.g. a
#: typo'd ``doxygen_src:``) must be a configure-time error, not silently
#: ignored: silently ignoring it would degrade to "no XML" with no
#: diagnostic at all.
_TESTMODULE_KEYS = ("doxygen_source", "api_reference", "spec")


def _validate(data):
    """Raise ``ValueError`` on any registry validation problem."""
    groups = data.get("groups")
    if not groups:
        raise ValueError(
            "docrefs: registry 'groups:' is missing or empty — declare at least "
            "one group with an 'id' and 'title'"
        )
    group_ids = {g["id"] for g in groups}

    for group in groups:
        mode = group.get("mode", "exclude_if_selected")
        if mode not in _GROUP_MODES:
            raise ValueError(
                f"docrefs: group '{group['id']}' has mode '{mode}', which is "
                f"not one of {_GROUP_MODES}"
            )
        display = group.get("display", "disabled_collapsing")
        if display not in _GROUP_DISPLAYS:
            raise ValueError(
                f"docrefs: group '{group['id']}' has display '{display}', which is "
                f"not one of {_GROUP_DISPLAYS}"
            )

    for doc_id, meta in data.get("documents", {}).items():
        group = meta.get("group")
        if group is None:
            raise ValueError(f"docrefs: document '{doc_id}' is missing a 'group:' field")
        if group not in group_ids:
            raise ValueError(
                f"docrefs: document '{doc_id}' has group '{group}', which is not "
                f"a declared group id (known groups: {sorted(group_ids)})"
            )
        kind = meta.get("kind", "sphinx")
        if kind not in _KINDS:
            raise ValueError(
                f"docrefs: document '{doc_id}' has kind '{kind}', which is not one of {_KINDS}"
            )
        if (
            kind in ("external", "sphinx-external", "doxygen-external")
            and meta.get("remote-url") is None
        ):
            # "remote-url" not in meta, or present but empty (YAML
            # `remote-url:` with no value) — an *empty string* ("root of
            # external_base_url") is deliberately valid and distinct from
            # this, so this checks for None specifically rather than
            # falsiness.
            raise ValueError(
                f"docrefs: {kind} document '{doc_id}' is missing a 'remote-url:' field"
            )
        if kind == "doxygen-external" and meta.get("remote-tagfile") is None:
            # A SEPARATE, independently-checked requirement from
            # 'remote-url:' above — a doxygen-external document needs BOTH
            # fields, and one being present must never mask the other being
            # absent (Doxygen tag-file names aren't standardized the way
            # Sphinx's objects.inv is, so there is no way to derive one from
            # the other).
            raise ValueError(
                f"docrefs: {kind} document '{doc_id}' is missing a 'remote-tagfile:' field"
            )

        # -- testmodule: sub-block (step 27) -----------------------------
        #
        # Rejected at CONFIGURE time (rule 6), naming the offending document,
        # rather than degrading at build time: an unresolvable reference here
        # would otherwise leave testmodule_xml_dir/testspec_needs_json empty
        # and the directives silently render nothing.
        testmodule = meta.get("testmodule")
        if testmodule is not None:
            unknown = sorted(set(testmodule) - set(_TESTMODULE_KEYS))
            if unknown:
                raise ValueError(
                    f"docrefs: document '{doc_id}' has unknown key(s) "
                    f"{unknown} in its 'testmodule:' block — allowed keys "
                    f"are {_TESTMODULE_KEYS}. A typo'd key (e.g. "
                    f"'doxygen_src' for 'doxygen_source') must not be "
                    f"silently ignored, or it would degrade to \"no XML\" "
                    f"with no diagnostic at all"
                )

            for field in ("doxygen_source", "api_reference"):
                ref_id = testmodule.get(field)
                if ref_id is None:
                    continue
                ref_meta = data.get("documents", {}).get(ref_id)
                if ref_meta is None:
                    raise ValueError(
                        f"docrefs: document '{doc_id}' has "
                        f"testmodule.{field}: '{ref_id}', which does not "
                        f"exist in the registry — fix the id, or add "
                        f"'{ref_id}' as a document"
                    )
                ref_kind = ref_meta.get("kind", "sphinx")
                if ref_kind != "doxygen":
                    raise ValueError(
                        f"docrefs: document '{doc_id}' has "
                        f"testmodule.{field}: '{ref_id}', which is kind "
                        f"'{ref_kind}', not 'doxygen' — {field} must name a "
                        f"'kind: doxygen' document"
                    )

            spec_id = testmodule.get("spec")
            if spec_id is not None:
                spec_meta = data.get("documents", {}).get(spec_id)
                if spec_meta is None:
                    raise ValueError(
                        f"docrefs: document '{doc_id}' has testmodule.spec: "
                        f"'{spec_id}', which does not exist in the registry "
                        f"— fix the id, or add '{spec_id}' as a document"
                    )
                spec_needs = spec_meta.get("needs")
                # Precise about the source kind: a `needs: source: inventory`
                # document (the real-world "requirements doc" shape) is
                # synthesized on the fly from an objects.inv (see
                # _needs_stub_from_inventory below) and is NOT the needs.json
                # testreport correlates against — only `source: json` is.
                # Left unrejected, this yields an empty testreport with a
                # clean exit at BUILD time (rule 5's failure shape) rather
                # than a loud configure-time refusal.
                if spec_needs is None or spec_needs.get("source") != "json":
                    raise ValueError(
                        f"docrefs: document '{doc_id}' has testmodule.spec: "
                        f"'{spec_id}', which does not publish a needs "
                        f"export ('needs: {{source: json}}') — testreport "
                        f"would correlate against nothing. Add "
                        f"'needs: {{source: json}}' to '{spec_id}', or "
                        f"point spec: at a document that already has it"
                    )


def _groups(data):
    """Ordered ``[{id, title, mode, display}]`` from the registry ``groups:`` list."""
    return [
        {
            "id": g["id"],
            "title": g["title"],
            "mode": g.get("mode", "exclude_if_selected"),
            "display": g.get("display", "disabled_collapsing"),
        }
        for g in data["groups"]
    ]


def grouped_links(this_doc, data, href_fn):
    """Ordered grouped cross-document links for ``this_doc``.

    Returns ``[{"id", "title", "mode", "display", "links": [{"label", "href"}]}]``:
      * groups in registry ``groups:`` order; documents in registry order;
      * groups with ``display: "no-display"`` are dropped entirely, as are
        groups left empty after filtering (no dangling heading);
      * ``label`` is the document ``title``; ``href`` is ``href_fn(doc_id, meta)``;
      * ``this_doc`` is excluded from its own group's links, unless that
        group's ``mode`` is ``"always_keep"`` (see ``_GROUP_MODES``).
    """
    documents = data["documents"]
    result = []
    for group in _groups(data):
        if group["display"] == "no-display":
            continue
        keep_current = group["mode"] == "always_keep"
        links = []
        for doc_id, meta in documents.items():
            if meta.get("group") != group["id"]:
                continue
            if doc_id == this_doc and not keep_current:
                continue
            links.append(
                {
                    "label": meta.get("title", doc_id),
                    "href": href_fn(doc_id, meta),
                }
            )
        if links:
            result.append(
                {
                    "id": group["id"],
                    "title": group["title"],
                    "mode": group["mode"],
                    "display": group["display"],
                    "links": links,
                }
            )
    return result


def build_root():
    """Deploy build root, derived from the per-target ``OUTPUT_DIR``.

    ``OUTPUT_DIR`` is the HTML output directory ``<root>/deploy/html/<id>``
    (step 22: builder-first layout), so the build root is three levels up —
    unchanged from the pre-step-22 ``<root>/deploy/<id>/html`` shape, since
    both nest the same two path segments (a builder name and a doc id, in
    either order) between ``deploy`` and the root. Useful for locating
    sibling deploy artifacts (e.g. a Doxygen project's XML for Breathe).
    """
    return Path(os.environ["OUTPUT_DIR"]).resolve().parents[2]


def _this_doc():
    """Registry id of the document currently being built (its deploy dir name).

    Step 22 moved the doc id from being ``OUTPUT_DIR``'s PARENT's name
    (``deploy/<id>/html``) to being ``OUTPUT_DIR``'s OWN name
    (``deploy/html/<id>``) — the builder folder and the doc id swapped
    places, so the doc id is now the last path segment, not the second-to-last.
    """
    return Path(os.environ["OUTPUT_DIR"]).resolve().name


def _needs_stub_from_inventory(html_dir, doc_id, cfg):
    """Synthesize a sphinx-needs external-needs JSON from a plain sphinx doc's
    ``objects.inv``.

    Lets documents that only publish an intersphinx inventory (e.g. the
    StrictDoc requirements document) still be imported as external needs. The
    stub is written next to the inventory and regenerated only when the
    inventory is newer.

    Returns the stub path once it has been generated, or ``None`` if the source
    inventory does not exist yet (stage 1, before the requirements doc's own
    index is built) — the caller then omits the entry, because sphinx-needs
    raises on a missing external ``json_path``.
    """
    inv_path = html_dir / "objects.inv"
    json_path = html_dir / "objects.json"
    out_path = html_dir / f"{doc_id}-needs.json"

    if not inv_path.exists():
        return None

    # Regenerate the sphobjinv JSON only when the inventory has changed.
    if not json_path.exists() or json_path.stat().st_mtime < inv_path.stat().st_mtime:
        subprocess.run(
            ["sphobjinv", "co", "json", str(inv_path), "--overwrite"],
            check=True,
            capture_output=True,
        )

    with open(json_path) as f:
        inv_data = json.load(f)

    label_re = re.compile(cfg.get("filter", r".*"))
    need_type = cfg.get("type", "requirement")
    status = cfg.get("status", "approved")

    needs = {}
    for k, v in inv_data.items():
        if k in ("project", "version", "count"):
            continue
        if v["role"] != "label" or not label_re.match(v["name"]):
            continue
        name = v["name"]
        title = v["dispname"] if v["dispname"] not in ("-", name) else name
        # sphobjinv uses '$' as a placeholder for the entry name in the URI.
        uri = v["uri"].replace("$", name)
        docname = uri.split(".html")[0]
        needs[name] = {
            "id": name,
            "type": need_type,
            "title": title,
            "content": "",
            "status": status,
            "docname": docname,
        }

    version = str(cfg.get("version", "1.0"))
    stub = {
        "current_version": version,
        "versions": {version: {"needs": needs, "needs_amount": len(needs)}},
    }
    with open(out_path, "w") as f:
        json.dump(stub, f, indent=2)
    return out_path


def _fallback_version(repo_root=None):
    """Graceful dev fallback: ``v0.0-dev+g<short-sha of repo_root>``.

    Never raises. Falls back further to a bare ``v0.0-dev`` if even
    ``git rev-parse`` fails (e.g. no git repo).
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if sha:
            return f"v0.0-dev+g{sha}"
    except Exception:
        pass
    return "v0.0-dev"


def resolve_version(*, scope=None, project=None, repo_root=None, west=None):
    """Resolve a document's displayed version. Single shared implementation.

    Used by both the sphinx path (``conf_common.py``) and the doxygen path (the
    ``version`` CLI subcommand). Resolution order:

      1. The ``VERSION`` env var (CI / reproducible-build escape hatch) wins.
      2. ``scope``: ``git -C <repo_root> describe --tags --match "<scope>/v*"
         --dirty``; the leading ``"<scope>/"`` is stripped so the version
         displays clean (``proj/v0.1-dirty`` -> ``v0.1-dirty``).
      3. ``project``: a west project name — its path is resolved via
         ``west list --format {abspath} <project>`` (run in the west topdir),
         then
         ``git -C <path> describe --tags --always --dirty`` (its own tag, else
         short sha, ``-dirty`` on a dirty tree).
      4. Otherwise / on any error -> graceful dev fallback
         (``v0.0-dev+g<short-sha of repo_root>``).

    Never raises. Deterministic for a given HEAD so the value is identical
    across the two sphinx build stages (xref and html).
    """
    version = os.environ.get("VERSION")
    if version:
        return version.strip()
    if scope:
        try:
            if scope == "/":
                described = subprocess.check_output(
                    ["git", "describe", "--tags", "--dirty"],
                    cwd=repo_root,
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            else:
                described = subprocess.check_output(
                    ["git", "describe", "--tags", "--match", f"{scope}/v*", "--dirty"],
                    cwd=repo_root,
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
        except Exception:
            return _fallback_version(repo_root)
        if not described:
            return _fallback_version(repo_root)
        prefix = f"{scope}/"
        if described.startswith(prefix):
            described = described[len(prefix) :]
        return described

    if project:
        try:
            path = subprocess.check_output(
                ["west", "list", "--format", "{abspath}", project],
                cwd=str(west) if west else None,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            described = subprocess.check_output(
                ["git", "describe", "--tags", "--always", "--dirty"],
                cwd=path,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return _fallback_version(repo_root)
        if not described:
            return _fallback_version(repo_root)
        return described

    return _fallback_version(repo_root)


class Refs:
    """Derived cross-document link structures for the current document."""

    def __init__(
        self,
        reference_groups,
        intersphinx_mapping,
        needs_external_needs,
        doxylink,
        version_scope=None,
        version_project=None,
        rel_urls=None,
        deploy_dirs=None,
        testmodule=None,
    ):
        self.reference_groups = reference_groups
        self.intersphinx_mapping = intersphinx_mapping
        self.needs_external_needs = needs_external_needs
        self.doxylink = doxylink
        self.version_scope = version_scope
        self.version_project = version_project
        self.rel_urls = rel_urls or {}
        self.deploy_dirs = deploy_dirs or {}
        #: This document's own resolved ``testmodule:`` block (step 27), or
        #: ``None`` when it has none — the registry entry IS the opt-in
        #: signal ``zdocs_conf.configure()`` uses to load the ``test_module``
        #: extension (decision 2), so ``None`` here must mean "do nothing",
        #: never a dict of empty strings. A dict with keys ``xml_dir``,
        #: ``doxygen_url``, ``api_url``, ``needs_json`` (each ``""`` when the
        #: corresponding ``testmodule:`` field is absent, e.g. no
        #: ``api_reference:``).
        self.testmodule = testmodule


def _resolve_external_url(url, external_base_url):
    """A ``kind: external`` document's ``remote-url:``, resolved against
    ``external_base_url`` if it's relative (no scheme, e.g. ``"html/sop-
    docctl/index.html"``) — left untouched if it's already absolute (has a
    scheme, e.g. ``"https://www.zephyrproject.org/"``), since not every
    external link lives under the same host as ``external_base_url``.
    """
    if urlsplit(url).scheme:
        return url
    return f"{external_base_url}/{url.lstrip('/')}"


def _intersphinx_target_dir(remote_url):
    """Derive a base directory URL from a ``remote-url:`` — strips a trailing
    FILENAME segment (one that looks like one, i.e. contains a ``.``, e.g.
    ``index.html``) and ensures a trailing slash, e.g.
    ``"https://docs.zephyrproject.org/latest/index.html"`` ->
    ``"https://docs.zephyrproject.org/latest/"``. A ``remote-url:`` already
    ending in ``"/"`` is returned unchanged.

    A ``remote-url:`` that is already a BARE DIRECTORY path — its last
    segment has no ``.`` (e.g. ``".../latest"``, or ``".../doxygen/html"``) —
    is NOT stripped: that last segment is a real path component, not a
    filename, so only a trailing slash is appended, e.g.
    ``"https://docs.zephyrproject.org/latest"`` ->
    ``"https://docs.zephyrproject.org/latest/"`` (the ``"latest"`` segment is
    kept). Splitting on ``"."`` rather than assuming the last segment is
    always a filename matters because a real ``remote-url:`` is written
    either way depending on the remote site's own convention, and the two
    must not collapse to the same (wrong, truncated) result.

    Used by both ``kind: sphinx-external`` (intersphinx's own target
    directory convention, hence the name) and ``kind: doxygen-external``
    (the absolute location half of a ``TAGFILES`` entry, and the
    ``doxylink`` base url) — reused verbatim rather than renamed for the
    second use, since test_20_sphinx_external.py's own
    ``test_intersphinx_target_dir_strips_a_trailing_filename_and_keeps_a_trailing_slash``
    pins this exact name via ``getattr(docrefs, "_intersphinx_target_dir", ...)``,
    and that existing, already-passing test must not be broken to satisfy a
    naming preference this step's own test module explicitly left as a
    judgment call (see its module docstring).
    """
    if remote_url.endswith("/"):
        return remote_url
    scheme, netloc, path, query, fragment = urlsplit(remote_url)
    head, _, last_segment = path.rpartition("/")
    if "." in last_segment:
        # The last segment looks like a filename (e.g. "index.html") —
        # strip it, keeping everything before it.
        path = head + "/"
    else:
        # The last segment is a bare directory name (e.g. "latest") — keep
        # it, just add the trailing slash.
        path = path + "/"
    return urlunsplit((scheme, netloc, path, query, fragment))


def external_doc(doc_id, registry=None):
    """``(title, url)`` for a ``kind: external``/``kind: sphinx-external``/
    ``kind: doxygen-external`` registry document, or ``None`` if ``doc_id``
    doesn't exist or isn't one of those kinds.

    Used by the ``qmsdoc`` role (``sphinx/_extensions/qms_ref.py``) to
    reference e.g. a QMS SOP from content — standard ``:ref:``/
    ``:external+prefix:ref:`` roles can't resolve these: they have no
    local label, and (for ``kind: external``) are deliberately excluded
    from ``intersphinx_mapping`` (no ``objects.inv`` to fetch — see
    documents.yaml's own field docs). A ``kind: sphinx-external``
    document IS also in ``intersphinx_mapping`` (see ``load()``), and a
    ``kind: doxygen-external`` document IS also in ``doxylink`` (see
    ``load()``), but ``:qmsdoc:`` still resolves any of them the same
    whole-document way as a plain ``external`` one.
    """
    data = _registry(registry)
    meta = data.get("documents", {}).get(doc_id)
    if meta is None or meta.get("kind") not in (
        "external",
        "sphinx-external",
        "doxygen-external",
    ):
        return None
    external_base_url = os.environ.get(
        "ZDOCS_DOC_EXTERNAL_BASE_URL", data.get("external_base_url", "")
    ).rstrip("/")
    url = _resolve_external_url(meta["remote-url"], external_base_url)
    return meta.get("title", doc_id), url


def _url_exists(url, timeout=5):
    """Best-effort HTTP existence check (HEAD request, any 2xx/3xx response
    counts). Never raises: a network error — including a genuinely
    unreachable or access-restricted host — is reported as "doesn't exist"
    rather than failing the build. Only called when check_external_urls is
    enabled (see load()); off by default, since the build job may have no
    route to some external hosts (e.g. an internal-only site).
    """
    try:
        with urlopen(Request(url, method="HEAD"), timeout=timeout) as response:
            return 200 <= response.status < 400
    except (URLError, ValueError, OSError):
        return False


def load(this_doc=None, registry=None):
    """Build the cross-document link structures for ``this_doc``.

    ``this_doc`` defaults to the document currently being built (detected from
    ``OUTPUT_DIR``); pass it explicitly to override. ``registry`` defaults to
    ``doc/documents.yaml``.
    """
    data = _registry(registry)

    # ZDOCS_-prefixed, matching the rest of the environment contract that
    # cmake/sphinx.cmake sets. These used to read DOC_BASE_URL and friends while
    # the build system passed <PROJECT>_DOC_BASE_URL, so the documented CMake
    # option silently did nothing and the registry's base_url always won —
    # invisible, because the registry value is usually right.
    base_url = os.environ.get("ZDOCS_DOC_BASE_URL") or data.get("base_url", "")
    base_url = base_url.rstrip("/") + "/"
    external_base_url = os.environ.get(
        "ZDOCS_DOC_EXTERNAL_BASE_URL", data.get("external_base_url", "")
    )
    external_base_url = external_base_url.rstrip("/")
    # Off by default: the build job may have no network route to some
    # external hosts (e.g. an access-restricted internal site), so probing
    # must be something a CI job opts into, not something it has to opt out
    # of just to get a working build.
    check_external_urls = str(
        os.environ.get("ZDOCS_DOC_CHECK_EXTERNAL_URLS", data.get("check_external_urls", False))
    ).strip().lower() in ("1", "true", "yes", "on")
    documents = data["documents"]
    deploy = build_root() / "deploy"
    this_doc = this_doc or _this_doc()

    # Registry-derived cross-document maps for extensions that need paths/URLs
    # to peer documents (e.g. test_module). Keyed by registry doc id; external
    # docs are skipped (they have no build output). `rel_urls` are deploy-relative
    # (from THIS doc's html root, portable); `deploy_dirs` are filesystem paths.
    this_path = documents.get(this_doc, {}).get("path", f"html/{this_doc}")
    rel_urls = {}  # doc_id -> URL relative to THIS doc's html root
    deploy_dirs = {}  # doc_id -> filesystem path (str) of that doc's html output dir
    for _doc_id, _meta in documents.items():
        if _meta.get("kind") in ("external", "sphinx-external", "doxygen-external"):
            continue
        _path = _meta.get("path", f"html/{_doc_id}")
        rel_urls[_doc_id] = posixpath.relpath(_path, this_path)
        deploy_dirs[_doc_id] = str(deploy / _path)

    # Nav links, grouped by the registry's `groups:`. Absolute hrefs (base_url):
    # sphinx/doxygen -> base_url + path; external -> its `remote-url`,
    # resolved against external_base_url if relative (see
    # _resolve_external_url).
    def _abs_href(doc_id, meta):
        if meta.get("kind") in ("external", "sphinx-external", "doxygen-external"):
            return _resolve_external_url(meta["remote-url"], external_base_url)
        return base_url + meta.get("path", f"html/{doc_id}")

    reference_groups = grouped_links(this_doc, data, _abs_href)

    if check_external_urls:
        for doc_id, meta in documents.items():
            if meta.get("kind") not in ("external", "sphinx-external", "doxygen-external"):
                continue
            url = _resolve_external_url(meta["remote-url"], external_base_url)
            if not _url_exists(url):
                print(
                    f"docrefs: WARNING: external document '{doc_id}' url '{url}' is not reachable",
                    file=sys.stderr,
                )

    intersphinx_mapping = {}
    needs_external_needs = []
    doxylink = {}

    for doc_id, meta in documents.items():
        if doc_id == this_doc:
            continue

        kind = meta.get("kind", "sphinx")
        # External links have no build outputs — no inventory/tag/needs.
        if kind == "external":
            continue

        path = meta.get("path", f"html/{doc_id}")
        url = base_url + path
        html_dir = deploy / path
        prefix = meta.get("prefix", doc_id.replace("-", "_"))

        if kind == "sphinx":
            # Local inventory only (no URL fallback / no trailing None): a
            # missing inventory then warns instead of triggering a slow network
            # fetch of <url>/objects.inv. Emitted unconditionally so the config
            # stays stable across build stages (keeps the doctree cache valid).
            intersphinx_mapping[prefix] = (url, str(html_dir / "objects.inv"))
        elif kind == "sphinx-external":
            # `None` inventory is DELIBERATE here (unlike the "sphinx" branch
            # above, which never uses `None` for its own stated reasons):
            # this document has no local build at all, so there is no
            # `objects.inv` on disk to point at — `None` tells Sphinx's own
            # intersphinx extension to fetch it itself, at build time, from
            # the target directory derived from `remote-url:`.
            intersphinx_mapping[prefix] = (_intersphinx_target_dir(meta["remote-url"]), None)
        elif kind == "doxygen":
            doxylink[prefix] = (str(html_dir / DOXYGEN_TAGFILE), url)
        elif kind == "doxygen-external":
            # Like "sphinx-external" above, this document has no local build
            # of its own: `html_dir` is where the engine downloads
            # `remote-tagfile:` to (see registry.cmake's doxygen-external
            # branch), and the base url is derived from `remote-url:` the
            # same way intersphinx's own target directory is.
            base_dir_url = _intersphinx_target_dir(meta["remote-url"])
            doxylink[prefix] = (str(html_dir / DOXYGEN_TAGFILE), base_dir_url)

        needs_cfg = meta.get("needs")
        if needs_cfg is not None:
            if needs_cfg.get("source") == "inventory":
                json_path = _needs_stub_from_inventory(html_dir, doc_id, needs_cfg)
            else:
                candidate = html_dir / "needs.json"
                json_path = candidate if candidate.exists() else None
            # Unlike intersphinx, sphinx-needs RAISES on a missing external
            # json_path, so this one entry must be gated on existence. It
            # resolves once the target's needs.json is built (by stage 2).
            if json_path is not None:
                needs_external_needs.append(
                    {
                        "json_path": str(json_path),
                        "base_url": url,
                    }
                )

    # The current document's own version source (e.g. scope "docs/swrs" or a
    # west project name), used by conf_common / the version CLI to derive its
    # displayed version. this_doc is excluded from the link structures above,
    # but reading its own meta here is fine.
    this_meta = documents.get(this_doc, {})
    version_scope = this_meta.get("version_scope")
    version_project = this_meta.get("version_project")

    # This document's own testmodule: block (step 27), resolved from the
    # rel_urls/deploy_dirs maps just built above. `_validate()` (via
    # `_registry()`, already called at the top of this function) has already
    # guaranteed every referenced id exists, is the right kind, and (for
    # `spec`) publishes a needs export — so no further existence/kind
    # checking is needed here.
    testmodule_block = this_meta.get("testmodule")
    testmodule = None
    if testmodule_block is not None:
        doxygen_source = testmodule_block.get("doxygen_source")
        api_reference = testmodule_block.get("api_reference")
        spec = testmodule_block.get("spec")

        xml_dir = ""
        if doxygen_source:
            # Step 22/23 deploy layout: Doxygen XML lives at
            # `deploy/xml/<id>/`, keyed on the registry id verbatim — the
            # SAME id `add_docs_from_registry` now passes straight through
            # to `add_doxygen_target` (step 24b removed the two compensating
            # strips that used to derive a bare name here and in
            # cmake/registry.cmake), NOT `Path(html).parent / "xml"` (the
            # never-migrated conf_test_common.py:42-43 expression, which
            # predates the step 22 rewrite entirely and is wrong for this
            # engine).
            xml_dir = str(deploy / "xml" / doxygen_source)

        needs_json = ""
        if spec:
            needs_json = str(Path(deploy_dirs[spec]) / "needs.json")

        testmodule = {
            "xml_dir": xml_dir,
            "doxygen_url": rel_urls.get(doxygen_source, "") if doxygen_source else "",
            "api_url": rel_urls.get(api_reference, "") if api_reference else "",
            "needs_json": needs_json,
        }

    return Refs(
        reference_groups,
        intersphinx_mapping,
        needs_external_needs,
        doxylink,
        version_scope,
        version_project,
        rel_urls=rel_urls,
        deploy_dirs=deploy_dirs,
        testmodule=testmodule,
    )


def tagfiles(this_doc, deploy_dir, registry=None):
    """Doxygen ``TAGFILES`` value for ``this_doc``: an entry for every OTHER
    ``kind: doxygen`` document in the registry, so any doxygen doc can resolve
    symbols defined in the others (e.g. testspec → safety-api) — plus an entry
    for every ``kind: doxygen-external`` peer, so an internal doxygen document
    can also resolve symbols documented in an externally-hosted one.

    Each entry is ``<tagfile>=<location>``. For an internal ``kind: doxygen``
    peer, ``location`` is the target's HTML dir relative to this doc's HTML
    dir (a filesystem hop, since both live under the same ``deploy/``). For a
    ``kind: doxygen-external`` peer there is no local HTML dir to be relative
    to — the tag file is downloaded, but the HTML it links into is hosted
    remotely — so ``location`` is instead the ABSOLUTE remote base directory
    url derived from ``remote-url:`` (Doxygen's ``TAGFILES`` natively accepts
    an absolute URL as the location half — the standard way to link against
    an externally-hosted Doxygen site). Unlike the build-time helpers this
    runs at CMake configure time (no ``OUTPUT_DIR``), so ``deploy_dir`` is
    passed in and entries are emitted unconditionally — Doxygen simply warns
    (and continues) for a tag file that has not been generated yet.
    """
    documents = _registry(registry)["documents"]
    deploy = Path(deploy_dir)
    this_path = documents.get(this_doc, {}).get("path", f"html/{this_doc}")
    this_html = (deploy / this_path).as_posix()

    entries = []
    for doc_id, meta in documents.items():
        if doc_id == this_doc:
            continue
        kind = meta.get("kind")
        if kind == "doxygen":
            path = meta.get("path", f"html/{doc_id}")
            tag = (deploy / path / DOXYGEN_TAGFILE).as_posix()
            location = posixpath.relpath((deploy / path).as_posix(), this_html)
            entries.append(f"{tag}={location}")
        elif kind == "doxygen-external":
            path = meta.get("path", f"html/{doc_id}")
            tag = (deploy / path / DOXYGEN_TAGFILE).as_posix()
            base_dir_url = _intersphinx_target_dir(meta["remote-url"])
            entries.append(f"{tag}={base_dir_url}")
    return " ".join(entries)


def navlinks(this_doc, registry=None):
    """Grouped cross-document navigation entries for ``this_doc``.

    Returns the grouped list ``[{id, title, links: [{label, href}]}]`` for every
    OTHER document in the registry, grouped by the registry's ``groups:``.

    Consumed by the doxygen cross-doc nav widget (doxygen/cross-doc-nav.js).
    ``href`` is deploy-relative (``<path>/index.html``) for sphinx/doxygen docs so
    the widget resolves it against the deploy/ root regardless of where the site
    is served; ``external``/``sphinx-external``/``doxygen-external`` docs use
    their absolute ``remote-url`` verbatim instead — a relative deploy-path
    href for one of these would resolve, in the reader's browser, against the
    CURRENT page's own URL rather than the deploy root, silently landing back
    on this site instead of the real remote one. Mirrors the sphinx sidebar's
    grouped document list (``load()``'s own ``_abs_href``), which is derived
    from the same registry (``reference_groups``) and has covered all three
    kinds since steps 20/21.
    """
    data = _registry(registry)

    def _rel_href(doc_id, meta):
        if meta.get("kind") in ("external", "sphinx-external", "doxygen-external"):
            return meta["remote-url"]
        path = meta.get("path", f"html/{doc_id}")
        return f"{path}/index.html"

    return grouped_links(this_doc, data, _rel_href)


def xml_enabled(registry=None):
    """Whether the project-scoped ``doxygen_xml:`` opt-in (step 23) is on.

    A single top-level boolean in the registry — NOT per-document — so this
    takes no ``doc_id``: when the key is present and true, EVERY ``kind:
    doxygen`` document in the registry generates XML; when it is absent (the
    common case: nothing in this registry ever wrote it) or explicitly
    false, NONE do, regardless of what any individual document's own
    ``Doxyfile.in`` says about ``GENERATE_XML`` (see the module docstring's
    ``load()`` example and ``zdocs-design-deploy-layout.md`` §3.4).

    The factory (``add_doxygen_target``, ``cmake/doxygen.cmake``) calls this
    itself, the same way it already shells out to ``tagfiles``/``navlinks``,
    rather than being handed the answer as a CMake argument by
    ``add_docs_from_registry`` — that is what makes a document declared via
    a hand-written ``add_doxygen_target(... REGISTRY ...)`` call (bypassing
    ``add_docs_from_registry`` entirely, as ``doc-broken-xref``'s fixture
    does) see the exact same answer as one declared through the registry
    dispatcher.
    """
    data = _registry(registry)
    return bool(data.get("doxygen_xml", False))


def manifest(registry=None):
    """The whole registry, as a plain list of ``{id, kind, group, doc_dir,
    builders, remote_tagfile}`` dicts, in registry order.

    Unlike ``navlinks``/``tagfiles`` (per-document views, keyed on
    ``this_doc``), this is a view over the WHOLE registry with no document
    excluded — the consumer is CMake's ``add_docs_from_registry``, which needs
    every entry (including ``kind: external`` ones, so it can skip them) to
    generate the per-document ``add_sphinx_target``/``add_doxygen_target``
    calls a consumer used to write by hand.

    Each field:
      * ``id`` — the document's key in the registry.
      * ``kind`` — defaults to ``"sphinx"``, matching ``load()``'s own
        convention (a document with no ``kind:`` is a plain Sphinx document).
      * ``group`` — as declared; ``_validate()`` (via ``_registry()``) already
        guarantees this is never missing.
      * ``doc_dir`` — the RAW value from the registry (``None`` if absent).
        Deliberately not resolved to an absolute path here: only CMake knows
        where ``documents.yaml`` lives when it wants to resolve one, and
        resolving it in Python would bake this script's notion of "relative
        to" into the output instead of leaving that to the caller.
      * ``builders`` — ``meta.get("builders", [])`` for a ``sphinx`` document
        (the only kind that takes one); ``[]`` for every other kind, since
        neither doxygen nor external documents have a BUILDERS concept.
      * ``remote_tagfile`` — ``meta.get("remote-tagfile")`` (``None`` for
        every kind other than ``doxygen-external``, which is the only one
        that has this field at all). CMake needs this to build the
        ``<id>-tag`` download target's command; it has no other way to
        read a single registry field without re-parsing the whole YAML file
        itself.
      * ``testmodule_doxygen_source`` — this document's own ``testmodule:``
        block's ``doxygen_source`` field (``None`` when the document carries
        no ``testmodule:`` block, or the block omits that field). Step 28b:
        ``add_docs_from_registry`` uses this to wire
        ``add_dependencies(<doc>-<builder> <doxygen_source>)`` — the surviving
        ordering edge from ``zdocs-brief-step28b-twister-report.md`` §2
        decision 2/3, fixing the concurrency hazard between a report
        document's stage-2 build and its doxygen source's own stage-2 run
        both touching ``deploy/xml/<id>/``. The value is the RAW registry
        id (e.g. ``"dox-checks"``, the fixture that keeps its prefix on
        purpose), which already IS the doxygen document's own CMake target
        name (``add_doxygen_target`` takes the id verbatim, since step 24b)
        — no prefix stripping needed here, nor in the "doxygen" dispatch
        branch below any more; before that step this edge already needed
        none while that branch did.
      * ``testmodule_spec`` — this document's own ``testmodule:`` block's
        ``spec`` field (``None`` when absent). Step 28b (decision 2,
        corrected a second time — the edge this field drives was first
        called redundant, then found to guard a real stage-1 race and
        reinstated): ``add_docs_from_registry`` wires
        ``add_dependencies(<doc>-index <spec>-index)`` — both documents'
        stage-1 targets are otherwise unordered siblings under ``doc-tags``,
        so a report document's stage-1 ``testreport``/``twisterinfo`` can run
        BEFORE its spec's stage-1 has exported ``needs.json``, silently
        yielding an incomplete export from whatever DID already run. Unlike
        ``doxygen_source``, ``spec`` names a SPHINX document (e.g.
        ``"duties"``), so the target name is ``<spec>-index``, not the raw
        value itself — see ``add_sphinx_target``'s own ``<doc_name>-index``
        stage-1 target convention. Directional by construction (a document is
        never its own spec), so this cannot cycle; it is deliberately NOT
        generalised to every needs-importer/publisher pair, which CAN cycle
        and is its own, deferred step.
    """
    documents = _registry(registry)["documents"]
    entries = []
    for doc_id, meta in documents.items():
        kind = meta.get("kind", "sphinx")
        testmodule = meta.get("testmodule") or {}
        entries.append(
            {
                "id": doc_id,
                "kind": kind,
                "group": meta.get("group"),
                "doc_dir": meta.get("doc_dir"),
                "builders": meta.get("builders", []) if kind == "sphinx" else [],
                "remote_tagfile": meta.get("remote-tagfile"),
                "testmodule_doxygen_source": testmodule.get("doxygen_source"),
                "testmodule_spec": testmodule.get("spec"),
            }
        )
    return entries


def _cli(argv=None):
    """Command-line entry point (used by CMake at configure time)."""
    parser = argparse.ArgumentParser(
        prog="docrefs",
        description="Query the central document registry (documents.yaml).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_tagfiles = sub.add_parser(
        "tagfiles",
        help="print the Doxygen TAGFILES string for a document",
        description="Print the Doxygen TAGFILES entries linking this document "
        "to every other doxygen document in the registry.",
    )
    p_tagfiles.add_argument(
        "doc_id", help="registry id of this document, e.g. doxygen-zephyr-safety-api"
    )
    p_tagfiles.add_argument(
        "deploy_dir", help="path to the deploy/ directory holding the built docs"
    )
    p_tagfiles.add_argument(
        "--registry",
        metavar="documents.yaml",
        required=True,
        help="path to the document registry (documents.yaml)",
    )

    p_navlinks = sub.add_parser(
        "navlinks",
        help="print the cross-document nav links JS for a document",
        description="Print 'window.ZDOCS_NAV_LINKS = [...]' listing every other "
        "document in the registry, for the doxygen cross-doc nav widget.",
    )
    p_navlinks.add_argument(
        "doc_id", help="registry id of this document, taken verbatim, e.g. widget"
    )
    p_navlinks.add_argument(
        "--registry",
        metavar="documents.yaml",
        required=True,
        help="path to the document registry (documents.yaml)",
    )

    p_xml_enabled = sub.add_parser(
        "xml-enabled",
        help="print whether the project-scoped doxygen_xml: opt-in is on",
        description="Print TRUE or FALSE depending on whether the registry's "
        "top-level doxygen_xml: key is present and true (step 23). "
        "Project-scoped, not per-document: takes no doc_id.",
    )
    p_xml_enabled.add_argument(
        "--registry",
        metavar="documents.yaml",
        required=True,
        help="path to the document registry (documents.yaml)",
    )

    p_manifest = sub.add_parser(
        "manifest",
        help="print the whole registry as a JSON array",
        description="Print every document in the registry as a JSON array of "
        "{id, kind, group, doc_dir, builders} objects, in registry "
        "order — for CMake's add_docs_from_registry to parse "
        "directly via string(JSON ...).",
    )
    p_manifest.add_argument(
        "--registry",
        metavar="documents.yaml",
        required=True,
        help="path to the document registry (documents.yaml)",
    )

    p_version = sub.add_parser(
        "version",
        help="print a document's git-derived version string",
        description="Resolve and print a document's displayed version from its "
        "version_scope (consuming repo git tags) or version_project "
        "(a west project's own git describe).",
    )
    p_version.add_argument(
        "doc_id", help="registry id of this document, taken verbatim, e.g. widget"
    )
    p_version.add_argument(
        "--registry",
        metavar="documents.yaml",
        required=True,
        help="path to the document registry (documents.yaml)",
    )
    p_version.add_argument(
        "--repo-root",
        metavar="DIR",
        default=None,
        help="path to the consuming project's git root (for version_scope)",
    )
    p_version.add_argument(
        "--west", metavar="DIR", default=None, help="west workspace topdir (for version_project)"
    )

    args = parser.parse_args(argv)

    if args.command == "tagfiles":
        sys.stdout.write(tagfiles(args.doc_id, args.deploy_dir, args.registry))
    elif args.command == "navlinks":
        links = navlinks(args.doc_id, args.registry)
        sys.stdout.write("window.ZDOCS_NAV_LINKS = " + json.dumps(links, indent=2) + ";\n")
    elif args.command == "xml-enabled":
        sys.stdout.write("TRUE" if xml_enabled(args.registry) else "FALSE")
    elif args.command == "manifest":
        sys.stdout.write(json.dumps(manifest(args.registry)))
    elif args.command == "version":
        meta = _registry(args.registry)["documents"].get(args.doc_id, {})
        ver = resolve_version(
            scope=meta.get("version_scope"),
            project=meta.get("version_project"),
            repo_root=args.repo_root,
            west=args.west,
        )
        sys.stdout.write(ver)


if __name__ == "__main__":
    _cli()
