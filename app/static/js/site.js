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

  // ---------- Admin messages: select all / delete selected ----------
  function bulkInit() {
    var all = document.getElementById("pick-all"), btn = document.getElementById("bulk-del"), n = document.getElementById("bulk-n");
    if (!all || !btn) return;
    var boxes = function () { return Array.prototype.slice.call(document.querySelectorAll("input[name=ids][form=bulk]")); };
    var update = function () {
      var on = boxes().filter(function (b) { return b.checked; }).length;
      n.textContent = on; btn.disabled = on === 0;
      all.checked = on > 0 && on === boxes().length; all.indeterminate = on > 0 && on < boxes().length;
    };
    all.addEventListener("change", function () { boxes().forEach(function (b) { b.checked = all.checked; }); update(); });
    boxes().forEach(function (b) { b.addEventListener("change", update); });
    update();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bulkInit); else bulkInit();
  document.addEventListener("page:load", bulkInit);

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
      if (!t || t.s === "naat" || t.s === "qawwali" || t.s === "sufi" || !/^[a-z0-9-]{1,40}$/.test(t.s) || !/^\/(genre|country)\/[a-z0-9-]{1,60}$/.test(t.h || "")) continue;
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

/* market prices: fill the gadget and the /markets page, then refresh every minute */
(function () {
  var timer = null, tries = 0;
  function apply(d) {
    var items = (d && d.items) || {}, any = false;
    document.querySelectorAll("[data-market]").forEach(function (row) {
      var it = items[row.getAttribute("data-market")];
      if (!it || !it.text) return;
      any = true;
      row.hidden = false;
      row.querySelector("[data-v]").textContent = it.text;
      var c = row.querySelector("[data-c]");
      if (c) { c.textContent = it.change || ""; c.className = "mk-chg" + (it.dir ? " mk-" + it.dir : ""); }
      var g = row.querySelector("svg.mk-spark");
      if (g) { g.setAttribute("class", "mk-spark" + (it.dir ? " mk-" + it.dir : "")); g.querySelector("polyline").setAttribute("points", it.spark || ""); }
    });
    var tk = document.querySelector("[data-ticker]");
    if (tk) {
      tk.hidden = !tk.querySelector("[data-market]:not([hidden])");
      var set = tk.querySelector("[data-ticker-set]"), old = tk.querySelector(".mk-dup");
      if (old) old.remove();
      if (set && !tk.hidden) {                       /* a second copy makes the strip loop without a gap */
        var dup = set.cloneNode(true);
        dup.removeAttribute("data-ticker-set"); dup.classList.add("mk-dup"); dup.setAttribute("aria-hidden", "true");
        dup.querySelectorAll("[data-market]").forEach(function (a) { a.removeAttribute("data-market"); a.tabIndex = -1; });
        set.parentNode.appendChild(dup);
      }
    }
    document.querySelectorAll("[data-market-section]").forEach(function (sec) {
      if (sec.getAttribute("data-market-section") === "gadget") return;
      sec.hidden = !sec.querySelector("[data-market]:not([hidden])");
    });
    var u = document.querySelector("[data-mk-updated]");
    if (u && d && d.updated) u.textContent = "Updated " + d.updated + ".";
    return any;
  }
  function load() {
    if (document.hidden) {                                   /* tab in the background: no refresh (saves data) */
      document.addEventListener("visibilitychange", function again() {
        if (!document.hidden) { document.removeEventListener("visibilitychange", again); load(); }
      });
      return;
    }
    fetch("/api/markets", { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (d) {
      var ok = apply(d);
      tries++;
      clearTimeout(timer);
      timer = setTimeout(load, ok ? 60000 : (tries < 6 ? 6000 : 120000));
    }).catch(function () { clearTimeout(timer); timer = setTimeout(load, 120000); });
  }
  function init() {
    clearTimeout(timer); tries = 0;
    if (document.querySelector("[data-market]")) load();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  document.addEventListener("page:load", init);
})();

/* floating drop-downs (Language): close when you tap outside or press Escape */
(function () {
  document.addEventListener("click", function (e) {
    document.querySelectorAll("details.pick.float[open], details.hd-dd[open]").forEach(function (d) { if (!d.contains(e.target)) d.removeAttribute("open"); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    document.querySelectorAll("details.pick.float[open], details.hd-dd[open]").forEach(function (d) { d.removeAttribute("open"); var s = d.querySelector("summary"); if (s) s.focus(); });
  });
})();

/* header menus: opening one closes the others; choosing a link closes the menu */
document.addEventListener("toggle", function (e) {
  var d = e.target;
  if (!d.classList || !d.classList.contains("hd-dd") || !d.open) return;
  document.querySelectorAll("details.hd-dd[open]").forEach(function (o) { if (o !== d) o.removeAttribute("open"); });
}, true);


/* the big "Now Playing" player is a separate file: fetched the first time it is wanted (saves data on every other page view) */
(function () {
  function wire() {
    var b = document.getElementById("np-open");
    if (!b || b.getAttribute("data-wired")) return;
    b.setAttribute("data-wired", "1");
    var loading = false, wantOpen = false;
    function load(openAfter) {
      if (openAfter) wantOpen = true;                       // remember a click made while the file is still on its way
      if (window.SurNowPlaying) { if (wantOpen) { wantOpen = false; window.SurNowPlaying.open(); } return; }
      if (loading) return; loading = true;
      var sc = document.createElement("script");
      sc.src = b.getAttribute("data-src");
      sc.onload = function () { b.removeEventListener("click", first, true); if (wantOpen && window.SurNowPlaying) { wantOpen = false; window.SurNowPlaying.open(); } };
      sc.onerror = function () { loading = false; };
      document.head.appendChild(sc);
    }
    function first(e) { e.stopImmediatePropagation(); load(true); }
    b.addEventListener("click", first, true);
    ["pointerenter", "focus", "touchstart"].forEach(function (ev) { b.addEventListener(ev, function () { load(false); }, { once: true, passive: true }); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();
  document.addEventListener("page:load", wire);
})();

// A partner-offer picture that cannot load (wrong or blocked address) is replaced by a small bag icon, never a broken image.
(function () {
  function fix(img) {
    if (!img || !img.parentNode || img.dataset.fixed) return;
    img.dataset.fixed = "1";
    var ph = document.createElement("span");
    ph.className = "offer-ph"; ph.setAttribute("aria-hidden", "true"); ph.textContent = "🛍️";
    img.parentNode.replaceChild(ph, img);
  }
  document.addEventListener("error", function (e) {
    var t = e.target;
    if (t && t.tagName === "IMG" && t.closest && t.closest(".offer")) fix(t);
  }, true);
  document.querySelectorAll(".offer img").forEach(function (img) { if (img.complete && img.naturalWidth === 0) fix(img); });
})();

/* category tabs (Music, News, Sports …): a tab shows its own buttons underneath */
(function () {
  document.addEventListener("click", function (e) {
    var tab = e.target.closest && e.target.closest("[data-nav-tabs] .nt-tab");
    if (!tab) return;
    e.preventDefault(); e.stopPropagation();
    var nav = tab.closest("[data-nav-tabs]"), key = tab.getAttribute("data-tab");
    nav.querySelectorAll(".nt-tab").forEach(function (t) {
      var on = t === tab;
      t.classList.toggle("on", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    nav.querySelectorAll(".nt-sub").forEach(function (p) { p.hidden = p.getAttribute("data-sub") !== key; });
  }, true);
})();


// ---------- "Add to home screen": one small button, shown only when the browser can do it (never a pop-up) ----------
(function () {
  var btn, help, deferred = null;
  function standalone() {
    return (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || window.navigator.standalone === true;
  }
  function init() {
    btn = document.getElementById("a2hs"); help = document.getElementById("a2hs-help");
    if (!btn || standalone()) return;
    var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
    if (ios) btn.hidden = false;
    else if (deferred) btn.hidden = false;
    btn.addEventListener("click", function () {
      if (deferred) {
        deferred.prompt();
        deferred.userChoice.then(function () { deferred = null; btn.hidden = true; }, function () { /* ignore */ });
      } else if (help) {
        help.hidden = !help.hidden;
      }
    });
  }
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); deferred = e;
    var b = document.getElementById("a2hs"); if (b && !standalone()) b.hidden = false;
  });
  window.addEventListener("appinstalled", function () { var b = document.getElementById("a2hs"); if (b) b.hidden = true; });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();


// ---------- world news strip: headlines for the visitor's own country, refreshed by themselves ----------
(function () {
  var bar, track, tries = 0, timer = null;
  function build(items) {
    track.textContent = "";
    var set = document.createElement("div"); set.style.display = "flex";
    items.forEach(function (it) {
      var a = document.createElement("a"); a.className = "nw-item"; a.href = it.u; a.target = "_blank";
      a.rel = "noopener nofollow ugc";
      var b = document.createElement("b"); b.textContent = it.t; b.style.fontWeight = "600";
      a.appendChild(b);
      if (it.s) { var s = document.createElement("i"); s.textContent = it.s; a.appendChild(s); }
      set.appendChild(a);
    });
    track.appendChild(set);
    var dup = set.cloneNode(true); dup.className = "nw-dup"; dup.setAttribute("aria-hidden", "true");
    dup.querySelectorAll("a").forEach(function (a) { a.tabIndex = -1; });
    track.appendChild(dup);
    bar.hidden = false;
    var secs = Math.max(60, Math.min(220, items.length * 9));
    track.style.setProperty("--nw-speed", secs + "s");
  }
  function load() {
    clearTimeout(timer);
    fetch("/api/headlines", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : { items: [] }; })
      .then(function (d) {
        if (d.items && d.items.length) { tries = 0; build(d.items); timer = setTimeout(load, 10 * 60 * 1000); }
        else { tries++; timer = setTimeout(load, tries < 5 ? 8000 : 5 * 60 * 1000); }
      }).catch(function () { timer = setTimeout(load, 5 * 60 * 1000); });
  }
  function init() {
    bar = document.getElementById("nw-ticker"); track = document.getElementById("nw-track");
    if (bar && track) load();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

/* Like / dislike a station (station pages). One vote per visitor; remembered in this browser. */
(function () {
  "use strict";
  function store() { try { return JSON.parse(localStorage.getItem("sm-likes") || "{}"); } catch (e) { return {}; } }
  function save(v) { try { localStorage.setItem("sm-likes", JSON.stringify(v)); } catch (e) {} }
  function paint(box) {
    var mine = store()[box.getAttribute("data-like-uuid")] || 0;
    box.querySelectorAll("[data-like]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(Number(b.getAttribute("data-like")) === mine));
    });
  }
  function paintAll() { document.querySelectorAll("[data-like-uuid]").forEach(paint); }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("[data-like]");
    if (!btn) return;
    var box = btn.closest("[data-like-uuid]"), uuid = box.getAttribute("data-like-uuid");
    var votes = store(), want = Number(btn.getAttribute("data-like"));
    var value = votes[uuid] === want ? 0 : want;
    var meta = document.querySelector("meta[name=csrf-token]"), status = box.querySelector("[data-like-status]");
    fetch("/api/like", { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": meta ? meta.content : "" },
      body: JSON.stringify({ uuid: uuid, value: value }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) { if (status) status.textContent = "Please try again later."; return; }
        if (value) votes[uuid] = value; else delete votes[uuid];
        save(votes);
        box.querySelector('[data-like-count="1"]').textContent = d.likes;
        box.querySelector('[data-like-count="-1"]').textContent = d.dislikes;
        paint(box);
        if (status) status.textContent = value === 1 ? "Thanks, you liked this station." : value === -1 ? "Thanks for your feedback." : "Vote removed.";
      })
      .catch(function () { if (status) status.textContent = "Please try again later."; });
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", paintAll); else paintAll();
  document.addEventListener("page:load", paintAll);
})();


/* header Country / Types menus: their long lists are fetched the first time the menu is opened (or hovered) */
(function () {
  function fill(d) {
    var panel = d.querySelector("[data-lazy]");
    if (!panel || panel.getAttribute("data-loaded")) return;
    panel.setAttribute("data-loaded", "1");
    panel.setAttribute("aria-busy", "true");
    fetch(panel.getAttribute("data-lazy"), { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function (html) {
      panel.innerHTML = html;
    }).catch(function () {
      panel.removeAttribute("data-loaded");                 /* keep the "All ..." link; try again next time */
    }).then(function () { panel.removeAttribute("aria-busy"); });
  }
  document.querySelectorAll("details.hd-dd, details.flag-all").forEach(function (d) {
    if (!d.querySelector("[data-lazy]")) return;
    d.addEventListener("toggle", function () { if (d.open) fill(d); });
    var s = d.querySelector("summary");
    if (s) ["pointerenter", "focus"].forEach(function (ev) { s.addEventListener(ev, function () { fill(d); }, { once: true, passive: true }); });
  });
})();

/* Home drop-downs: choosing a country, language or category opens its page */
document.addEventListener("change", function (e) {
  var el = e.target;
  if (el && el.matches && el.matches("select[data-go]") && el.value && el.value.charAt(0) === "/") window.location.href = el.value;
});

/* A channel logo that does not load is removed, so the coloured letter shows instead of a broken picture */
document.addEventListener("error", function (e) {
  var el = e.target;
  if (el && el.tagName === "IMG" && el.closest && el.closest(".thumb")) el.remove();
  else if (el && el.tagName === "IMG" && el.classList.contains("flagimg")) {      /* flag picture missing: show the flag emoji */
    var t = document.createElement("span"); t.textContent = el.getAttribute("data-emoji") || ""; el.replaceWith(t);
  }
}, true);

/* Type to find: in the header Language / Country / Types lists, and in the channel list of a page.
   A word that starts with what was typed matches (P shows Pakistan, Panama …). */
(function () {
  function words(t) { return (t || "").toLowerCase().split(/[^a-z0-9\u0600-\u06ff]+/).filter(Boolean); }
  function hit(text, q, contains) {
    if (!q) return true;
    var low = (text || "").toLowerCase();
    if (contains && low.indexOf(q) !== -1) return true;
    return words(low).some(function (w) { return w.indexOf(q) === 0; }) || low.indexOf(q) === 0;
  }
  document.addEventListener("input", function (e) {
    var el = e.target;
    if (!el || !el.matches) return;
    var q = (el.value || "").trim().toLowerCase();
    if (el.matches("[data-filter-menu]")) {
      var panel = el.parentNode;
      var lis = panel.querySelectorAll("li");
      var starts = false;                                  /* names that begin with the typed letters come first: P shows Pakistan, not French Polynesia */
      lis.forEach(function (li) { if (q && li.textContent.trim().replace(/^[^a-z\u0600-\u06ff]+/i, "").toLowerCase().indexOf(q) === 0) starts = true; });
      lis.forEach(function (li) {
        var name = li.textContent.trim().replace(/^[^a-z\u0600-\u06ff]+/i, "").toLowerCase();
        li.hidden = starts ? name.indexOf(q) !== 0 : !hit(li.textContent, q, false);
      });
      panel.querySelectorAll("h3").forEach(function (h) {
        var ul = h.nextElementSibling;
        h.hidden = !!q && !!ul && !ul.querySelector("li:not([hidden])");
      });
    } else if (el.matches("[data-filter-list]")) {
      document.querySelectorAll("ul.stations > li.st").forEach(function (li) {
        var n = li.querySelector(".st-name");
        li.hidden = !hit(n ? n.textContent : li.textContent, q, true);
      });
    }
  });
  document.addEventListener("keydown", function (e) {
    var el = e.target;
    if (e.key === "Enter" && el && el.matches && el.matches("[data-filter-menu]")) {
      var a = el.parentNode.querySelector("li:not([hidden]) a");
      if (a) { e.preventDefault(); window.location.href = a.getAttribute("href"); }
    }
  });
})();

/* Radio by country: starts with the main countries, then the list quietly becomes every country (A to Z) so scrolling shows them all */
(function () {
  var grids = document.querySelectorAll(".flag-grid[data-flags-all]");
  if (!grids.length || !window.fetch) return;
  function load() {
    fetch(grids[0].getAttribute("data-flags-all"), { credentials: "same-origin" }).then(function (r) { return r.ok ? r.text() : ""; }).then(function (html) {
      if (!html) return;
      var tmp = document.createElement("div"); tmp.innerHTML = html;
      var src = tmp.querySelector(".flag-grid");
      if (!src || src.children.length < 40) return;
      grids.forEach(function (g) { var top = g.scrollTop; g.innerHTML = src.innerHTML; g.scrollTop = top; });
    }).catch(function () {});
  }
  var done = false;
  function once() { if (done) return; done = true; load(); }
  grids.forEach(function (g) {                       /* load the long list when someone touches the flags, or after a quiet 6 seconds */
    ["pointerenter", "touchstart", "scroll", "focusin"].forEach(function (ev) { g.addEventListener(ev, once, { passive: true, once: true }); });
  });
  setTimeout(once, 6000);
  if (window.IntersectionObserver) {                 /* phones: load the full list as soon as the flags box is close to the screen */
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { once(); io.disconnect(); } }); }, { rootMargin: "600px 0px" });
    grids.forEach(function (g) { io.observe(g); });
  }
})();
