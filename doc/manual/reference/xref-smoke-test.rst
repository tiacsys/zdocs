Cross-reference smoke test
==========================

This page exists to be checked, not read. Every bullet below exercises one
cross-reference channel this documentation set uses, and ``doccheck``'s
smoke-page check (see :doc:`cli`) fails the build if any of them renders as
plain text or as nothing at all.

That is not a hypothetical failure mode. A parse-time role whose target
inventory was not built yet emits **no output whatsoever** — not a broken link,
not a warning worth noticing — and a reference into a target that has gone
missing degrades to ordinary prose. Both look completely normal on the page.
The registry names this page in its ``xref_smoketest:`` field, and the check
asserts that every bullet here came out as a real link.

If you are reading this because a bullet failed: the channel named in the
failing bullet is broken, and the page it points into is where to look.

- Companion document: :external+zdocs-api:doc:`index`
- Python module: :external+zdocs-api:py:mod:`docrefs`
- Python function: :external+zdocs-api:py:func:`docrefs.load`
- Shared Sphinx configuration: :external+zdocs-api:py:func:`zdocs_conf.configure`
- CMake command, Sphinx factory: :external+zdocs-api:cmake:command:`add_sphinx_target <command:add_sphinx_target>`
- CMake command, registry dispatch: :external+zdocs-api:cmake:command:`add_docs_from_registry <command:add_docs_from_registry>`
- Same-document reference: :doc:`registry-schema`
- Glossary term: :term:`deploy tree`
