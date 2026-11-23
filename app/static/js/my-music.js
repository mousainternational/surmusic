// Sur Music — the visitor's own audio files. They play in the site's one player bar (player.js); files never leave the device.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var panel = $("mm-panel");
  if (!$("mm") || !panel) return;
  function setOpen(on) {                               // the song list is a part of the big player: shown or hidden in place
    panel.hidden = !on;
    document.querySelectorAll('[data-act="playlists"]').forEach(function (c) { c.setAttribute("aria-expanded", String(on)); });
    if (on) chips();
  }
  $("mm-close").addEventListener("click", function () { setOpen(false); });
  var speeds = ["0.5", "0.75", "1", "1.25", "1.5", "2"];
  function chips() {                                  // keep the buttons in the player bar and the big player in step with the panel
    var on = $("mm-shuffle").getAttribute("aria-pressed") === "true";
    document.querySelectorAll('[data-act="shuffle"]').forEach(function (c) { c.setAttribute("aria-pressed", String(on)); c.textContent = "🔀 Shuffle" + (on ? ": on" : ""); });
    document.querySelectorAll('[data-act="repeat"]').forEach(function (c) { c.textContent = "🔁 " + $("mm-repeat").textContent; });
    document.querySelectorAll('[data-act="speed"]').forEach(function (c) { c.textContent = "⚡ " + (+$("mm-speed").value) + "×"; });
  }
  window.SurMyMusic = {
    toggle: function () { setOpen(panel.hidden); }, open: function () { setOpen(true); },
    act: function (what) {
      if (what === "playlists") { setOpen(panel.hidden); return; }
      if (what === "songs") { setOpen(true); return; }
      if (what === "shuffle") $("mm-shuffle").click();
      else if (what === "repeat") $("mm-repeat").click();
      else if (what === "speed") { var sel = $("mm-speed"); sel.value = speeds[(speeds.indexOf(sel.value) + 1) % speeds.length]; sel.dispatchEvent(new Event("change")); }
      chips();
    }
  };
  $("mm-close").addEventListener("click", function () { setOpen(false); if (opener) opener.focus(); });
  var items = [], orig = [], shuffle = false, repeat = 1, seq = 0;      // repeat: 0 off, 1 all, 2 one
  var KEY = "mm-playlists";
  function P() { return window.SurPlayer; }

  function fmt(t) {
    if (!isFinite(t)) return "0:00";
    t = Math.floor(t); var h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), s = t % 60;
    return (h ? h + ":" + (m < 10 ? "0" : "") : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }
  function pls(val) {
    try {
      if (val === undefined) return JSON.parse(localStorage.getItem(KEY) || "{}") || {};
      localStorage.setItem(KEY, JSON.stringify(val));
    } catch (e) { return {}; }
  }
  function say(t) { $("mm-now").textContent = t; }
  function current() { var a = P() && P().audio; return a && a.getAttribute("src") ? a : null; }

  function render() {
    var ol = $("mm-items"); ol.textContent = "";
    items.forEach(function (it, i) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button"; b.className = "mm-item"; b.textContent = it.name;
      b.addEventListener("click", function () { play(i); });
      var x = document.createElement("button");
      x.type = "button"; x.className = "mm-x"; x.textContent = "×"; x.setAttribute("aria-label", "Remove " + it.name);
      x.addEventListener("click", function () { remove(i); });
      li.appendChild(b); li.appendChild(x); ol.appendChild(li);
    });
    $("mm-count").textContent = items.length ? "(" + items.length + ")" : "";
    $("mm-drop").hidden = !!items.length;
    if (P()) P().setList(items);
  }
  function play(i) {
    if (!P()) { say("The player is still loading — try again in a moment."); return; }
    P().playLocal(items, i); say("Playing: " + items[i].name);
  }
  function add(files) {
    var n = 0, first = items.length;
    Array.prototype.forEach.call(files, function (f) {
      var ok = /^(audio|video)\//.test(f.type) || /\.(mp3|m4a|aac|wav|ogg|oga|opus|flac|mp4|m4v|webm|mkv|mov)$/i.test(f.name);
      if (!ok) return;
      var it = { uuid: "local:" + (++seq), name: f.name.replace(/\.[^.]+$/, ""), url: URL.createObjectURL(f),
                 tags: "podcast,local", local: true };
      items.push(it); orig.push(it); n++;
    });
    if (!n) { say("No audio files found in that selection."); return; }
    render(); say(items.length + " track(s) ready.");
    if (!current()) play(first);
  }
  function remove(i) {
    var it = items[i]; URL.revokeObjectURL(it.url); items.splice(i, 1);
    orig = orig.filter(function (o) { return o !== it; }); render();
  }

  function shuffled(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  // end of a track: repeat-one plays it again; "repeat off" stops after the last track; otherwise the player goes on
  function wire() {
    if (!P()) return setTimeout(wire, 300);
    var a = P().audio;
    P().onEnded = function (st) {
      if (repeat === 2) { a.currentTime = 0; a.play(); return true; }
      if (repeat === 0 && items.length && items[items.length - 1].uuid === st.uuid) { P().pause(); say("End of list"); return true; }
      return false;
    };
    a.addEventListener("loadedmetadata", function () { $("mm-dur").textContent = fmt(a.duration); a.playbackRate = +$("mm-speed").value; });
    a.addEventListener("timeupdate", function () {
      $("mm-cur").textContent = fmt(a.currentTime);
      if (a.duration) $("mm-seek").value = Math.round(a.currentTime / a.duration * 1000);
    });
    a.addEventListener("playing", function () {
      var s = P().audio, st = items.filter(function (i) { return s.src === i.url; })[0];
      if (st) say("Playing: " + st.name);
    });
  }
  wire();

  $("mm-back").addEventListener("click", function () { var a = current(); if (a) a.currentTime = Math.max(0, a.currentTime - 10); });
  $("mm-fwd").addEventListener("click", function () { var a = current(); if (a) a.currentTime = Math.min(a.duration || 0, a.currentTime + 10); });
  $("mm-seek").addEventListener("input", function () { var a = current(); if (a && a.duration) a.currentTime = this.value / 1000 * a.duration; });
  $("mm-speed").addEventListener("change", function () { var a = current(); if (a) a.playbackRate = +this.value; });
  $("mm-shuffle").addEventListener("click", function () {
    shuffle = !shuffle; this.textContent = "Shuffle: " + (shuffle ? "on" : "off"); this.setAttribute("aria-pressed", shuffle);
    items = shuffle ? shuffled(items) : orig.slice(); render();
  });
  $("mm-repeat").addEventListener("click", function () {
    repeat = (repeat + 1) % 3; this.textContent = "Repeat: " + ["off", "all", "one"][repeat];
  });
  $("mm-clear").addEventListener("click", function () {
    items.forEach(function (it) { URL.revokeObjectURL(it.url); });
    items = []; orig = []; if (P() && current()) P().pause(); say("Nothing added yet"); render();
  });
  $("mm-files").addEventListener("change", function () { add(this.files); this.value = ""; });
  $("mm-folder").addEventListener("change", function () { add(this.files); this.value = ""; });

  var box = $("mm");
  ["dragover", "dragenter"].forEach(function (e) { box.addEventListener(e, function (ev) { ev.preventDefault(); box.classList.add("over"); }); });
  ["dragleave", "drop"].forEach(function (e) { box.addEventListener(e, function () { box.classList.remove("over"); }); });
  box.addEventListener("drop", function (ev) { ev.preventDefault(); if (ev.dataTransfer) add(ev.dataTransfer.files); });

  // ---- playlists: names are remembered; files are matched by name when added again ----
  function renderPls() {
    var all = pls(), ul = $("mm-pllist"); ul.textContent = "";
    Object.keys(all).forEach(function (name) {
      var li = document.createElement("li");
      var b = document.createElement("button"); b.type = "button"; b.className = "btn btn-ghost";
      b.textContent = name + " (" + all[name].length + ")";
      b.addEventListener("click", function () { load(name); });
      var x = document.createElement("button"); x.type = "button"; x.className = "mm-x"; x.textContent = "×";
      x.setAttribute("aria-label", "Delete playlist " + name);
      x.addEventListener("click", function () { var a = pls(); delete a[name]; pls(a); renderPls(); });
      li.appendChild(b); li.appendChild(x); ul.appendChild(li);
    });
    if (!Object.keys(all).length) { var e = document.createElement("li"); e.className = "muted"; e.textContent = "No playlists yet."; ul.appendChild(e); }
  }
  function load(name) {
    var want = pls()[name] || [], map = {};
    items.forEach(function (it) { map[it.name] = it; });
    var picked = want.filter(function (n) { return map[n]; }).map(function (n) { return map[n]; });
    if (!picked.length) { say("Add the songs of “" + name + "” first (+ Add files), then open the playlist."); return; }
    items = picked.concat(items.filter(function (it) { return picked.indexOf(it) < 0; }));
    render(); play(0);
    if (picked.length < want.length) say("Playing “" + name + "” — " + (want.length - picked.length) + " track(s) not added yet.");
  }
  $("mm-plsave").addEventListener("click", function () {
    var name = $("mm-plname").value.trim();
    if (!name) { say("Type a playlist name first."); return; }
    if (!items.length) { say("Add some songs first."); return; }
    var all = pls(); all[name] = items.map(function (i) { return i.name; }); pls(all);
    $("mm-plname").value = ""; renderPls(); say("Saved playlist “" + name + "”.");
  });
  renderPls(); render();
  var pending = $("mm-files").files;                 // songs chosen with the "＋♪" button before this file had finished loading
  if (pending && pending.length) { add(pending); $("mm-files").value = ""; }
})();
