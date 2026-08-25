Vendored doxygen-awesome-css
============================

The following files are vendored verbatim from `doxygen-awesome-css
<https://github.com/jothepro/doxygen-awesome-css>`_ (MIT licensed). They were
copied from the zephyr tree (``zephyr/doc/_doxygen/``); update them by
re-copying from there (or from upstream) and keeping their SPDX/MIT headers
intact:

- ``doxygen-awesome.css``
- ``doxygen-awesome-sidebar-only.css``
- ``doxygen-awesome-sidebar-only-darkmode-toggle.css``
- ``doxygen-awesome-darkmode-toggle.js``

The remaining files are zdocs' own and are *not* vendored:

- ``doxygen-header.html`` -- doxygen 1.16.1 default header, plus the
  doxygen-awesome dark-mode toggle wiring and the ``#projectversion`` row.
- ``zdocs-doxygen.css`` -- styling for the markup the header above adds, which
  the vendored theme knows nothing about. Loaded after the theme and before any
  ``ZDOCS_DOXYGEN_EXTRA_CSS``.
- ``cross-doc-nav.css`` / ``cross-doc-nav.js`` -- cross-document sidebar nav.
- ``doxygen-footer.html`` -- doxygen footer that injects the cross-doc nav.

Nothing here may depend on a consumer's stylesheet. Branding is supplied through
``ZDOCS_PROJECT_LOGO`` and ``ZDOCS_DOXYGEN_EXTRA_CSS``, both optional, and the
header must render correctly with neither set. The engine's first consumer hid
``#projectalign`` in its brand overlay, and the header quietly came to rely on
that to suppress a version it rendered twice -- so every *other* project got the
version printed twice.
