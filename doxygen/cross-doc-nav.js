// Copyright (c) 2026 inovex GmbH
//
// SPDX-License-Identifier: Apache-2.0

// Cross-document navigation widget for the doxygen HTML.
//
// Reads window.ZDOCS_NAV_LINKS (generated at configure time from
// doc/documents.yaml by scripts/docrefs.py `navlinks`) and injects a grouped
// link list into the doxygen sidebar, so every doxygen site can navigate to the
// other documents in the set — the doxygen counterpart of the sphinx grouped
// document sidebar block. The grouped list is derived from the same registry, so
// both stay in sync automatically. Its shape is:
//   [{ id, title, links: [{ label, href }] }, ...]
document.addEventListener("DOMContentLoaded", function () {
  if (!window.ZDOCS_NAV_LINKS) return;

  var sideNav = document.getElementById("side-nav");
  var navTree = document.getElementById("nav-tree");
  if (!sideNav || !navTree) return;

  // Doxygen writes extra stylesheet links using $relpath^, so the href of the
  // cross-doc-nav.css <link> is the relative path from the current page back to
  // this site's html/ root (e.g. "" at root, "../" one level in).
  var cssLink = document.querySelector('link[href$="cross-doc-nav.css"]');
  if (!cssLink) return;
  var relToHtmlRoot = cssLink.getAttribute("href").replace("cross-doc-nav.css", "");

  // From html/ go up two more levels to reach deploy/:
  //   html/ -> <site-dir>/ -> deploy/
  var prefix = relToHtmlRoot + "../../";

  // Mark the active entry using the absolute CSS URL, which contains the current
  // site directory name (e.g. "/dox-api/").
  var cssAbsHref = cssLink.href;
  function isActive(href) {
    if (/^https?:\/\//.test(href)) return false;
    var siteDir = href.split("/")[0];
    return cssAbsHref.indexOf("/" + siteDir + "/") !== -1;
  }

  var nav = document.createElement("div");
  nav.id = "cross-doc-nav";

  // One caption per group, followed by that group's links.
  window.ZDOCS_NAV_LINKS.forEach(function (group) {
    var caption = document.createElement("div");
    caption.id = "cross-doc-nav-caption";
    caption.textContent = group.title;
    nav.appendChild(caption);

    group.links.forEach(function (entry) {
      var a = document.createElement("a");
      a.textContent = entry.label;
      a.href = /^https?:\/\//.test(entry.href) ? entry.href : prefix + entry.href;
      if (isActive(entry.href)) a.classList.add("active");
      nav.appendChild(a);
    });
  });

  // Place the block BELOW the doxygen content, inside the scrollable nav area —
  // matching the sphinx sidebar, where the document list sits under the toctree.
  // Appending to #nav-tree (not #nav-tree-contents) keeps it out of the subtree
  // that doxygen's navtree.js populates dynamically, so it is not clobbered.
  navTree.appendChild(nav);
});
