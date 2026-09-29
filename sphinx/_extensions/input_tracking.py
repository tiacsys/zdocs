# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: track a document's inputs from outside the source tree.

The testmodule, testreport, twisterinfo and symbolneeds directives read files
Sphinx knows nothing about: Doxygen XML, twister's XML/JSON, a spec's
needs.json. Sphinx re-reads a document only when a tracked input is missing or
NEWER than the document's last read. That is not enough here: twister output
often arrives with an older mtime (a CI artifact or cache restored with its
timestamps, a copy that preserves them), and the report then stays stale
without a warning. So each input's signature is recorded at read time, and a
document is re-read whenever a signature differs, in either direction.

Loaded by the extensions that use it (``app.setup_extension``), which Sphinx
does once however many ask.
"""

import os


def _input_signature(path):
    """(mtime_ns, size) of ``path``, or None if it does not exist."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _note_input(env, path):
    """Track ``path`` as an input of the document being read."""
    path = str(path)
    env.note_dependency(path)
    inputs = getattr(env, "zdocs_report_inputs", None)
    if inputs is None:
        inputs = env.zdocs_report_inputs = {}
    inputs.setdefault(env.docname, {})[path] = _input_signature(path)


def _outdated_by_input_change(app, env, added, changed, removed):
    """``env-get-outdated``: documents whose recorded inputs changed."""
    return [
        docname
        for docname, paths in getattr(env, "zdocs_report_inputs", {}).items()
        if docname not in removed
        and any(_input_signature(path) != sig for path, sig in paths.items())
    ]


def _purge_inputs(app, env, docname):
    getattr(env, "zdocs_report_inputs", {}).pop(docname, None)


def _merge_inputs(app, env, docnames, other):
    theirs = getattr(other, "zdocs_report_inputs", {})
    if not hasattr(env, "zdocs_report_inputs"):
        env.zdocs_report_inputs = {}
    for docname in docnames:
        if docname in theirs:
            env.zdocs_report_inputs[docname] = theirs[docname]


def setup(app):
    app.connect("env-get-outdated", _outdated_by_input_change)
    app.connect("env-purge-doc", _purge_inputs)
    app.connect("env-merge-info", _merge_inputs)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
