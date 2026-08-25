Documents zdocs does not build
==============================

A documentation set almost always references material that lives somewhere
else: an upstream project's manual, a vendor's API reference, a corporate
document behind another URL. zdocs models those as first-class registry
entries — declared, grouped and navigable exactly like local documents — that
simply produce no build target.

There are three of them, and which one to use depends entirely on what the
remote side publishes. The decision record is
:doc:`decisions/0005-remote-document-kinds`; the fields are in
:doc:`../reference/registry-schema`.

``external`` — a link, and nothing more
---------------------------------------

For a document with no machine-readable index at all: a PDF on a share, a
wiki page, a product site. It appears in navigation and is reachable through
the ``:qmsdoc:`` role, which is how a controlled document references another
controlled document that is not part of this set.

No cross-referencing is possible, because there is nothing to cross-reference
against. That is the honest outcome, not a limitation to work around.

``sphinx-external`` — a remote Sphinx site
------------------------------------------

Any Sphinx site publishes ``objects.inv``, so a remote peer can be a full
intersphinx target: ``:external+<prefix>:`` references into it resolve, and
break the build when they are wrong.

The engine does not fetch anything here. It adds the site to
``intersphinx_mapping`` and lets Sphinx's own intersphinx do the work —
mature, cached, retrying machinery that already exists and that no engine code
should be reimplementing.

``doxygen-external`` — a remote Doxygen site
--------------------------------------------

Doxygen has no equivalent capability: a tag file must be a local file. So for
this kind the **engine** downloads it, at build time, in the same stage local
tag files are produced, and stores it under the engine's own conventional name
regardless of what the remote publisher calls it.

That is why this kind needs two separate fields — the site's URL, and the tag
file's URL. Doxygen tag-file names are not standardised the way ``objects.inv``
is, so one cannot be derived from the other, and each is validated
independently so that supplying one never masks forgetting the other.

Because the download is wired into the same stage-one gate every local document
already waits on, existing documents pick up the dependency without any
per-consumer wiring.

The recurring hazard
--------------------

Every one of these kinds means "produces no local build output", and several
places in the engine need to know that. Historically they each asked the
question by comparing against ``external`` alone — so adding a kind silently
missed them.

The most expensive instance built the navigation sidebar shared by both
toolchains: a remote peer's sidebar link rendered as a local URL that would
never exist, with a completely green test suite, because nothing asserted on
where a nav entry actually pointed. When touching this area, audit every place
that asks "is this document local?", not only the dispatch that obviously
needs changing.

Testing without the internet
----------------------------

The test suite never reaches the network. Remote peers in the fixtures are
``file://`` URLs serving checked-in content, which keeps the suite offline,
deterministic and fast; the real upstream URLs appear only in documentation and
comments.
