/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * A preview of the linked need: when the pointer stays on a link in a need
 * card, and the link goes to another need card, a popup shows a copy of that
 * card. The target page is fetched once and kept. A page opened as file://
 * cannot fetch other pages; there only needs on the same page get a preview.
 * The need_cards extension gives the links to a need the class zd-need-ref;
 * the other links (Doxygen pages) get no popup, so no fetch.
 *
 * The popup is styled in zdocs-needs.css (.zd-preview). The need_cards
 * extension adds this file to each page.
 */
(() => {
  "use strict";

  const SHOW_DELAY = 300; // ms the pointer stays on a link before the popup opens
  const HIDE_DELAY = 250; // ms to move the pointer from the link into the popup
  // need_cards gives this class to the links that go to a need.
  const LINKS = "table.need a.zd-need-ref";

  const pages = new Map(); // page URL -> Promise<Document | null>
  let popup = null;
  let link = null; // the link the popup is for, or will be for
  let showTimer = 0;
  let hideTimer = 0;

  function pageUrl(url) {
    const u = new URL(url, location.href);
    u.hash = "";
    return u.href;
  }

  function load(page) {
    if (page === pageUrl(location.href)) return Promise.resolve(document);
    if (!pages.has(page)) {
      pages.set(
        page,
        fetch(page)
          .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
          .then((text) => new DOMParser().parseFromString(text, "text/html"))
          .catch(() => null),
      );
    }
    return pages.get(page);
  }

  // A copy of the card with the id `id` in `doc`, or null if `id` is no card.
  function card(doc, id, page) {
    const found = doc.getElementById(id);
    if (!found || !found.matches("table.need")) return null;
    const copy = found.cloneNode(true);
    // The page has the ids already; the copy keeps none.
    copy.removeAttribute("id");
    copy.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
    if (doc !== document) {
      // Relative to the target page, not to this one.
      copy.querySelectorAll("a[href]").forEach((a) => {
        a.href = new URL(a.getAttribute("href"), page).href;
      });
      copy.querySelectorAll("img[src]").forEach((img) => {
        img.src = new URL(img.getAttribute("src"), page).href;
      });
    }
    return copy;
  }

  function target(a) {
    const url = new URL(a.getAttribute("href"), location.href);
    const id = decodeURIComponent(url.hash.slice(1));
    if (!id) return null;
    // The id link of a card goes to the card itself.
    const own = a.closest("table.need");
    if (own && own.id === id && pageUrl(url.href) === pageUrl(location.href)) return null;
    return { page: pageUrl(url.href), id };
  }

  function ensurePopup() {
    if (popup) return popup;
    popup = document.createElement("div");
    popup.className = "zd-preview";
    popup.setAttribute("role", "tooltip");
    popup.hidden = true;
    popup.addEventListener("mouseenter", () => clearTimeout(hideTimer));
    popup.addEventListener("mouseleave", scheduleHide);
    // In the content area: the card rules of zdocs-needs.css start there.
    (document.querySelector(".rst-content") || document.body).appendChild(popup);
    return popup;
  }

  function place(a) {
    const gap = 6;
    const margin = 16;
    const r = a.getBoundingClientRect();
    const p = popup.getBoundingClientRect();
    const below = window.innerHeight - r.bottom - gap - margin;
    const above = r.top - gap - margin;
    const top = p.height <= below || below >= above ? r.bottom + gap : r.top - gap - p.height;
    const left = Math.min(Math.max(margin, r.left), window.innerWidth - margin - p.width);
    popup.style.top = `${Math.max(margin, top)}px`;
    popup.style.left = `${Math.max(margin, left)}px`;
  }

  function show(a) {
    const t = target(a);
    if (!t) return;
    load(t.page).then((doc) => {
      if (link !== a || !doc) return; // the pointer has gone, or no fetch
      const copy = card(doc, t.id, t.page);
      if (!copy) return;
      ensurePopup();
      popup.replaceChildren(copy);
      popup.scrollTop = 0;
      popup.style.top = "0px";
      popup.style.left = "0px";
      popup.hidden = false;
      place(a);
    });
  }

  function hide() {
    clearTimeout(showTimer);
    link = null;
    if (popup) popup.hidden = true;
  }

  function scheduleHide() {
    clearTimeout(showTimer);
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, HIDE_DELAY);
  }

  function enter(a) {
    clearTimeout(hideTimer);
    if (a === link) return;
    clearTimeout(showTimer);
    if (popup) popup.hidden = true;
    link = a;
    showTimer = setTimeout(() => show(a), SHOW_DELAY);
  }

  // A link in a card, but not one in the popup: no preview of a preview.
  function previewLink(el) {
    const a = el instanceof Element ? el.closest(LINKS) : null;
    return a && !a.closest(".zd-preview") ? a : null;
  }

  function init() {
    document.addEventListener("mouseover", (e) => {
      const a = previewLink(e.target);
      if (a) enter(a);
    });
    document.addEventListener("mouseout", (e) => {
      const a = previewLink(e.target);
      if (a && !a.contains(e.relatedTarget)) scheduleHide();
    });
    document.addEventListener("focusin", (e) => {
      const a = previewLink(e.target);
      if (a) enter(a);
    });
    document.addEventListener("focusout", (e) => {
      if (previewLink(e.target)) scheduleHide();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hide();
    });
    // The popup is fixed; a scroll of the page moves the link away from it.
    document.addEventListener(
      "scroll",
      (e) => {
        if (popup && !popup.hidden && !popup.contains(e.target)) hide();
      },
      true,
    );
  }

  // Only with a pointer that can hover; a tap follows the link.
  if (window.matchMedia("(hover: hover)").matches) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }
})();
