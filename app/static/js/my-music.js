// Sur Music — player for the visitor's own audio/video files. Files never leave the device.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var v = $("mm-video");
  if (!v) return;
  var items = [], idx = -1, shuffle = false, repeat = 0, order = [];   // repeat: 0 off, 1 all, 2 one
  var KEY = "mm-playlists";

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
  function pauseRadio() {
    var r = document.getElementById("pl-audio"); if (r && !r.paused) r.pause();
  }

  function render() {
    var ol = $("mm-items"); ol.textContent = "";
    items.forEach(function (it, i) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button"; b.className = "mm-item" + (i === idx ? " on" : "");
      b.textContent = it.name; b.addEventListener("click", function () { play(i); });
      var x = document.createElement("button");
      x.type = "button"; x.className = "mm-x"; x.textContent = "×"; x.setAttribute("aria-label", "Remove " + it.name);
      x.addEventListener("click", function () { remove(i); });
      li.appendChild(b); li.appendChild(x); ol.appendChild(li);
    });
    $("mm-count").textContent = items.length ? "(" + items.length + ")" : "";
    $("mm-drop").hidden = !!items.length;
  }
  function add(files) {
    var n = 0;
    Array.prototype.forEach.call(files, function (f) {
      var ok = /^(audio|video)\//.test(f.type) || /\.(mp3|m4a|aac|wav|ogg|oga|opus|flac|mp4|m4v|webm|mkv|mov)$/i.test(f.name);
      if (!ok) return;
      items.push({ name: f.name.replace(/\.[^.]+$/, ""), file: f, url: URL.createObjectURL(f) }); n++;
    });
    if (!n) { say("No audio or video files found in that selection."); return; }
    render();
    if (idx < 0) play(0);
  }
  function remove(i) {
    URL.revokeObjectURL(items[i].url); items.splice(i, 1);
    if (i < idx) idx--; else if (i === idx) { v.pause(); v.removeAttribute("src"); idx = -1; say("Nothing playing"); }
    render();
  }
  function play(i) {
    if (i < 0 || i >= items.length) return;
    idx = i; pauseRadio(); v.src = items[i].url; v.playbackRate = +$("mm-speed").value;
    v.play().catch(function () { say("Press Play to start"); });
    say("Playing: " + items[i].name); render();
    document.title = items[i].name + " — My music player";
  }
  function step(d) {
    if (!items.length) return;
    if (shuffle && items.length > 1) {
      var j; do { j = Math.floor(Math.random() * items.length); } while (j === idx); return play(j);
    }
    var n = idx + d;
    if (n >= items.length) n = repeat === 1 ? 0 : -1;
    if (n < 0 && d < 0) n = items.length - 1;
    if (n >= 0) play(n); else { say("End of list"); }
  }

  v.addEventListener("ended", function () { if (repeat === 2) play(idx); else step(1); });
  v.addEventListener("error", function () { if (idx >= 0) say("Your browser cannot play “" + items[idx].name + "”. Try Next."); });
  v.addEventListener("loadedmetadata", function () { $("mm-dur").textContent = fmt(v.duration); });
  v.addEventListener("timeupdate", function () {
    $("mm-cur").textContent = fmt(v.currentTime);
    if (v.duration) $("mm-seek").value = Math.round(v.currentTime / v.duration * 1000);
  });
  v.addEventListener("play", function () { $("mm-play").textContent = "⏸"; $("mm-play").setAttribute("aria-label", "Pause"); });
  v.addEventListener("pause", function () { $("mm-play").textContent = "▶"; $("mm-play").setAttribute("aria-label", "Play"); });

  $("mm-play").addEventListener("click", function () {
    if (idx < 0) { if (items.length) play(0); return; }
    if (v.paused) { pauseRadio(); v.play(); } else v.pause();
  });
  $("mm-prev").addEventListener("click", function () { if (v.currentTime > 3) v.currentTime = 0; else step(-1); });
  $("mm-next").addEventListener("click", function () { step(1); });
  $("mm-back").addEventListener("click", function () { v.currentTime = Math.max(0, v.currentTime - 10); });
  $("mm-fwd").addEventListener("click", function () { v.currentTime = Math.min(v.duration || 0, v.currentTime + 10); });
  $("mm-seek").addEventListener("input", function () { if (v.duration) v.currentTime = this.value / 1000 * v.duration; });
  $("mm-vol").addEventListener("input", function () { v.volume = this.value / 100; });
  $("mm-speed").addEventListener("change", function () { v.playbackRate = +this.value; });
  $("mm-shuffle").addEventListener("click", function () {
    shuffle = !shuffle; this.textContent = "Shuffle: " + (shuffle ? "on" : "off"); this.setAttribute("aria-pressed", shuffle);
  });
  $("mm-repeat").addEventListener("click", function () {
    repeat = (repeat + 1) % 3; this.textContent = "Repeat: " + ["off", "all", "one"][repeat];
  });
  $("mm-full").addEventListener("click", function () {
    var el = $("mm"); if (document.fullscreenElement) document.exitFullscreen(); else if (el.requestFullscreen) el.requestFullscreen();
  });
  $("mm-clear").addEventListener("click", function () {
    items.forEach(function (it) { URL.revokeObjectURL(it.url); });
    items = []; idx = -1; v.pause(); v.removeAttribute("src"); say("Nothing playing"); render();
  });
  $("mm-files").addEventListener("change", function () { add(this.files); this.value = ""; });
  $("mm-folder").addEventListener("change", function () { add(this.files); this.value = ""; });

  var box = $("mm");
  ["dragover", "dragenter"].forEach(function (e) { box.addEventListener(e, function (ev) { ev.preventDefault(); box.classList.add("over"); }); });
  ["dragleave", "drop"].forEach(function (e) { box.addEventListener(e, function () { box.classList.remove("over"); }); });
  box.addEventListener("drop", function (ev) { ev.preventDefault(); if (ev.dataTransfer) add(ev.dataTransfer.files); });

  document.addEventListener("keydown", function (e) {
    var t = e.target.tagName; if (/INPUT|SELECT|TEXTAREA/.test(t) && e.target.type !== "range") return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key.toLowerCase();
    if (k === " " && t !== "BUTTON") { e.preventDefault(); $("mm-play").click(); }
    else if (k === "arrowright" && t !== "INPUT") { $("mm-fwd").click(); }
    else if (k === "arrowleft" && t !== "INPUT") { $("mm-back").click(); }
    else if (k === "n") step(1); else if (k === "p") $("mm-prev").click();
    else if (k === "m") v.muted = !v.muted; else if (k === "f") $("mm-full").click();
  });

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
    var rest = items.filter(function (it) { return picked.indexOf(it) < 0; });
    items = picked.concat(rest); idx = -1; render(); play(0);
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
})();
