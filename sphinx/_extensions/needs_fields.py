# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Optional need fields: set one only where the consumer declared it.

A need type, a link and a field are the consumer's vocabulary
(``needs_config.toml``). The engine can fill some fields the consumer may not
want; setting an undeclared one makes sphinx-needs warn "Unknown option" on
every need. So an optional field is set only when the running sphinx-needs
schema has it, and how it is declared decides whether its value survives.
"""

from sphinx.util import logging

logger = logging.getLogger(__name__)

#: The Kconfig conditions of a test case or API symbol
#: (``@kconfig_depends{<condition>}``), joined with ``"; "``.
DEPENDS_ON = "depends_on"

#: sphinx-needs splits a directive's value for an ``array`` field at these.
_ARRAY_DELIMITERS = frozenset(";|,")


def field_type(env, name):
    """The declared schema type of need field ``name``, or ``None`` if undeclared."""
    try:
        from sphinx_needs.data import SphinxNeedsData

        field = SphinxNeedsData(env).get_schema().get_extra_field(name)
    except Exception:  # no sphinx-needs, or no schema yet: nothing is declared
        return None
    return field.type if field is not None else None


def depends_field(env, conditions, subject):
    """Whether to set ``depends_on`` for ``subject``'s ``conditions``.

    Declare it as a string field: the value is the conditions joined with
    ``"; "``, verbatim. An ``array`` field works too, as long as no condition
    contains one of ``; | ,`` — sphinx-needs would split ``A || B`` or
    ``IS_ENABLED(A, B)`` into pieces — so such a need gets no field and a
    warning instead of a silently wrong value.
    """
    if not conditions:
        return False
    kind = field_type(env, DEPENDS_ON)
    if kind == "string":
        return True
    if kind == "array":
        split = [c for c in conditions if _ARRAY_DELIMITERS & set(c)]
        if split:
            logger.warning(
                f"{subject}: '{DEPENDS_ON}' is declared as an array, which "
                f"sphinx-needs splits at ';', '|' and ',' — not set for "
                f"{split!r}; declare it as a string field"
            )
            return False
        return True
    return False
