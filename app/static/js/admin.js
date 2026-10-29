// Sur Music admin: bar widths (CSP-safe) and live auto-refresh.
(function () {
  "use strict";

  // Bars: <span class="bl-fill" data-w="73"> → width 73% (set with JS; inline styles are blocked by our CSP)
  function bars(root) {
    (root || document).querySelectorAll("[data-w]").forEach(function (el) {
      var w = Math.max(0, Math.min(100, Number(el.getAttribute("data-w")) || 0));
      el.style.width = (w ? Math.max(w, 2) : 0) + "%";
    });
  }
  bars();

  // Phones: the admin menu scrolls sideways — bring the current page's link into view
  var nav = document.querySelector(".admin-links");
  var cur = nav && nav.querySelector('[aria-current="page"]');
  if (nav && cur && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = Math.max(0, cur.offsetLeft - nav.offsetLeft - 12);

  // Live listeners: refresh every 15 s on pages that have #live-rows
  var body = document.getElementById("live-rows");
  if (!body) return;

  function cell(text, cls) {
    var td = document.createElement("td");
    if (cls) td.className = cls;
    td.textContent = text;
    return td;
  }
  function time(iso) { return (iso || "").slice(11, 16); }

  function render(data) {
    var lc = document.getElementById("live-count"), oc = document.getElementById("online-count");
    if (lc) lc.textContent = data.listening;
    if (oc) oc.textContent = data.online;
    body.textContent = "";
    if (!data.rows.length) {
      var tr0 = document.createElement("tr"), td0 = cell("Nobody is listening right now.", "muted");
      td0.colSpan = 5; tr0.appendChild(td0); body.appendChild(tr0);
    }
    data.rows.forEach(function (r) {
      var tr = document.createElement("tr");
      var who = document.createElement("td");
      if (r.user_id) {
        var a = document.createElement("a");
        a.href = "/admin/users/" + encodeURIComponent(r.user_id);
        a.textContent = r.who;
        who.appendChild(a);
        if (r.email && r.email !== r.who) {
          who.appendChild(document.createElement("br"));
          var em = document.createElement("span"); em.className = "small muted"; em.textContent = r.email;
          who.appendChild(em);
        }
      } else {
        var g = document.createElement("span"); g.className = "muted"; g.textContent = "Guest"; who.appendChild(g);
      }
      var st = document.createElement("td");
      var strong = document.createElement("strong"); strong.textContent = r.station; st.appendChild(strong);
      if (r.category) {
        st.appendChild(document.createElement("br"));
        var c = document.createElement("span"); c.className = "small muted"; c.textContent = r.category; st.appendChild(c);
      }
      tr.appendChild(who);
      tr.appendChild(st);
      tr.appendChild(cell(r.flag + " " + r.place, "nowrap"));
      tr.appendChild(cell(r.device + " · " + r.browser, "small"));
      tr.appendChild(cell(time(r.since) + " (" + r.minutes + " min)", "small nowrap"));
      body.appendChild(tr);
    });
    var up = document.getElementById("live-updated");
    if (up) up.textContent = "updated " + new Date().toLocaleTimeString();
  }

  function refresh() {
    if (document.hidden) return;
    fetch("/admin/live.json", { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(render)
      .catch(function () { var up = document.getElementById("live-updated"); if (up) up.textContent = "connection lost — retrying"; });
  }
  setInterval(refresh, 15000);
  document.addEventListener("visibilitychange", refresh);
})();
