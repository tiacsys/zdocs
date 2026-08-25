Decisions
=========

Architecture decision records: numbered, dated, immutable. Each one records a
decision that was actually taken, the situation that forced it, and what the
project has to live with as a result.

An ADR is not revised when the project later changes its mind — a decision that
is revisited gets a **new** ADR that supersedes the old one, so the record
stays a history rather than a snapshot. To add one, copy the most recent file,
take the next sequential number, and ship it in the same change that implements
the decision.

The pages under :doc:`../architecture/index` state what the engine *is*; these
state why it is that. Where an ADR needs more depth than its Consequences
section can carry, it links to the relevant explanation page rather than
repeating it.

.. toctree::
   :maxdepth: 1

   0001-zephyr-module-seam
   0002-acceptance-tests-in-a-consumer-repo
   0003-engine-unit-suite
   0004-registry-as-single-source-of-truth
   0005-remote-document-kinds
   0006-deploy-tree-by-builder
   0007-engine-managed-doxygen-xml
   0008-doxygen-tag-file-name
   0009-need-type-role-mapping
   0010-payload-split-by-tool
   0011-documentation-structure
