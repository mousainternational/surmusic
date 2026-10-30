// Sur Music — site behaviour: menu, theme, in-site navigation that keeps the music playing,
// copy buttons, QR lightbox, password reveal, cookie notice. The site also works without JS.
(function () {
  "use strict";
  var root = document.documentElement;

  // ---------- theme ----------
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  root.setAttribute("data-theme", currentTheme());
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".theme-toggle");
    if (!b) return;
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("sm-theme", next); } catch (err) { /* ignore */ }
  });

  // ---------- mobile menu ----------
  function closeMenu() {
    var menu = document.getElementById("menu"), t = document.querySelector(".nav-toggle");
    if (menu && t) { menu.classList.remove("open"); t.setAttribute("aria-expanded", "false"); t.setAttribute("aria-label", "Open menu"); }
    root.classList.remove("menu-open");
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest(".nav-toggle");
    var menu = document.getElementById("menu");
    if (!t) {
      // tap outside the open menu closes it
      if (menu && menu.classList.contains("open") && !e.target.closest("#menu")) closeMenu();
      return;
    }
    var open = menu.classList.toggle("open");
    t.setAttribute("aria-expanded", open ? "true" : "false");
    t.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    root.classList.toggle("menu-open", open);   // page behind stays still while the menu scrolls
    if (open) menu.scrollTop = 0;
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenu(); });

  // ---------- in-site navigation (keeps the player alive) ----------
  var NO_SWAP = /^\/(admin|account|login|signup|logout|forgot|reset|verify|download\/|media\/|api\/|static\/|ads\.txt|robots\.txt|sitemap\.xml)/;
  function swappable(url) {
    if (url.origin !== location.origin) return false;
    if (NO_SWAP.test(url.pathname)) return false;
    return !document.body.classList.contains("admin") && !document.body.classList.contains("page-auth");
  }
  function replaceHead(doc) {
    document.title = doc.title;
    ["meta[name=description]", "meta[name=robots]", "link[rel=canonical]", "meta[property='og:title']",
     "meta[property='og:description']", "meta[property='og:url']"].forEach(function (sel) {
      var cur = document.head.querySelector(sel), nxt = doc.head.querySelector(sel);
      if (cur && nxt) cur.replaceWith(nxt.cloneNode(true));
      else if (cur && !nxt) cur.remove();
      else if (!cur && nxt) document.head.appendChild(nxt.cloneNode(true));
    });
    document.head.querySelectorAll("script[type='application/ld+json']").forEach(function (s) { s.remove(); });
    doc.head.querySelectorAll("script[type='application/ld+json']").forEach(function (s) {
      var n = document.createElement("script"); n.type = "application/ld+json"; n.textContent = s.textContent;
      document.head.appendChild(n);
    });
  }
  // Back / Forward return to where you were on the page (instead of jumping to the top)
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  function rememberScroll() {
    try { history.replaceState(Object.assign({}, history.state, { sm: 1, y: window.scrollY }), ""); } catch (e) { /* ignore */ }
  }
  var saveTimer = null;
  window.addEventListener("scroll", function () {
    if (saveTimer) return;
    saveTimer = setTimeout(function () { saveTimer = null; rememberScroll(); }, 200);
  }, { passive: true });

  var navToken = 0;
  function navigate(href, push, restoreY) {
    var token = ++navToken;
    if (push) rememberScroll();
    document.body.classList.add("is-loading");
    return fetch(href, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } })
      .then(function (r) {
        var ct = r.headers.get("content-type") || "";
        if (!ct.includes("text/html")) throw new Error("not html");
        return r.text().then(function (html) { return { html: html, url: r.url || href }; });
      })
      .then(function (res) {
        if (token !== navToken) return;
        var doc = new DOMParser().parseFromString(res.html, "text/html");
        var newMain = doc.querySelector("main"), newMenu = doc.getElementById("menu");
        if (!newMain || doc.body.classList.contains("admin") || doc.body.classList.contains("page-auth")) {
          location.href = res.url; return;
        }
        document.querySelector("main").replaceWith(newMain);
        var menu = document.getElementById("menu");
        if (menu && newMenu) menu.innerHTML = newMenu.innerHTML;
        document.body.className = doc.body.className;
        var csrf = doc.querySelector("meta[name=csrf-token]"), cur = document.querySelector("meta[name=csrf-token]");
        if (csrf && cur) cur.content = csrf.content;
        replaceHead(doc);
        if (push) history.pushState({ sm: 1, y: 0 }, "", res.url);
        closeMenu();
        window.scrollTo({ top: restoreY || 0, left: 0, behavior: "instant" });
        newMain.focus({ preventScroll: true });
        var sr = document.getElementById("sr-announce");      // tell screen-reader users the page changed
        if (sr) { sr.textContent = ""; setTimeout(function () { sr.textContent = "Page: " + document.title; }, 60); }
        document.dispatchEvent(new Event("page:load"));
      })
      .catch(function () { location.href = href; })
      .finally(function () { document.body.classList.remove("is-loading"); });
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target || a.hasAttribute("download") || a.hasAttribute("data-no-pjax")) return;
    var url = new URL(a.href, location.href);
    if (!swappable(url)) return;
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
    e.preventDefault();
    navigate(url.href, true);
  });
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if ((f.method || "get").toLowerCase() !== "get" || e.defaultPrevented) return;
    var url = new URL(f.action || location.href, location.href);
    if (!swappable(url)) return;
    e.preventDefault();
    url.search = new URLSearchParams(new FormData(f)).toString();
    navigate(url.href, true);
  });
  window.SurNav = function (href) { var u = new URL(href, location.href); if (swappable(u)) navigate(u.href, true); };
  window.addEventListener("popstate", function (e) {
    navigate(location.href, false, e.state && typeof e.state.y === "number" ? e.state.y : 0);
  });

  // ---------- copy buttons ----------
  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", ""); ta.className = "sr";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) { /* ignore */ }
    ta.remove();
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    var el = document.querySelector(btn.getAttribute("data-copy"));
    if (!el) return;
    var text = el.textContent.trim();
    var done = function () { var old = btn.textContent; btn.textContent = "Copied ✓"; setTimeout(function () { btn.textContent = old; }, 1600); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    else { fallbackCopy(text); done(); }
  });

  // ---------- lightbox (QR codes) ----------
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-lightbox-src]");
    if (!b) return;
    var img0 = b.querySelector("img");
    var box = document.createElement("div");
    box.className = "lightbox"; box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true");
    var img = document.createElement("img"); img.src = b.getAttribute("data-lightbox-src"); img.alt = img0 ? img0.alt : "";
    var close = document.createElement("button"); close.className = "btn btn-ghost btn-sm"; close.type = "button"; close.textContent = "Close ✕";
    box.appendChild(img); box.appendChild(close); document.body.appendChild(box); close.focus();
    function shut() { box.remove(); document.removeEventListener("keydown", onKey); b.focus(); }
    function onKey(ev) { if (ev.key === "Escape") shut(); }
    box.addEventListener("click", shut); document.addEventListener("keydown", onKey);
  });

  // ---------- show password ----------
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-show]");
    if (!b) return;
    var input = document.querySelector(b.getAttribute("data-show"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    b.textContent = show ? "Hide" : "Show";
    b.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });

  // ---------- confirm dangerous actions ----------
  document.addEventListener("submit", function (e) {
    var f = e.target.closest("form[data-confirm]");
    if (f && !window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
  }, true);

  // ---------- page-view beacon (Admin → Analytics; sends only the page, time zone and referring site) ----------
  var firstView = true;
  function trackView() {
    if (document.body.classList.contains("admin")) return;
    var meta = document.querySelector("meta[name=csrf-token]");
    var tz = "";
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { tz = ""; }
    fetch("/api/track", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": meta ? meta.content : "" },
      body: JSON.stringify({ path: location.pathname, tz: tz, ref: firstView ? document.referrer : "" })
    }).catch(function () {});
    firstView = false;
  }
  document.addEventListener("page:load", trackView);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", trackView); else trackView();

  // ---------- cookie notice ----------
  function cookieNote() {
    var note = document.getElementById("cookie-note");
    if (!note) return;
    var seen = false;
    try { seen = localStorage.getItem("sm-cookie-ok") === "1"; } catch (e) { seen = false; }
    if (!seen) note.hidden = false;
    var ok = document.getElementById("cookie-ok");
    if (ok) ok.addEventListener("click", function () {
      note.hidden = true;
      try { localStorage.setItem("sm-cookie-ok", "1"); } catch (e) { /* ignore */ }
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", cookieNote); else cookieNote();

  // ---------- "Listen by type": the types this visitor opened before come first (kept only in this browser)
  function myTypes() {
    try { var v = JSON.parse(localStorage.getItem("sm-types") || "[]"); return Array.isArray(v) ? v : []; }
    catch (e) { return []; }
  }
  function personalChips() {
    var head = document.querySelector("[data-topic-page]"), list = myTypes();
    if (head) {
      var slug = head.getAttribute("data-topic-page"), label = head.getAttribute("data-topic-label") || slug;
      if (/^[a-z0-9-]{1,40}$/.test(slug)) {
        list = [{ s: slug, l: label.slice(0, 40), h: location.pathname }].concat(list.filter(function (x) { return x && x.s !== slug; })).slice(0, 5);
        try { localStorage.setItem("sm-types", JSON.stringify(list)); } catch (e) { /* ignore */ }
      }
    }
    var box = document.querySelector("[data-genre-chips] .chips");
    if (!box || !list.length) return;
    for (var i = list.length - 1; i >= 0; i--) {
      var t = list[i];
      if (!t || !/^[a-z0-9-]{1,40}$/.test(t.s) || !/^\/(genre|country)\/[a-z0-9-]{1,60}$/.test(t.h || "")) continue;
      var chip = box.querySelector('[data-topic="' + t.s + '"]');
      if (!chip) {
        chip = document.createElement("a");
        chip.className = "chip"; chip.href = t.h; chip.textContent = t.l; chip.setAttribute("data-topic", t.s);
      }
      chip.classList.add("chip-mine");
      box.insertBefore(chip, box.firstChild);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", personalChips); else personalChips();
  document.addEventListener("page:load", personalChips);
})();
