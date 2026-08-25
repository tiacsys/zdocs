0009. Need types and links are a consumer-supplied role→name mapping
=====================================================================

Status
------

Accepted.

Context
-------

The test-specification extension turns annotated C into sphinx-needs objects:
a test case, the procedure that describes it, the result that reports on it,
and the links between them. It emitted those with hardcoded names —
``test_case``, ``test_procedure``, ``test_result``, linked by ``verifies``,
``result_of`` and ``covers``.

Need types are not the engine's vocabulary to choose. They are methodology
terms a project's quality system dictates, they appear in every rendered page
and every traceability query, and sphinx-needs rejects a need whose type it has
not been told about. Hardcoding them obliges every consumer to declare the
engine's words in its own methodology configuration — an engine constant
imposed on a consumer, which is the pattern the extraction exists to remove.

Decision
--------

The engine keeps the six **roles**; the **names** belong to the consumer. Two
configuration values map one to the other, defaulting to the previous literals
so that an existing project sees no change. Resolution goes through a single
helper with a **per-role** fallback, so a partial mapping — renaming only what
a project cares to rename — works.

Custom **field** names stay literal, deliberately. A need type and a link are
methodology vocabulary; the fields hanging off them are the engine's own data
model. The distinction is visible in a generated needs table, where literal
field names sit beside a mapped link name.

Consequences
------------

- **Every place that emits or queries a name must go through the mapping, and
  one that does not fails silently.** The engine emits its own needs table, and
  a name missed there produces a green build with an empty table rather than an
  error. The same defect recurred later in a module the original change did not
  reach, for the same reason: nothing had ever rendered that output, so nothing
  exposed the literal.
- **The control is the unchanged tests.** Because the defaults equal the old
  literals, an untouched suite passing is what proves the indirection is
  transparent. The tests that override names deliberately share no substring
  with the defaults, so a test cannot pass against an implementation that
  merely mangles a default.
- The rST-building module must not import Sphinx or read the application
  configuration — the mapping is passed in. Its unit tests call it bare, so
  reaching for the application there breaks them.
- A consumer that renames these types must declare the new names in its own
  sphinx-needs configuration. That is the point: the names are theirs.
