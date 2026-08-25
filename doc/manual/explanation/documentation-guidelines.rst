Documentation guidelines
========================

The rules this documentation set follows, stated as norms — a checklist for
anyone, human or otherwise, writing or reviewing a page here. See
:doc:`coding-guidelines` for the equivalent conventions covering code.

Format
------

- **reStructuredText only** — no Markdown, no MyST, anywhere under ``doc/``.
- Documentation lives in ``doc/`` (singular), and is built by zdocs itself
  through the same registry and the same CMake surface any consumer uses.
- **Every page is reachable from a toctree.** No orphan pages, no dangling
  references.
- The gate is the engine's own ``doc-check`` target plus a clean stage-two
  build log — not ``sphinx-build -W``, which the two-stage build's deliberate
  stage-one warnings would fight. See
  :doc:`decisions/0011-documentation-structure`.

Structure
---------

Every page lives in one of the four `Diátaxis <https://diataxis.fr/>`_
quadrants, decided *before* writing rather than after:

- **Tutorial** — learning by doing: a guided path to a working result.
- **How-to guide** — a task recipe for someone who already knows their way
  around.
- **Reference** — facts to look up: precise, complete, no narrative.
- **Explanation** — understanding: why something is built the way it is.

Two documents
-------------

The manual holds the Diátaxis tree; the companion API document holds generated
reference. The line between them is the *kind* of reference, not the subject:

- **Task-facing reference belongs to the manual** — the ``ZDOCS_*`` contract,
  the registry schema, the directives an author writes, the command-line tools.
  A reader consults these to *use* zdocs.
- **Implementation reference belongs to the API document** — module and
  command signatures, extracted from docstrings and from the CMake sources
  themselves. A reader consults these to *change* zdocs.

Nothing is written in both. A manual page needing a signature links to it.

Architecture pages
------------------

The architecture record is an **arc42-lite** page set under
``explanation/architecture/``: introduction and goals, system context, solution
strategy, building blocks, cross-cutting concepts — one page each. System
context and building blocks each carry a **C4-style diagram** rendered from
source with ``.. graphviz::`` (context = level 1, building blocks = level 2),
so diagrams stay text-diffable and cannot rot into out-of-date screenshots.

Facts only
----------

Architecture pages state what **is**, in present tense. Rationale, history,
alternatives considered and provenance live in :doc:`decisions/index`, not in
the architecture prose. There is no "what this is not" section: a deferral
worth recording becomes one positive clause, or a line in the relevant ADR,
never a standalone negative-space essay.

Honesty about maturity
----------------------

- Anything not yet implemented is explicitly hedged as a **design target** —
  say so on the page; do not let present-tense prose imply otherwise.
- Never promise a page or a feature that does not exist. Link only to what is
  actually written.
- A known defect, a parked decision or a deliberate piece of debt is worth
  documenting where a reader would trip over it. Documenting a rough edge is
  not an admission; hiding it is how a reader loses a day.

Vocabulary
----------

- The glossary owns nuanced terminology. Define a term once, in
  :doc:`../reference/glossary`, and never restate that definition elsewhere.
  Use ``:term:`` where a reader meeting the word needs the definition to
  follow the sentence — typically its first use on a page aimed at newcomers.
  Reference and explanation pages written for a reader already fluent in the
  vocabulary do not need to link every occurrence; linking everything is as
  unreadable as linking nothing.
- Write for a developer who knows CMake and Zephyr but has never built a
  multi-document, multi-toolchain documentation set. Sphinx and Doxygen
  concepts get named and explained; embedded concepts do not.
- Distinguish the **engine's** vocabulary from a **consumer's** throughout.
  Type and link names in examples are the consumer's, and an example that
  silently uses the engine's defaults teaches the wrong lesson.

ADRs
----

Architecture decisions are numbered rST files under
``explanation/decisions/``, each with Status, Context, Decision and
Consequences sections. To record one: copy the most recent, take the next
sequential number, and ship it in the same change that implements the decision
— not as a documentation-only change afterwards. ADRs are immutable records of
a decision made at a point in time: a later change that revisits a decision
supersedes it with a new ADR rather than rewriting the old one.
