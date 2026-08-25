0007. Doxygen XML is engine-managed, and lives outside the servable tree
========================================================================

Status
------

Accepted.

Context
-------

Doxygen's XML output is not documentation. It is a machine-readable
intermediate that the test-specification extension parses to turn annotated C
into rendered test cases — useful to the build, meaningless to a reader, and
sizeable.

Decision
--------

The engine controls both ``GENERATE_XML`` and ``XML_OUTPUT``. XML is a
**project-scoped opt-in** through a single top-level registry key, and lands
outside the servable tree, at ``deploy/xml/<name>/``.

"Opt-in" here means the engine decides in **both** directions. Because
consumer doxyfiles already ask for XML, enabling-only-when-asked would be a
no-op; the engine has to force it off for a document whose own doxyfile says
yes. That distinction — the engine deciding, versus the engine relocating what
the consumer already asked for — is what the test for the absent key pins.

Consequences
------------

- The servable tree contains no XML, asserted directly rather than inferred.
- ``XML_OUTPUT`` must be an absolute path. Verified against Doxygen with a
  control: a relative value lands inside the output directory, an absolute one
  lands where asked.
- A Doxygen document's clean target removes two paths unconditionally, because
  a document can turn XML off across a re-configure and the previously
  generated XML must still go. This is exactly where the previous decision's
  "a Doxygen document has one output location" reasoning stops holding.
- The factory asks the registry for the key itself rather than being handed it
  by the dispatcher, because the factory is also called by hand and a value
  passed down would leave that path blind. A failure to read the key is fatal,
  never read as "off".
