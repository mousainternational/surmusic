// © 2026 Mousa International Software House. All rights reserved.
// Podcast rows (cover picture + name) on the page, in order, like a podcast app. Each cover opens the show on this site.
(function () {
  "use strict";
  function fill(row) {
    if (row.getAttribute("data-done")) return; row.setAttribute("data-done", "1");
    fetch("/api/podcasts/c/" + encodeURIComponent(row.getAttribute("data-slug")), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : { items: [] }; })
      .then(function (d) {
        var items = (d.items || []), seen = {}, box = row.querySelector(".pr-scroll"), n = 0;
        items.forEach(function (it) {
          var k = String(it.a || it.n).toLowerCase(); if (seen[k] || n >= 14) return; seen[k] = 1; n++;
          var a = document.createElement("a"); a.className = "pr-card"; a.href = "/podcasts/" + encodeURIComponent(it.i); a.setAttribute("role", "listitem");
          var pic = document.createElement("span"); pic.className = "pr-pic"; pic.setAttribute("data-letter", (it.n || "?").charAt(0).toUpperCase());
          if (it.m && /^https:\/\//.test(it.m)) { var g = document.createElement("img"); g.src = it.m; g.alt = ""; g.width = 120; g.height = 120; g.loading = "lazy"; g.decoding = "async"; g.referrerPolicy = "no-referrer"; pic.appendChild(g); }
          var t = document.createElement("span"); t.className = "pr-name"; t.textContent = it.n;
          a.appendChild(pic); a.appendChild(t); box.appendChild(a);
        });
        if (n) row.hidden = false;
      }).catch(function () { /* the row simply stays hidden */ });
  }
  function init() {
    var rows = document.querySelectorAll(".pr-row"); if (!rows.length) return;
    var all = function () { rows.forEach(fill); };
    var host = document.querySelector(".pr-rows");
    if (!window.IntersectionObserver || !host) { all(); return; }
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); all(); } }); }, { rootMargin: "600px 0px" });
    io.observe(host);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  document.addEventListener("page:load", init);
})();
