# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""A document's version comes from ITS repository.

A downstream set builds an upstream document through ``doc_dir:`` and names
the upstream west project in ``version_project:``. The Sphinx path ignored
that key and showed the downstream (consuming) repository's version, while the
Doxygen path honoured it; the ``version_project`` result also kept its tag
namespace (``sysreq/v1.0``).

The fixture is a real west workspace (``.west/config`` and a manifest) with two
git repositories, so ``west list`` and ``git describe`` run as in a build.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import docrefs  # noqa: E402

_BIN = str(Path(sys.executable).parent)

MANIFEST = """\
manifest:
  projects:
    - name: upstream
      url: https://example.org/upstream
      path: upstream
  self:
    path: consumer
"""


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.org",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.org",
            "GIT_CONFIG_GLOBAL": os.devnull,
        },
    )


def _repo(path, tags):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "file").write_text(path.name)
    _git(path, "add", "file")
    _git(path, "commit", "-q", "-m", "init")
    for tag in tags:
        _git(path, "tag", "-a", tag, "-m", tag)
    return path


def _sha(repo):
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], text=True
    ).strip()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.delenv("VERSION", raising=False)
    monkeypatch.delenv("ZDOCS_WEST_TOPDIR", raising=False)
    monkeypatch.setenv("PATH", _BIN + os.pathsep + os.environ.get("PATH", ""))
    if not shutil.which("west"):
        pytest.skip("west is not installed")
    consumer = _repo(tmp_path / "consumer", ["sw-req/v3.0"])
    (consumer / "west.yml").write_text(MANIFEST)
    upstream = _repo(tmp_path / "upstream", ["sysreq/v1.0", "stkreq/v2.1"])
    (tmp_path / ".west").mkdir()
    (tmp_path / ".west" / "config").write_text("[manifest]\npath = consumer\nfile = west.yml\n")
    return tmp_path, consumer, upstream


def test_version_scope_alone_reads_the_consuming_repository(workspace):
    _, consumer, _ = workspace
    assert docrefs.resolve_version(scope="sw-req", repo_root=consumer) == "v3.0"


def test_version_project_alone_strips_the_tag_namespace(workspace):
    top, consumer, _ = workspace
    # The nearest tag of the upstream project, without its namespace.
    version = docrefs.resolve_version(project="upstream", repo_root=consumer, west=top)
    assert version in ("v1.0", "v2.1")


def test_version_scope_is_matched_in_the_projects_repository(workspace):
    top, consumer, _ = workspace
    version = docrefs.resolve_version(
        scope="sysreq", project="upstream", repo_root=consumer, west=top
    )
    assert version == "v1.0"


def test_an_unknown_scope_falls_back_to_the_projects_sha(workspace):
    top, consumer, upstream = workspace
    version = docrefs.resolve_version(
        scope="nothing", project="upstream", repo_root=consumer, west=top
    )
    assert version == f"v0.0-dev+g{_sha(upstream)}"


def test_an_unknown_project_falls_back_to_the_consuming_repository(workspace):
    top, consumer, _ = workspace
    version = docrefs.resolve_version(project="missing", repo_root=consumer, west=top)
    assert version == f"v0.0-dev+g{_sha(consumer)}"


def test_the_environment_override_still_wins(workspace, monkeypatch):
    top, consumer, _ = workspace
    monkeypatch.setenv("VERSION", "v9.9")
    assert docrefs.resolve_version(scope="sysreq", project="upstream", west=top) == "v9.9"


def test_document_version_reads_both_keys_and_the_west_topdir_from_the_environment(
    workspace, monkeypatch
):
    top, consumer, _ = workspace
    monkeypatch.setenv("ZDOCS_WEST_TOPDIR", str(top))
    meta = {"version_scope": "stkreq", "version_project": "upstream"}
    assert docrefs.document_version(meta, repo_root=consumer) == "v2.1"


def test_the_version_cli_and_document_version_agree(workspace):
    # The Doxygen side runs the CLI; the Sphinx side calls resolve_version.
    top, consumer, _ = workspace
    registry = top / "documents.yaml"
    registry.write_text(
        "groups:\n  - id: up\n    title: Upstream\n"
        "documents:\n  sysreq:\n    group: up\n    builders: [html]\n"
        "    doc_dir: ../upstream/docs/sysreq\n"
        "    version_scope: sysreq\n    version_project: upstream\n"
    )
    cli = subprocess.run(
        [sys.executable, docrefs.__file__, "version", "sysreq", "--registry", registry,
         "--repo-root", consumer, "--west", top],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert cli == "v1.0"


def test_a_project_without_tags_shows_the_fallback_of_its_sha(workspace):
    # The same text as an unscoped document in the project's own build.
    top, consumer, upstream = workspace
    for tag in ("sysreq/v1.0", "stkreq/v2.1"):
        _git(upstream, "tag", "-d", tag)
    version = docrefs.resolve_version(project="upstream", repo_root=consumer, west=top)
    assert version == f"v0.0-dev+g{_sha(upstream)}"
    assert version == docrefs.resolve_version(repo_root=upstream)
