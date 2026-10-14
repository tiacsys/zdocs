# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

r"""What the zdocs need cards (``zdocs-needs.css``) need from the build.

**The color of each need type.** A need type in ``needs_config.toml`` has a
``color``; sphinx-needs uses it in need flows. This extension writes
``_static/zdocs-need-types.css`` with one rule per type, so that a card has the
same color as the type has in a flow::

    table.need.need.need.need.needs_type_req { --zd-type: #FDEBD0; }

A type without a color, or with a value that is no CSS color, gets no rule;
its cards stay grey.

**The status and the verdict of each need.** sphinx-needs gives the table of
a need no class for a field value, and CSS cannot read the text. After
sphinx-needs has rendered the needs of a page, the extension adds
``zd-status-<status>`` and ``zd-verdict-<verdict>`` to each need table that
has the field (``zd-status-passed``, ``zd-verdict-partial``), so that the card
can color the pill. The need data does not change.

**A preview of the linked need.** The extension adds ``zdocs-need-preview.js``
to each page. When the pointer stays on a link in a card, and the link goes
to another card, a popup shows a copy of that card. The script fetches the
target page in the browser, so it needs a page served over HTTP; a page
opened as ``file://`` gets previews of the needs on the same page only.

**The card in a PDF.** CSS does not reach LaTeX: there, sphinx-needs writes a
card as a table of grey rows. In a LaTeX build the extension replaces the
table of each zdocs card (layout name ``zdocs...``) with a `zd_need` node, and
writes it with the macros of ``zdocs.sty``::

    \begin{zdneed}{<accent RRGGBB>}
    \zdneedhead{<type>}{<ID>}{<tone>}{<status>}
    \zdneedtitle{<title>}
    <text of the need>
    \zdneedfield{<label>}{<value>}   (each field and link)
    \end{zdneed}

The accent is the type color of the HTML card, made darker. The tone of the
status (``good``, ``bad``, ``gap``, ``none`` or ``accent``) is the color of
the pill in ``zdocs-needs.css``. The links in the card stay links, and the
label of the need stays a LaTeX label, so links into the card still work.
"""

import math
import re
from pathlib import Path

from docutils import nodes

CSS_NAME = "zdocs-need-types.css"
JS_NAME = "zdocs-need-preview.js"
_JS_SOURCE = Path(__file__).resolve().parents[1] / "_static" / JS_NAME

#: A CSS color as needs_config.toml gives it: #rgb(a) / #rrggbb(aa) or a name.
_COLOR = re.compile(r"^(#([0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})|[A-Za-z]+)$")


def type_colors_css(types):
    """The CSS rules for ``types`` (the sphinx-needs ``needs_types`` list)."""
    rules = []
    for need_type in types:
        color = str(need_type.get("color") or "").strip()
        if not _COLOR.match(color):
            continue
        # sphinx-needs: "needs_type_" + the type name without white space.
        name = "".join(need_type["directive"].split())
        # One class more than the default in zdocs-needs.css, so the load
        # order of the two files does not matter.
        rules.append(f"table.need.need.need.need.needs_type_{name} {{ --zd-type: {color}; }}")
    return "\n".join(rules) + "\n"


#: The class of a link in a card that goes to a need: the preview script
#: takes only these links, and so fetches no page that has no card (a
#: Doxygen source listing or API page).
NEED_REF_CLASS = "zd-need-ref"

#: The fields that a card shows as a pill: the engine's status and verdict.
PILL_FIELDS = ("status", "verdict")


