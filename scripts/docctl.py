#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# Copyright (c) 2026 almedso GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Author/review/approve controlled documents by editing their
``.. doc_control::`` directive and committing the change with the caller's
own git identity.

    docctl list
    docctl author <document-id> [--version VERSION]
    docctl review <document-id> [--force]
    docctl approve <document-id> [--effective-date YYYY-MM-DD] [--force]
    docctl bump-version <document-id> [--major | --minor]

Documents are looked up by id in a ``documents.yaml`` registry (default:
this repo's own ``doc/documents.yaml``, resolved relative to this script;

All three subcommands:
  * take the caller's identity from ``git config user.name``/``user.email``
    (i.e. the same ``.gitconfig`` git itself uses for authorship);
  * stage only the one file changed and commit it signed-off (``-s``) and
    GPG-signed (``-S``) — this is a controlled-document compliance action,
    so an unconfigured signing key is a hard failure, not a skip;
  * commit with a subject line of "docs(<document-id>): <Action> version
    <version-no>" — the document's current version (or, for ``author``,
    the new ``--version`` if given), read from the directive before
    editing it.

``author``'s commit relies on the ``-s``-generated ``Signed-off-by:`` line
alone. ``review``/``approve`` add a further trailer recording which action
was taken, since a plain Signed-off-by doesn't distinguish "I wrote this"
from "I reviewed/approved this": ``Reviewed-by:`` / ``Approved-by:``.

``review`` refuses to run unless ``author`` is already set (i.e. ``docctl
author`` ran first); ``approve`` likewise refuses unless ``reviewed_by`` is
already set *and* backed by an actual commit (``git blame`` on that line
resolves to a real commit, not an uncommitted edit) — i.e. ``docctl review``
ran and its commit succeeded. This enforces the author -> review -> approve
order.

``approve`` additionally creates a signed tag (``git tag -s``) on the new
commit, named ``<document-id>/<version>`` per SOP-DOCCTL's "Released
Versions" — the same ``<document-id>/*`` scheme ``docrefs.resolve_version``
matches against to render the sidebar's version.

