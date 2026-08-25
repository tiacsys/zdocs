0008. The Doxygen tag file is named ``doxygen.tag``
====================================================

Status
------

Accepted, 2026-08-11.

Context
-------

Every Doxygen document the engine builds emits a tag file under one fixed
name, the way every Sphinx document emits ``objects.inv`` under one fixed name.
The name it emitted was ``zephyr.tag``.

Decision
--------

The engine's own tag file is ``doxygen.tag``, for every Doxygen document, local
or downloaded. Remote tag files keep whatever name their publisher chose — that
is what ``remote-tagfile:`` is for — and are stored locally under the engine's
own name.

Consequences
------------

- The name is shared across two languages and nothing in either makes that
  visible: CMake writes it, Python reads it. The Python sites are one
  module-level constant, and all three files carry a comment naming the other
  two.