def status_class(value, field="status"):
    """The class for ``value`` of ``field``: ``zd-<field>-`` and the value in
    lower case, with each run of other characters than letters and digits as
    one ``-``. ``None`` for no value."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return f"zd-{field}-{slug}" if slug else None


def _add_status_classes(app, doctree, docname):
    from sphinx_needs.data import SphinxNeedsData

    needs = SphinxNeedsData(app.env).get_needs_view()
    for table in doctree.findall(nodes.table):
        if "need" not in table["classes"] or not table["ids"]:
            continue
        try:
            need = needs[table["ids"][0]]
        except KeyError:
            continue
        for field in PILL_FIELDS:
            cls = status_class(need.get(field), field)
            if cls and cls not in table["classes"]:
                table["classes"].append(cls)
        _mark_need_refs(table, needs)


def _mark_need_refs(table, needs):
    """Give each link in ``table`` whose fragment is a need id `NEED_REF_CLASS`."""
    for ref in table.findall(nodes.reference):
        fragment = ref.get("refid") or ref.get("refuri", "").partition("#")[2]
        if fragment and fragment in needs and NEED_REF_CLASS not in ref["classes"]:
            ref["classes"].append(NEED_REF_CLASS)


# -- The card in a PDF ---------------------------------------------------------

#: The tone of a status or verdict value (its class), as zdocs-needs.css
#: colors the pill. Other values have the tone "accent", the type color.
TONES = {
    "good": ("zd-status-passed", "zd-verdict-true"),
    "bad": ("zd-status-failed", "zd-status-error", "zd-verdict-broken"),
    "none": (
        "zd-status-skipped", "zd-status-filtered", "zd-status-blocked", "zd-status-not-run",
        "zd-verdict-unattributed", "zd-verdict-unresolved", "zd-verdict-no-cov",
    ),
    "gap": ("zd-verdict-partial", "zd-verdict-no-impl"),
}


def tone(cls):
    """The tone of the pill class ``cls``."""
    for name, classes in TONES.items():
        if cls in classes:
            return name
    return "accent"


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _to_oklab(r, g, b):
    """OKLab of an sRGB color (each channel 0..1)."""
    r, g, b = (_srgb_to_linear(c) for c in (r, g, b))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def _linear_from_oklab(L, a, b):
    """Linear sRGB of an OKLab color; a channel outside 0..1 is out of gamut."""
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def accent(color):
    """The accent of a card of type color ``color`` (``#rrggbb``, ``#rgb``), as
    ``RRGGBB``; ``None`` for no such color.

    The same as ``--zd-accent`` in zdocs-needs.css: the hue of the type color,
    lightness 0.52 and four times the chroma plus 0.02 (OKLCH), so that a
    pastel type color gives a line that is dark enough on paper. A chroma
    that sRGB cannot show is made smaller until it fits.
    """
    m = re.fullmatch(r"#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})", str(color or "").strip())
    if not m:
        return None
    hexa = m.group(1)
    if len(hexa) == 3:
        hexa = "".join(c * 2 for c in hexa)
    _, a, b = _to_oklab(*(int(hexa[i : i + 2], 16) / 255 for i in (0, 2, 4)))
    chroma, hue = math.hypot(a, b), math.atan2(b, a)
    # A grey has no hue: it stays grey.
    chroma = chroma * 4 + 0.02 if chroma > 1e-3 else 0.0
    while True:
        rgb = _linear_from_oklab(0.52, chroma * math.cos(hue), chroma * math.sin(hue))
        if chroma <= 0 or all(-1e-6 <= c <= 1 + 1e-6 for c in rgb):
            break
        chroma = max(chroma - 0.002, 0.0)
    return "".join(f"{round(_linear_to_srgb(min(max(c, 0.0), 1.0)) * 255):02X}" for c in rgb)


#: The accent of a type without a color: the grey of the HTML card.
DEFAULT_ACCENT = "666666"


class zd_need(nodes.General, nodes.Element):
    """A zdocs card in a LaTeX build. Attributes: ``accent``, ``type_name``,
    ``need_id``, ``tone``, ``pill``. Children: one `zd_need_title`, then the
    text of the need, then one `zd_need_field` for each field and link."""


class zd_need_title(nodes.Part, nodes.TextElement):
    """The title of a card."""


class zd_need_field(nodes.Part, nodes.TextElement):
    """A field or link of a card; attribute ``label``, the value as children."""


def _is_zdocs_card(table):
    return "need" in table["classes"] and any(
        c.startswith("needs_layout_zdocs") for c in table["classes"]
    )


def _row(table, cls):
    for row in table.findall(nodes.row):
        if cls in row["classes"]:
            return row
    return None


def _inline(row, cls):
    if row is None:
        return None
    for node in row.findall(nodes.inline):
        if cls in node["classes"]:
            return node
    return None


def _fields(row):
    """``(label, value nodes)`` of each field and link line of the meta ``row``."""
    if row is None:
        return
    for line in row.findall(nodes.line):
        if next(iter(line.findall(nodes.line, include_self=False)), None) is not None:
            continue  # a line that holds lines
        if not line.astext().strip():
            continue
        label = next((n for n in line.findall(nodes.inline) if "needs_label" in n["classes"]), None)
        if label is not None:
            # <inline needs_<field>><inline needs_label>Label:</inline><value></inline>
            field = label.parent
            value = [n.deepcopy() for n in field.children if n is not label]
            yield label.astext().strip().rstrip(":").strip(), value
            continue
        # A link line: "refined by: " and then the links.
        children = list(line.children)
        if children and isinstance(children[0], nodes.Text) and ":" in children[0]:
            name, _, rest = str(children[0]).partition(":")
            value = ([nodes.Text(rest.lstrip())] if rest.strip() else []) + [
                n.deepcopy() for n in children[1:]
            ]
            yield name.strip(), value
        else:
            yield "", [n.deepcopy() for n in children]


def card_node(table, accents):
    """The `zd_need` for the need ``table`` of a zdocs card; ``accents`` maps the
    ``needs_type_<name>`` class to an accent ``RRGGBB``."""
    head = _row(table, "head")
    type_name = _inline(head, "needs_type_name")
    need_id = table["ids"][0] if table["ids"] else ""
    pill_field = next((f for f in PILL_FIELDS if _inline(head, f"needs_{f}") is not None), None)
    pill = _inline(head, f"needs_{pill_field}") if pill_field else None
    pill_text = pill.astext().strip() if pill is not None else ""
    type_class = next((c for c in table["classes"] if c.startswith("needs_type_")), "")
    card = zd_need(
        ids=list(table["ids"]),
        accent=accents.get(type_class, DEFAULT_ACCENT),
        type_name=type_name.astext().strip() if type_name is not None else "",
        need_id=need_id,
        pill=pill_text,
        tone=tone(status_class(pill_text, pill_field)) if pill_text else "accent",
    )
    title = _inline(head, "needs_title")
    card += zd_need_title("", "", *([n.deepcopy() for n in title.children] if title else []))
    content = _row(table, "content")
    if content is not None:
        for entry in content.findall(nodes.entry):
            card.extend(n.deepcopy() for n in entry.children)
            break
    for label, value in _fields(_row(table, "meta")):
        card += zd_need_field("", "", *value, label=label)
    return card


def _latex_cards(app, doctree, docname):
    if app.builder.format != "latex":
        return
    from sphinx_needs.config import NeedsSphinxConfig

    accents = {}
    for need_type in NeedsSphinxConfig(app.config).types:
        value = accent(need_type.get("color"))
        if value:
            accents["needs_type_" + "".join(need_type["directive"].split())] = value
    for table in list(doctree.findall(nodes.table)):
        if _is_zdocs_card(table):
            table.replace_self(card_node(table, accents))


def visit_zd_need(self, node):
    self.body.append(f"\n\\begin{{zdneed}}{{{node['accent']}}}\n")
    # The target of a link to the need: at the top of the card.
    self.body.append("\\phantomsection" + self.hypertarget_to(node))
    # A long ID (a test result) also breaks after an underscore.
    need_id = self.encode(node["need_id"]).replace("\\_", "\\_\\allowbreak{}")
    self.body.append(
        f"\\zdneedhead{{{self.encode(node['type_name'])}}}"
        f"{{{need_id}}}"
        f"{{{node['tone']}}}{{{self.encode(node['pill'])}}}\n"
    )


def depart_zd_need(self, node):
    self.body.append("\n\\end{zdneed}\n")


def visit_zd_need_title(self, node):
    self.body.append("\\zdneedtitle{")


def depart_zd_need_title(self, node):
    self.body.append("}\n")


def visit_zd_need_field(self, node):
    self.body.append(f"\\zdneedfield{{{self.encode(node['label'])}}}{{")


def depart_zd_need_field(self, node):
    self.body.append("}\n")


def _write(app, exception):
    if exception is not None or app.builder.format != "html":
        return
    from sphinx_needs.config import NeedsSphinxConfig

    static = Path(app.outdir) / "_static"
    static.mkdir(parents=True, exist_ok=True)
    css = type_colors_css(NeedsSphinxConfig(app.config).types)
    path = static / CSS_NAME
    if not path.exists() or path.read_text() != css:
        path.write_text(css)
    # zdocs_conf has the zdocs _static in html_static_path, so the file is
    # there already; a document without zdocs_conf gets it here.
    js = _JS_SOURCE.read_text()
    path = static / JS_NAME
    if not path.exists() or path.read_text() != js:
        path.write_text(js)


def _add_files(app):
    if app.builder.format == "html":
        app.add_css_file(CSS_NAME)
        app.add_js_file(JS_NAME)


def setup(app):
    app.add_node(zd_need, latex=(visit_zd_need, depart_zd_need))
    app.add_node(zd_need_title, latex=(visit_zd_need_title, depart_zd_need_title))
    app.add_node(zd_need_field, latex=(visit_zd_need_field, depart_zd_need_field))
    app.connect("builder-inited", _add_files)
    # After sphinx-needs replaced each need node with its table and resolved
    # the links in it (doctree-resolved at the default priority 500).
    app.connect("doctree-resolved", _add_status_classes, priority=600)
    # After the status classes; pdf_links (900) finds the links in the card.
    app.connect("doctree-resolved", _latex_cards, priority=650)
    # After the HTML builder copied the static files, which it does at the end.
    app.connect("build-finished", _write)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