``review`` also refuses (segregation of duties — SOP-DOCCTL: "enforces that
author is a different person than the reviewer") if the commit that set
``author`` (found via ``git blame`` on that line) was made by the same
person now running ``review``, identified by committer email.

``--force`` overrides either check: on ``review`` it allows self-review; on
``approve`` it allows approving without a committed review.

``bump-version`` starts a new version cycle for an already-released
controlled document (see SOP-DOCCTL's "Starting an Updated Version") —
refused for ``classification: Record`` documents, which use their own
edition-per-folder versioning instead. ``--minor`` (default) bumps
``x.Y`` -> ``x.Y+1``; ``--major`` bumps ``X.y`` -> ``X+1.0``; the current
version must already be ``major.minor``. It then, in one commit:
  * sets ``:version:`` to the new version;
  * removes ``:author:``, ``:reviewed_by:``, ``:approved_by:`` and
    ``:approval_date:`` from the directive entirely (not just blanks
    them), so doc_control.py's own "not-authored-yet"/etc. placeholders
    take over until the new version is actually authored/reviewed/
    approved again;
  * if a release tag ``<document-id>/<old-version>`` exists, points the
    document's ``.. git_changelog::`` directive's ``:rev-list:`` at
    ``<document-id>/<old-version>..HEAD``, so the rendered change history
    covers only this new version's commits instead of an arbitrary
    window of recent commits;
  * commits with subject "docs(<document-id>): Bump version to
    <new-version>" and a plain ``Signed-off-by:`` trailer (like
    ``author``).
"""

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent

# No default registry: this script ships with the ENGINE, which has no documents
# of its own. It used to default to `<script>/../doc/documents.yaml`, which was
# right while it lived in the consuming repository and resolves to a
# non-existent file here — and the failure would have been the quiet kind,
# because `list` silently drops entries whose confdir does not resolve and would
# have printed nothing at all.
#
# A project that runs this often should wrap it:
#   alias docctl='python3 <zdocs>/scripts/docctl.py --registry <repo>/doc/documents.yaml'

DOC_CONTROL_RE = re.compile(r"^\.\. doc_control::\s*$")
# The directive is written with or without a space before '::' across
# existing SOPs ('.. git_changelog ::' / '.. git_changelog::') — match both.
GIT_CHANGELOG_RE = re.compile(r"^\.\.\s+git_changelog\s*::\s*$")
OPTION_RE = re.compile(r"^(?P<indent>[ \t]+):(?P<key>[a-zA-Z_]+):\s*(?P<value>.*)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


class DocctlError(Exception):
    """A user-facing error; caught at the top level and printed without a traceback."""


def _load_registry(registry_path):
    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def _confdir_for(registry_path, document_id, data):
    documents = data.get("documents", {})
    if document_id not in documents:
        known = ", ".join(sorted(documents))
        raise DocctlError(f"Unknown document-id '{document_id}'. Known ids: {known}")

    meta = documents[document_id]
    group_id = meta.get("group")
    group_dir = ""
    for g in data.get("groups", []):
        if g["id"] == group_id:
            group_dir = g.get("dir", "")
            break

    # <registry dir>/<docs_root>/<group dir>/<document id>, skipping the parts
    # that are empty or ".".
    #
    # `docs_root` is registry-level and defaults to "docs", which is the layout
    # this script was written against (qms-base: registry at the repo root,
    # documents under docs/<group.dir>/<id>).
    root = registry_path.parent
    parts = [data.get("docs_root", "docs"), group_dir, document_id]
    for part in parts:
        if part and part != ".":
            root = root / part
    return root


def _find_doc_control_file(confdir):
    candidates = []
    for path in sorted(confdir.glob("*.rst")):
        text = path.read_text(encoding="utf-8")
        if any(DOC_CONTROL_RE.match(line) for line in text.splitlines()):
            candidates.append(path)

    if not candidates:
        raise DocctlError(f"No '.. doc_control::' directive found under {confdir}")
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        raise DocctlError(
            f"Multiple '.. doc_control::' directives found directly under {confdir} "
            f"({names}) — docctl only knows how to update a single, unambiguous one"
        )
    return candidates[0]


def _read_directive_options(path, directive_re):
    """Existing option -> value pairs in the block introduced by the first
    line matching ``directive_re`` (e.g. ``.. doc_control::`` or
    ``.. git_changelog::``). Returns None if no matching directive is
    found — the caller decides whether that's an error (doc_control always
    is) or just "nothing to do" (git_changelog is optional).
    """
    lines = path.read_text(encoding="utf-8").splitlines()

    start = next((i for i, line in enumerate(lines) if directive_re.match(line)), None)
    if start is None:
        return None

    values = {}
    i = start + 1
    while i < len(lines):
        m = OPTION_RE.match(lines[i])
        if not m:
            break
        values[m.group("key")] = m.group("value").strip()
        i += 1
    return values


def _read_doc_control(path):
    """Existing option -> value pairs in ``path``'s ``.. doc_control::``
    block. A key absent here means the option isn't set in the source at
    all (the "not-authored-yet"/etc. placeholders doc_control.py renders
    are synthesized at build time, never written back to the source).
    """
    values = _read_directive_options(path, DOC_CONTROL_RE)
    if values is None:
        raise DocctlError(f"No '.. doc_control::' directive found in {path}")
    return values


def _require(doc_file, document_id, field, prior_command):
    """Raise unless ``field`` is already set (non-blank) in doc_file — used
    to enforce the author -> review -> approve order.
    """
    existing = _read_doc_control(doc_file)
    if not existing.get(field, "").strip():
        raise DocctlError(
            f"{doc_file} has no '{field}' set yet — run "
            f"`docctl {prior_command} {document_id}` first"
        )
    return existing


def _identity_email(identity):
    """Extract the "<email>" out of an "Name <email>" identity string."""
    m = re.search(r"<(.+)>\s*$", identity)
    return (m.group(1) if m else identity).strip().lower()


def _field_committer_email(repo_root, doc_file, field):
    """Committer email of the commit that last set/changed the exact
    ':<field>:' line in doc_file, via ``git blame`` — used to check the
    reviewer/author segregation-of-duties rule (see SOP-DOCCTL's "enforces
    that author is a different person than the reviewer"). Returns None
    if the field isn't currently set, or blame can't attribute a commit
    (e.g. an uncommitted edit) — in either case there's nothing to check.
    """
    lines = doc_file.read_text(encoding="utf-8").splitlines()
    line_no = next(
        (
            i + 1
            for i, line in enumerate(lines)
            if (m := OPTION_RE.match(line)) and m.group("key") == field and m.group("value").strip()
        ),
        None,
    )
    if line_no is None:
        return None

    rel_path = doc_file.relative_to(repo_root)
    blame = _git(
        ["blame", "--porcelain", "-L", f"{line_no},{line_no}", "--", str(rel_path)],
        cwd=repo_root,
        check=False,
    )
    if not blame:
        return None
    commit_hash = blame.splitlines()[0].split()[0]
    if set(commit_hash) == {"0"}:
        return None  # uncommitted/working-tree line

    email = _git(["log", "-1", "--format=%cE", commit_hash], cwd=repo_root, check=False)
    return email.strip().lower() or None


def _update_directive_options(path, updates, directive_re):
    """Set/replace ``updates`` (option -> value) in the block introduced by
    the first line matching ``directive_re``: existing options are updated
    in place, missing ones appended before the blank line that ends the
    block. Raises if no matching directive is found.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    start = next(
        (i for i, line in enumerate(lines) if directive_re.match(line.rstrip("\n"))),
        None,
    )
    if start is None:
        raise DocctlError(f"No directive matching {directive_re.pattern!r} found in {path}")

    indent = "   "
    found_keys = set()
    end = start + 1
    while end < len(lines):
        stripped = lines[end].rstrip("\n")
        m = OPTION_RE.match(stripped)
        if not m:
            break
        indent = m.group("indent")
        key = m.group("key")
        found_keys.add(key)
        if key in updates:
            lines[end] = f"{indent}:{key}: {updates[key]}\n"
        end += 1

    missing = [k for k in updates if k not in found_keys]
    if missing:
        new_lines = [f"{indent}:{k}: {updates[k]}\n" for k in missing]
        lines[end:end] = new_lines

    path.write_text("".join(lines), encoding="utf-8")


def _update_doc_control(path, updates):
    """Set/replace ``updates`` (option -> value) in the file's
    ``.. doc_control::`` block: existing options are updated in place,
    missing ones appended before the blank line that ends the block.
    """
    _update_directive_options(path, updates, DOC_CONTROL_RE)


def _remove_doc_control_fields(path, keys):
    """Delete whichever of ``keys`` are currently set in ``path``'s
    ``.. doc_control::`` block outright (not just blank their value) — used
    by ``bump-version`` to reset author/review/approval back to "not set"
    for a new version cycle, so doc_control.py's own "not-authored-yet"/
    "not-reviewed-yet"/"not-approved-yet" placeholders take over again
    instead of rendering an empty cell.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    start = next(
        (i for i, line in enumerate(lines) if DOC_CONTROL_RE.match(line.rstrip("\n"))),
        None,
    )
    if start is None:
        raise DocctlError(f"No '.. doc_control::' directive found in {path}")

    end = start + 1
    keep = []
    while end < len(lines):
        m = OPTION_RE.match(lines[end].rstrip("\n"))
        if not m:
            break
        if m.group("key") not in keys:
            keep.append(lines[end])
        end += 1

    lines[start + 1 : end] = keep
    path.write_text("".join(lines), encoding="utf-8")


def _update_git_changelog_rev_list(doc_file, rev_range):
    """Point ``doc_file``'s ``.. git_changelog::`` directive's
    ``:rev-list:`` at ``rev_range`` — used by ``bump-version`` so the
    rendered change history restarts from the previous release instead of
    an arbitrary window of recent commits (see sphinx_git's own default:
    the last 10 commits repo-wide, filtered by ``filename_filter`` — a
    range with no bound at all if this document hasn't been touched
    recently). Returns False (no-op) if this document has no
    ``.. git_changelog::`` directive to begin with — not every document
    necessarily has one, and that's not this command's problem to fix.
    """
    if _read_directive_options(doc_file, GIT_CHANGELOG_RE) is None:
        return False
    _update_directive_options(doc_file, {"rev-list": rev_range}, GIT_CHANGELOG_RE)
    return True


def _git(args, cwd, check=True):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise DocctlError(f"'git {' '.join(args)}' failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def _git_identity(repo_root):
    name = _git(["config", "user.name"], cwd=repo_root)
    email = _git(["config", "user.email"], cwd=repo_root)
    if not name or not email:
        raise DocctlError(
            "git user.name/user.email are not configured — set them (git config "
            "user.name / user.email) before running docctl"
        )
    return f"{name} <{email}>"


def _commit(repo_root, path, subject, identity, trailer_key=None):
    """Stage ``path`` and commit signed-off (``-s``) and GPG-signed (``-S``).
    ``-s`` already appends a ``Signed-off-by:`` trailer using ``identity``;
    pass ``trailer_key`` to additionally record a distinct action (e.g.
    "Reviewed-by") when a plain Signed-off-by doesn't say enough on its own.
    """
    _git(["add", "--", str(path)], cwd=repo_root)
    message = f"{subject}\n"
    if trailer_key:
        message += f"\n{trailer_key}: {identity}\n"
    _git(["commit", "-s", "-S", "-m", message], cwd=repo_root)
    sha = _git(["rev-parse", "--short", "HEAD"], cwd=repo_root)
    print(f"Committed {sha}: {subject}")


def _tag(repo_root, name, message):
    """Signed tag (``-s`` — see SOP-DOCCTL's "Released Versions") on HEAD."""
    _git(["tag", "-s", name, "-m", message], cwd=repo_root)
    print(f"Tagged {name}")


def _resolve(args):
    """(doc_file, repo_root, identity) for args.document_id."""
    registry_path = args.registry.resolve()
    data = _load_registry(registry_path)
    confdir = _confdir_for(registry_path, args.document_id, data)
    doc_file = _find_doc_control_file(confdir)
    repo_root = registry_path.parent
    identity = _git_identity(repo_root)
    return doc_file, repo_root, identity


def _subject(action, document_id, version):
    """Commit subject line: "docs(<document-id>): <Action> version <version>",
    (if known) — e.g. "docs(sop-docctl): Approve version 1.0".
    """
    subject = f"docs({document_id}): {action}"
    return f"{subject} version {version}" if version else subject


def cmd_list(args):
    """document-ids that author/review/approve can actually operate on —
    i.e. resolve to a confdir containing exactly one ``.. doc_control::``
    (see _find_doc_control_file). Registry entries that don't (missing
    confdir, no directive, or an ambiguous multi-directive project) are
    silently excluded: they aren't valid targets for the other subcommands.
    """
    registry_path = args.registry.resolve()
    data = _load_registry(registry_path)

    ids = []
    for document_id in data.get("documents", {}):
        try:
            confdir = _confdir_for(registry_path, document_id, data)
            _find_doc_control_file(confdir)
        except DocctlError:
            continue
        ids.append(document_id)

    for document_id in sorted(ids):
        print(document_id)


def cmd_author(args):
    doc_file, repo_root, identity = _resolve(args)
    existing = _read_doc_control(doc_file)

    updates = {"author": identity}
    if args.doc_version:
        updates["version"] = args.doc_version

    _update_doc_control(doc_file, updates)
    print(f"Updated {doc_file}: " + ", ".join(f"{k} = {v}" for k, v in updates.items()))

    version = args.doc_version or existing.get("version", "")
    _commit(
        repo_root,
        doc_file,
        _subject("Author", args.document_id, version),
        identity,
    )


def cmd_review(args):
    doc_file, repo_root, identity = _resolve(args)
    existing = _require(doc_file, args.document_id, "author", "author")

    if not args.force:
        author_email = _field_committer_email(repo_root, doc_file, "author")
        if author_email and author_email == _identity_email(identity):
            raise DocctlError(
                f"the 'author' commit for {args.document_id} was made by you "
                f"({author_email}) — a reviewer must be a different person "
                "from the author (pass --force to override)"
            )

    _update_doc_control(doc_file, {"reviewed_by": identity})
    print(f"Updated {doc_file}: reviewed_by = {identity}")

    _commit(
        repo_root,
        doc_file,
        _subject("Review", args.document_id, existing.get("version", "")),
        identity,
        "Reviewed-by",
    )


def cmd_approve(args):
    doc_file, repo_root, identity = _resolve(args)

    if not args.force:
        existing = _require(doc_file, args.document_id, "reviewed_by", "review")
        if not _field_committer_email(repo_root, doc_file, "reviewed_by"):
            raise DocctlError(
                f"{doc_file}'s 'reviewed_by' isn't backed by a commit — run "
                f"`docctl review {args.document_id}` and commit it first "
                "(pass --force to override)"
            )
    else:
        existing = _read_doc_control(doc_file)

    version = existing.get("version", "")
    if not version:
        raise DocctlError(
            f"{doc_file} has no 'version' set — cannot create the release "
            f"tag '{args.document_id}/<version>' without one"
        )

    approval_date = datetime.date.today().isoformat()
    updates = {"approved_by": identity, "approval_date": approval_date}

    if args.effective_date:
        if not DATE_RE.match(args.effective_date):
            raise DocctlError(f"--effective-date must be YYYY-MM-DD, got: {args.effective_date!r}")
        if args.effective_date < approval_date:
            raise DocctlError(
                f"--effective-date ({args.effective_date}) must be >= "
                f"approval_date ({approval_date})"
            )
        updates["effective_date"] = args.effective_date

    _update_doc_control(doc_file, updates)
    print(f"Updated {doc_file}: " + ", ".join(f"{k} = {v}" for k, v in updates.items()))

    subject = _subject("Approve", args.document_id, version)
    _commit(repo_root, doc_file, subject, identity, "Approved-by")
    _tag(repo_root, f"{args.document_id}/{version}", subject)


def _bump(version, major):
    """New ``major.minor`` version string: ``--major`` increments the major
    component and resets minor to 0; otherwise (default) the minor
    component is incremented. Raises if ``version`` isn't already
    ``major.minor`` — e.g. a Record's own edition numbering, which
    bump-version doesn't apply to (see cmd_bump_version's own check).
    """
    m = VERSION_RE.match(version)
    if not m:
        raise DocctlError(
            f"current version {version!r} is not 'major.minor' — bump-version "
            "only applies to major.minor-versioned controlled documents"
        )
    maj, min_ = int(m.group(1)), int(m.group(2))
    return f"{maj + 1}.0" if major else f"{maj}.{min_ + 1}"


def cmd_bump_version(args):
    doc_file, repo_root, identity = _resolve(args)
    existing = _read_doc_control(doc_file)

    if existing.get("classification") == "Record":
        raise DocctlError(
            f"{args.document_id} is classified as a Record — Records use their "
            "own edition-per-folder versioning, not major.minor bump-version "
            "(see SOP-DOCCTL's Version Numbering)"
        )

    old_version = existing.get("version", "")
    new_version = _bump(old_version, args.major)

    _update_doc_control(doc_file, {"version": new_version})
    _remove_doc_control_fields(doc_file, {"author", "reviewed_by", "approved_by", "approval_date"})

    changelog_note = ""
    old_tag = f"{args.document_id}/{old_version}"
    if _git(["rev-parse", "--verify", "--quiet", old_tag], cwd=repo_root, check=False):
        rev_range = f"{old_tag}..HEAD"
        if _update_git_changelog_rev_list(doc_file, rev_range):
            changelog_note = f"; git_changelog rev-list = {rev_range}"

    print(
        f"Updated {doc_file}: version = {new_version}; cleared author, "
        f"reviewed_by, approved_by, approval_date{changelog_note}"
    )

    subject = _subject(f"Bump version to {new_version}", args.document_id, None)
    _commit(repo_root, doc_file, subject, identity)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="docctl", description="Review/approve controlled documents."
    )
    parser.add_argument(
        "--registry",
        type=Path,
        required=True,
        metavar="documents.yaml",
        help="registry file to resolve document-ids against (required: this "
        "script ships with zdocs, which has no documents of its own)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser(
        "list", help="list document-ids that author/review/approve can operate on"
    )
    p_list.set_defaults(func=cmd_list)

    p_author = sub.add_parser("author", help="set author and commit")
    p_author.add_argument("document_id", help="registry id of the document to author")
    p_author.add_argument(
        "--version",
        dest="doc_version",
        metavar="VERSION",
        help="also overwrite the document's version on the doc_control directive",
    )
    p_author.set_defaults(func=cmd_author)

    p_review = sub.add_parser("review", help="set reviewed_by and commit")
    p_review.add_argument("document_id", help="registry id of the document to review")
    p_review.add_argument(
        "--force",
        action="store_true",
        help="allow reviewing a document whose 'author' commit is your own (normally refused)",
    )
    p_review.set_defaults(func=cmd_review)

    p_approve = sub.add_parser("approve", help="set approved_by/approval_date and commit")
    p_approve.add_argument("document_id", help="registry id of the document to approve")
    p_approve.add_argument(
        "--effective-date",
        metavar="YYYY-MM-DD",
        help="also set effective_date on the doc_control directive",
    )
    p_approve.add_argument(
        "--force",
        action="store_true",
        help="allow approving a document whose 'reviewed_by' isn't backed by "
        "a commit (normally refused)",
    )
    p_approve.set_defaults(func=cmd_approve)

    p_bump = sub.add_parser(
        "bump-version",
        help="start a new version cycle: bump version, clear author/review/"
        "approval, rebase the change history",
    )
    p_bump.add_argument("document_id", help="registry id of the document to bump")
    bump_group = p_bump.add_mutually_exclusive_group()
    bump_group.add_argument(
        "--major", action="store_true", help="bump the major version (X.y -> X+1.0)"
    )
    bump_group.add_argument(
        "--minor",
        action="store_true",
        help="bump the minor version (x.Y -> x.Y+1) — default",
    )
    p_bump.set_defaults(func=cmd_bump_version)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except DocctlError as e:
        print(f"docctl: error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
