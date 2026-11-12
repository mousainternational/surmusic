// © 2026 Mousa International Software House. All rights reserved.
// Podcast rows (cover picture + name) on the page, in order, like a podcast app. Each cover opens the show on this site.
(function () {
  "use strict";
  function faithSlug(row) {                    // the religious row: a guess from the country, always changeable, remembered in this browser
    return fetch("/api/podcasts/near", { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (d) {
      var saved = ""; try { saved = localStorage.getItem("sm-faith") || ""; } catch (e) { /* ignore */ }
      var list = d.faiths || [], cur = list.some(function (f) { return f.slug === saved; }) ? saved : d.faith;
      var sel = row.querySelector("select");
      if (sel && !sel.options.length) {
        list.forEach(function (f) { var o = document.createElement("option"); o.value = f.slug; o.textContent = f.name; sel.appendChild(o); });
        sel.value = cur;
        sel.addEventListener("change", function () {
          try { localStorage.setItem("sm-faith", sel.value); } catch (e) { /* ignore */ }
          row.removeAttribute("data-done"); row.querySelector(".pr-scroll").textContent = ""; fill(row);
        });
      }
      if (sel) cur = sel.value;
      var h = row.querySelector("h2"), name = (list.filter(function (f) { return f.slug === cur; })[0] || {}).name || "";
      if (h) h.textContent = cur === "faiths" ? "Religion & spirituality" : name + " podcasts";
      var a = row.querySelector(".section-head a"); if (a) a.href = "/podcasts/c/" + cur;
      return cur;
    }).catch(function () { return "faiths"; });
  }
  function slugOf(row) {                       // "near" = the chart of the visitor's own country
    var s = row.getAttribute("data-slug");
    if (s === "faith") return faithSlug(row);
    if (s !== "near") return Promise.resolve(s);
    return fetch("/api/podcasts/near", { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (d) {
      var h = row.querySelector("h2"); if (h && d.title) h.textContent = d.title;
      var a = row.querySelector(".section-head a"); if (a) a.href = "/podcasts/c/" + d.slug;
      return d.slug;
    }).catch(function () { return "top-world"; });
  }
  function fill(row, tries) {
    if (row.getAttribute("data-done")) return; row.setAttribute("data-done", "1"); tries = tries || 0;
    slugOf(row).then(function (slug) { return fetch("/api/podcasts/c/" + encodeURIComponent(slug), { credentials: "same-origin" }); })
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
        else if (tries < 3) setTimeout(function () { row.removeAttribute("data-done"); fill(row, tries + 1); }, 12000);   // a list that is still being prepared: ask again
      }).catch(function () { /* the row simply stays hidden */ });
  }
  function init() {
    var rows = document.querySelectorAll(".pr-row"); if (!rows.length) return;
    var all = function () { rows.forEach(function (r) { fill(r, 0); }); };
    var host = document.querySelector(".pr-rows");
    if (!window.IntersectionObserver || !host) { all(); return; }
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); all(); } }); }, { rootMargin: "600px 0px" });
    io.observe(host);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  document.addEventListener("page:load", init);
})();
