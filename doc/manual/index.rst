zdocs
=====

zdocs is a **documentation engine shipped as a Zephyr module**. A project
declares its documents in one registry file, sets a handful of variables, and
gets a build that drives Sphinx and Doxygen together, resolves cross-references
between every document in the set in both directions, and produces a deploy
tree that is published by copying one folder.

.. warning::

   **Pre-release.** The engine is in active development and nothing is
   published yet: the registry schema and the ``ZDOCS_*`` contract may still
   change without a deprecation period. What is documented here is what the
   engine does today, and every page of it is built by the engine itself.

What you get for one registry entry: a two-stage build that makes circular
cross-references resolve, a navigation sidebar shared by both toolchains,
scoped per-document versions from your own git tags, sphinx-needs
requirements traceability, test specifications rendered from annotated C,
controlled-document headers, PDF output, and an integrity check that fails when
a cross-reference has silently degraded to plain text.

This documentation follows the `Diátaxis <https://diataxis.fr/>`_ framework,
organised into four kinds of page:

- **Tutorials** — guided, hands-on lessons that end with something built.
- **How-to guides** — step-by-step recipes for one specific task.
- **Reference** — precise, factual descriptions of the contract, the registry
  schema, the directives and the command-line tools.
- **Explanation** — architecture, mechanisms and the decision record, for
  understanding *why* zdocs is built the way it is.

Generated API reference — every Python module and every CMake command — lives
in a companion document, :external+zdocs-api:doc:`index`, built from the
sources themselves. :doc:`reference/index` is where the two meet: it documents
the surface you write against, and links into the API document for signatures.

.. toctree::
   :maxdepth: 2
   :caption: Tutorials

   tutorials/index

.. toctree::
   :maxdepth: 2
   :caption: How-to guides

   howto/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/index

.. toctree::
   :maxdepth: 2
   :caption: Explanation

   explanation/index
