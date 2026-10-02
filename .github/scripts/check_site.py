# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
"""Check the internal links of the assembled Pages site.

Usage: python check_site.py <site dir>

The site is served under a path prefix (https://tiacsys.github.io/zdocs/).
A static server maps a URL to a file, so the check resolves every href and
src of every HTML page against the file system, relative to the page:

- the target file must exist (a directory needs an index.html),
- the target must stay inside the site directory (a link that climbs out
  of it leaves the prefix and fails on GitHub Pages),
- a #fragment on an HTML target must name an id or a name in that page.

A ?query is ignored. Links with a scheme (https:, mailto:, ...) and
protocol-relative links are not checked. The exit status is 1 if there is
a broken link.
"""

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlparse


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ("id", "name"):
            if a.get(key):
                self.ids.add(a[key])
        for key in ("href", "src"):
            if a.get(key):
                self.links.append(a[key])


_PAGES = {}


def parse(path):
    if path not in _PAGES:
        page = Page()
        page.feed(path.read_text(encoding="utf-8", errors="replace"))
        _PAGES[path] = page
    return _PAGES[path]


def main(root):
    root = root.resolve()
    pages = sorted(root.rglob("*.html"))
    broken, checked = [], 0
    for page_path in pages:
        for link in parse(page_path).links:
            url = urlparse(link)
            if url.scheme or url.netloc or link.startswith("#"):
                continue
            checked += 1
            target_ref, fragment = urldefrag(link)
            target_ref = target_ref.split("?", 1)[0]
            if target_ref.startswith("/"):
                broken.append((page_path, link, "absolute path"))
                continue
            target = (page_path.parent / unquote(target_ref)).resolve()
            if not target.is_relative_to(root):
                broken.append((page_path, link, "outside the site"))
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                broken.append((page_path, link, "no such file"))
                continue
            if fragment and target.suffix == ".html" and unquote(fragment) not in parse(target).ids:
                broken.append((page_path, link, "no such #fragment"))
    print(f"check_site: {len(pages)} pages, {checked} internal links, {len(broken)} broken")
    for page_path, link, reason in broken:
        print(f"  {page_path.relative_to(root)}: {link} ({reason})")
    return 1 if broken else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1])))
