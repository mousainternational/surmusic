// Sur Music — web radio player. Lives in the fixed bar at the bottom and survives in-site navigation.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var audio = $("pl-audio");
  var bar = $("player");
  if (!audio || !bar) return;

  var state = {
    station: null,      // currently selected station
    list: [],           // stations of the list it came from (for next / previous)
    category: "",
    favIds: new Set(),
    loggedIn: false,
    locked: bar.getAttribute("data-locked") === "1"   // sign-in required to listen
  };
  var beatTimer = null;
  var STATUS = {
    idle: "", loading: "Connecting…", playing: "LIVE · Playing now", paused: "Paused",
    error: "This station is offline right now — press Next"
  };

  // ---------- helpers ----------
  function csrf() {
    var m = document.querySelector("meta[name=csrf-token]");
    return m ? m.content : "";
  }
  function api(method, url, body) {
    return fetch(url, {
      method: method, credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
  }
  function local(key, value) {
    try {
      if (value === undefined) return JSON.parse(localStorage.getItem(key) || "null");
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) { return null; }
  }
  function stationFrom(li) {
    try { return JSON.parse(li.getAttribute("data-station")); } catch (e) { return null; }
  }
  function listStations(ul) {
    return Array.prototype.map.call(ul.querySelectorAll(":scope > li.st"), stationFrom).filter(Boolean);
  }

  // ---------- UI ----------
  function setState(s) {
    bar.setAttribute("data-state", s);
    var st = $("pl-status");
    st.textContent = "";
    if (s === "playing") {
      var eq = document.createElement("span");
      eq.className = "eq"; eq.innerHTML = "<i></i><i></i><i></i>";
      st.appendChild(eq);
    }
    st.appendChild(document.createTextNode(STATUS[s] || ""));
    $("pl-play").setAttribute("aria-label", (s === "playing" || s === "loading") ? "Pause" : "Play");
    if ("mediaSession" in navigator) {
      navigator.mediaSession.playbackState = s === "playing" ? "playing" : (s === "paused" ? "paused" : "none");
    }
  }
  function renderNow() {
    var s = state.station;
    $("pl-name").textContent = s ? s.name : "Pick a station to start listening";
    var t = $("pl-thumb");
    t.innerHTML = "";
    if (s && s.favicon) {
      var img = document.createElement("img");
      img.src = s.favicon; img.alt = ""; img.referrerPolicy = "no-referrer";
      img.addEventListener("error", function () { img.remove(); t.textContent = "♪"; });
      t.appendChild(img);
    } else { t.textContent = "♪"; }
    var fav = $("pl-fav");
    var on = !!(s && state.favIds.has(s.uuid));
    fav.classList.toggle("on", on);
    fav.setAttribute("aria-pressed", on ? "true" : "false");
    fav.setAttribute("aria-label", on ? "Remove from favourites" : "Add to favourites");
    markLists();
  }
  function markLists() {
    var cur = state.station ? state.station.uuid : null;
    var playing = bar.getAttribute("data-state");
    document.querySelectorAll("li.st").forEach(function (li) {
      var uuid = li.getAttribute("data-uuid");
      li.classList.toggle("playing", uuid === cur && (playing === "playing" || playing === "loading"));
      var f = li.querySelector(".st-fav");
      if (f) {
        var on = state.favIds.has(uuid);
        f.classList.toggle("on", on);
        f.setAttribute("aria-pressed", on ? "true" : "false");
      }
    });
  }

  // ---------- sign-in box ----------
  function showGate(station) {
    var gate = document.getElementById("login-gate");
    var back = location.pathname + location.search;
    if (station) local("sm-pending", { station: station, category: state.category, path: back });
    if (!gate) { location.href = "/login?next=" + encodeURIComponent(back); return; }
    var q = "?next=" + encodeURIComponent(back);
    document.getElementById("gate-signup").href = "/signup" + q;
    document.getElementById("gate-login").href = "/login" + q;
    if (station) document.getElementById("gate-title").textContent = "Sign in to listen to " + station.name;
    gate.hidden = false;
    document.getElementById("gate-signup").focus();
  }
  function hideGate() { var g = document.getElementById("login-gate"); if (g) g.hidden = true; }
  document.addEventListener("click", function (e) {
    if (e.target.id === "gate-close" || e.target.id === "login-gate") hideGate();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideGate(); });

  // ---------- listening check-ins (Admin → Live now) ----------
  function beat(stop, keepalive) {
    var s = state.station;
    if (!s && !stop) return;
    fetch("/api/heartbeat", {
      method: "POST", credentials: "same-origin", keepalive: !!keepalive,
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
      body: JSON.stringify(stop ? { stop: true } : { station_name: s.name, category: state.category || "" })
    }).catch(function () {});
  }
  function startBeats() { stopBeats(false); beat(false); beatTimer = setInterval(function () { beat(false); }, 60000); }
  function stopBeats(sendStop) {
    if (beatTimer) { clearInterval(beatTimer); beatTimer = null; if (sendStop) beat(true); }
  }
  window.addEventListener("pagehide", function () { if (beatTimer) beat(true, true); });

  // ---------- playback ----------
  function resolveUrl(station) {
    if (station.url) return Promise.resolve(station.url);
    return api("POST", "/api/stream", { station: station }).then(function (r) { return r.url; });
  }
  function play(station, list, category) {
    if (!station) return;
    if (list && list.length) state.list = list;
    if (!state.list.length || !state.list.some(function (s) { return s.uuid === station.uuid; })) {
      // e.g. a station restored after sign-in: use the list on this page that contains it (or the first list)
      var li = document.querySelector('li.st[data-uuid="' + (window.CSS && CSS.escape ? CSS.escape(station.uuid) : station.uuid) + '"]');
      var ul = li ? li.parentElement : document.querySelector("main ul.stations");
      if (ul) { state.list = listStations(ul); if (!category && ul.dataset.cat) state.category = ul.dataset.cat; }
    }
    state.category = category || state.category;
    if (state.locked) { showGate(station); return; }
    if (state.station && state.station.uuid !== station.uuid) stopBeats(false);
    state.station = station;
    local("sm-last", { station: station, category: state.category });
    renderNow();
    setState("loading");
    resolveUrl(station).then(function (url) {
      if (state.station !== station) return;               // user already picked another station
      if (!/^https:\/\//.test(url || "")) { setState("error"); return; }
      audio.src = url;
      audio.volume = Number($("pl-vol").value);
      var p = audio.play();
      if (p && p.catch) p.catch(function (err) { if (err && err.name !== "AbortError") setState("error"); });
    }, function (status) {
      if (status === 401) { state.locked = true; setState("idle"); showGate(station); } else { setState("error"); }
    });
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: station.name, artist: "Sur Music · Live radio", album: station.country || "",
          artwork: station.favicon ? [{ src: station.favicon, sizes: "96x96" }] : []
        });
      } catch (e) { /* older browsers */ }
    }
    api("POST", "/api/play", { station: station, category: state.category }).catch(function () {});
  }
  function pause() {
    audio.pause(); audio.removeAttribute("src"); audio.load();
    stopBeats(true);
    setState("paused"); markLists();
  }
  function toggle() {
    var s = bar.getAttribute("data-state");
    if (s === "playing" || s === "loading") { pause(); return; }
    if (state.station) { play(state.station); return; }
    var first = document.querySelector("ul.stations li.st");
    if (first) play(stationFrom(first), listStations(first.parentElement), first.parentElement.dataset.cat);
  }
  function step(dir) {
    if (!state.list.length) return;
    var i = state.list.findIndex(function (s) { return state.station && s.uuid === state.station.uuid; });
    var next = state.list[(i + dir + state.list.length) % state.list.length];
    play(next);
  }

  audio.addEventListener("playing", function () { setState("playing"); markLists(); if (!beatTimer) startBeats(); });
  audio.addEventListener("waiting", function () { if (audio.src) setState("loading"); });
  audio.addEventListener("error", function () { if (audio.getAttribute("src")) { stopBeats(true); setState("error"); markLists(); } });
  audio.addEventListener("stalled", function () { if (!audio.paused) setState("loading"); });

  $("pl-play").addEventListener("click", toggle);
  $("pl-next").addEventListener("click", function () { step(1); });
  $("pl-prev").addEventListener("click", function () { step(-1); });
  $("pl-vol").addEventListener("input", function (e) { audio.volume = Number(e.target.value); local("sm-volume", audio.volume); });
  $("pl-fav").addEventListener("click", function () { if (state.station) toggleFav(state.station); });

  if ("mediaSession" in navigator) {
    try {
      navigator.mediaSession.setActionHandler("play", toggle);
      navigator.mediaSession.setActionHandler("pause", pause);
      navigator.mediaSession.setActionHandler("nexttrack", function () { step(1); });
      navigator.mediaSession.setActionHandler("previoustrack", function () { step(-1); });
    } catch (e) { /* unsupported action */ }
  }

  // ---------- favourites ----------
  function localFavs() { return local("sm-favs") || []; }
  function toggleFav(st) {
    var on = state.favIds.has(st.uuid);
    if (state.loggedIn) {
      var req = on ? api("DELETE", "/api/favorites/" + encodeURIComponent(st.uuid))
                   : api("POST", "/api/favorites", { station: st });
      req.catch(function () { /* revert on failure */ if (on) state.favIds.add(st.uuid); else state.favIds.delete(st.uuid); renderNow(); });
    } else {
      var favs = localFavs().filter(function (f) { return f.uuid !== st.uuid; });
      if (!on) favs.unshift(st);
      local("sm-favs", favs.slice(0, 200));
    }
    if (on) state.favIds.delete(st.uuid); else state.favIds.add(st.uuid);
    renderNow();
  }

  function renderLocalFavs() {
    var box = document.getElementById("local-favs");
    if (!box) return;
    var favs = localFavs();
    box.innerHTML = "";
    if (!favs.length) {
      var p = document.createElement("div"); p.className = "empty card";
      p.textContent = box.getAttribute("data-empty"); box.appendChild(p); return;
    }
    var ul = document.createElement("ul"); ul.className = "stations"; ul.setAttribute("data-cat", "favorites");
    favs.forEach(function (st) { ul.appendChild(buildItem(st)); });
    box.appendChild(ul);
  }
  var COLORS = 7;
  function thumbClass(name) { var h = 0; for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360; return "c" + (h % COLORS); }
  function buildItem(st) {
    var li = document.createElement("li"); li.className = "st";
    li.setAttribute("data-station", JSON.stringify(st)); li.setAttribute("data-uuid", st.uuid);
    var b = document.createElement("button"); b.className = "st-play"; b.type = "button"; b.setAttribute("aria-label", "Play " + st.name);
    var th = document.createElement("span"); th.className = "thumb " + thumbClass(st.name || "?"); th.setAttribute("data-letter", (st.name || "?").charAt(0).toUpperCase());
    if (st.favicon) { var im = document.createElement("img"); im.src = st.favicon; im.alt = ""; im.loading = "lazy"; im.referrerPolicy = "no-referrer"; th.appendChild(im); }
    var tx = document.createElement("span"); tx.className = "st-text";
    var n = document.createElement("span"); n.className = "st-name"; n.textContent = st.name;
    var m = document.createElement("span"); m.className = "st-meta"; m.textContent = [st.country, st.tags].filter(Boolean).join(" · ");
    tx.appendChild(n); tx.appendChild(m);
    var eq = document.createElement("span"); eq.className = "st-eq"; eq.innerHTML = "<i></i><i></i><i></i>";
    b.appendChild(th); b.appendChild(tx); b.appendChild(eq);
    var f = document.createElement("button"); f.className = "st-fav"; f.type = "button"; f.textContent = "★"; f.setAttribute("aria-label", "Save " + st.name + " to favourites");
    li.appendChild(b); li.appendChild(f);
    return li;
  }

  // ---------- list clicks (event delegation works for swapped pages too) ----------
  document.addEventListener("click", function (e) {
    var fav = e.target.closest(".st-fav");
    if (fav) {
      var st = stationFrom(fav.closest("li.st"));
      if (st) toggleFav(st);
      if (document.getElementById("local-favs") && !state.loggedIn) renderLocalFavs();
      return;
    }
    var btn = e.target.closest(".st-play");
    if (btn) {
      var li = btn.closest("li.st"), ul = li.parentElement;
      var station = stationFrom(li);
      if (state.station && station && station.uuid === state.station.uuid &&
          (bar.getAttribute("data-state") === "playing" || bar.getAttribute("data-state") === "loading")) { pause(); return; }
      play(station, listStations(ul), ul.getAttribute("data-cat"));
      return;
    }
    var first = e.target.closest("[data-play-first]");
    if (first) {
      var ul2 = document.querySelector("main ul.stations");
      var li2 = ul2 && ul2.querySelector("li.st");
      if (li2) play(stationFrom(li2), listStations(ul2), ul2.getAttribute("data-cat"));
    }
  });
  // broken station logos → show the coloured letter instead
  document.addEventListener("error", function (e) {
    var t = e.target;
    if (t && t.tagName === "IMG" && t.closest(".thumb")) t.remove();
  }, true);

  // ---------- start-up ----------
  function onPage() { renderLocalFavs(); markLists(); }
  document.addEventListener("page:load", onPage);

  var vol = local("sm-volume");
  if (typeof vol === "number") { $("pl-vol").value = vol; audio.volume = vol; }
  var last = local("sm-last");
  if (last && last.station) { state.station = last.station; state.category = last.category || ""; }
  var pending = state.locked ? null : local("sm-pending");
  if (pending && pending.station) {
    state.station = pending.station; state.category = pending.category || "";
    local("sm-pending", null);
  }
  localFavs().forEach(function (f) { state.favIds.add(f.uuid); });
  renderNow();
  setState("idle");
  onPage();

  fetch("/api/me", { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (me) {
    state.locked = !!me.gate && !me.user;
    if (!me.user) return;
    state.loggedIn = true;
    state.favIds = new Set(me.favorites || []);
    var pending = localFavs();
    if (pending.length) {  // move browser favourites into the account once
      api("POST", "/api/favorites/import", { stations: pending }).then(function () {
        pending.forEach(function (f) { state.favIds.add(f.uuid); });
        local("sm-favs", []);
        renderNow();
      }).catch(function () {});
    }
    renderNow();
  }).catch(function () {});
})();
