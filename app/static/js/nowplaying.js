// Sur Music — "Now Playing": a big centred player with lights and a choice of looks.
// It only draws pictures; the real player (player.js) keeps playing. The lights follow the beat of the music
// they cannot "hear" (radio streams do not allow that), so they move while a station plays and rest when it stops.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var ov = $("np"), cv = $("np-canvas"), bar = $("player");
  if (!ov || !cv || !bar) return;
  var g = cv.getContext("2d");
  if (!g) return;

  var SKINS = ["neon", "tunnel", "glass", "vinyl", "sunset", "edm"];
  var COLS = ["#ff3d86", "#ff7a1a", "#f5a300", "#12b886", "#3b7bff", "#8a5cf6"];
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var slowNet = document.documentElement.classList.contains("slow-net");
  var skin = "neon", lights = !reduce && !slowNet, W = 0, H = 0, D = 1, t = 0, level = 0, raf = 0, last = 0, isOpen = false;
  var opener = null;

  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, v) { try { localStorage.setItem(key, v); } catch (e) { /* private window */ } }

  var saved = load("sm-skin");
  if (SKINS.indexOf(saved) >= 0) skin = saved;
  var savedLights = load("sm-lights");
  if (savedLights === "off") lights = false; else if (savedLights === "on") lights = true;

  // ---------- two-way sync with the bar player ----------
  function state() { return bar.getAttribute("data-state") || "idle"; }
  function playing() { return state() === "playing"; }
  function syncText() {
    $("np-name").textContent = $("pl-name").textContent;
    $("np-status").textContent = $("pl-status") ? $("pl-status").textContent : "";
    var s = state();
    $("np-state").textContent = s === "playing" ? "LIVE NOW" : (s === "loading" ? "CONNECTING" : (s === "paused" ? "PAUSED" : (s === "slow" ? "SLOW CONNECTION" : "READY")));
    var play = $("np-play");
    play.setAttribute("aria-label", s === "playing" || s === "loading" ? "Pause" : "Play");
    play.classList.toggle("on", s === "playing" || s === "loading");
    var fav = $("pl-fav"), nf = $("np-fav"), on = fav.classList.contains("on");
    nf.classList.toggle("on", on);
    nf.setAttribute("aria-pressed", on ? "true" : "false");
    nf.setAttribute("aria-label", on ? "Remove from favourites" : "Add to favourites");
    ov.setAttribute("data-state", s);
    if (isOpen && !lights) draw(0, true);
    var v = $("pl-vol");
    if (v && $("np-vol").value !== v.value) $("np-vol").value = v.value;
  }
  new MutationObserver(syncText).observe(bar, { attributes: true, subtree: true, childList: true, characterData: true, attributeFilter: ["data-state", "class", "aria-pressed"] });

  $("np-play").addEventListener("click", function () { $("pl-play").click(); });
  $("np-prev").addEventListener("click", function () { $("pl-prev").click(); });
  $("np-next").addEventListener("click", function () { $("pl-next").click(); });
  $("np-fav").addEventListener("click", function () { $("pl-fav").click(); });
  $("np-vol").addEventListener("input", function (e) {
    var v = $("pl-vol"); v.value = e.target.value; v.dispatchEvent(new Event("input"));
  });

  // ---------- open / close ----------
  function setSkin(k) {
    if (SKINS.indexOf(k) < 0) k = "neon";
    skin = k; ov.setAttribute("data-skin", k); $("np-skin").value = k; save("sm-skin", k);
    if (isOpen) { fit(); draw(0, true); }
  }
  function setLights(on) {
    lights = on; save("sm-lights", on ? "on" : "off");
    var b = $("np-lights"); b.setAttribute("aria-pressed", on ? "true" : "false"); b.textContent = on ? "Lights on" : "Lights off";
    if (isOpen) { cancelAnimationFrame(raf); raf = 0; schedule(); }
  }
  function open() {
    if (isOpen) return;
    opener = document.activeElement; isOpen = true; ov.hidden = false;
    document.documentElement.classList.add("np-lock");
    syncText(); setSkin(skin); setLights(lights); fit(); schedule();
    $("np-close").focus();
  }
  function close() {
    if (!isOpen) return;
    isOpen = false; ov.hidden = true; cancelAnimationFrame(raf); raf = 0;
    document.documentElement.classList.remove("np-lock");
    if (opener && opener.focus) opener.focus();
  }
  $("np-open").addEventListener("click", open);
  $("np-close").addEventListener("click", close);
  $("np-skin").addEventListener("change", function (e) { setSkin(e.target.value); });
  $("np-lights").addEventListener("click", function () { setLights(!lights); });
  document.addEventListener("keydown", function (e) {
    if (!isOpen) return;
    if (e.key === "Escape") { close(); e.preventDefault(); return; }
    if (e.key === "Tab") {                       // keep the keyboard inside the big player
      var f = ov.querySelectorAll("button, select, input");
      if (!f.length) return;
      var first = f[0], lastEl = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { lastEl.focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === lastEl) { first.focus(); e.preventDefault(); }
    }
  });
  document.addEventListener("visibilitychange", function () { if (document.hidden) { cancelAnimationFrame(raf); raf = 0; } else if (isOpen) schedule(); });
  window.addEventListener("resize", function () { if (isOpen) { fit(); draw(0, true); } });

  // ---------- drawing helpers ----------
  function fit() {
    D = Math.min(window.devicePixelRatio || 1, 1.5);
    var r = cv.getBoundingClientRect();
    W = cv.width = Math.max(1, Math.round(r.width * D)); H = cv.height = Math.max(1, Math.round(r.height * D));
  }
  function wave(x, tt) { return 0.5 + 0.5 * Math.sin(tt * 3.1 + x * 0.55) * Math.sin(tt * 1.7 + x * 0.23 + 1); }
  function vol() { var v = Number($("np-vol").value); return isNaN(v) ? 0.8 : v; }
  function small() { return window.innerWidth < 620; }

  function bg(color, alpha) { g.globalCompositeOperation = "source-over"; g.fillStyle = color; g.globalAlpha = alpha === undefined ? 1 : alpha; g.fillRect(0, 0, W, H); g.globalAlpha = 1; }

  var particles = [];
  for (var i = 0; i < 160; i++) particles.push({ a: Math.random() * 6.283, r: Math.random(), s: 0.15 + Math.random() * 0.6, k: i % 6 });
  var perspLast = 0;

  // ---------- the six looks ----------
  var DRAW = {
    neon: function (T, L, v) {
      bg("#05040c", 0.24);
      var cx = W / 2, cy = H * (small() ? 0.33 : 0.38), R = Math.min(W, H) * (small() ? 0.15 : 0.155), k, i;
      g.globalCompositeOperation = "lighter";
      for (k = 0; k < 7; k++) {
        var a = T * 0.35 + k * 0.9, Ln = Math.max(W, H);
        g.save(); g.translate(cx, cy); g.rotate(a);
        var gr = g.createLinearGradient(0, 0, Ln, 0); gr.addColorStop(0, COLS[k % 6] + "55"); gr.addColorStop(1, "transparent");
        g.fillStyle = gr; g.globalAlpha = (0.05 + 0.07 * wave(k * 3, T)) * (0.3 + L); g.beginPath(); g.moveTo(0, 0); g.lineTo(Ln, -Ln * 0.05); g.lineTo(Ln, Ln * 0.05); g.closePath(); g.fill(); g.restore();
      }
      g.globalAlpha = 1; g.globalCompositeOperation = "source-over";
      var og = g.createRadialGradient(cx - R * 0.3, cy - R * 0.35, R * 0.05, cx, cy, R * 1.05);
      og.addColorStop(0, "#fff6e8"); og.addColorStop(0.18, "#ffb13f"); og.addColorStop(0.5, "#ff3d86"); og.addColorStop(0.85, "#4a1d7a"); og.addColorStop(1, "#120a28");
      g.shadowBlur = 60 * D; g.shadowColor = "#ff3d86"; g.fillStyle = og; g.beginPath(); g.arc(cx, cy, R * (1 + 0.025 * wave(0, T) * L), 0, 6.283); g.fill(); g.shadowBlur = 0;
      g.globalCompositeOperation = "lighter";
      for (k = 0; k < 3; k++) {
        g.save(); g.translate(cx, cy); g.rotate(T * 0.25 * (k % 2 ? -1 : 1) + k); g.scale(1, 0.28 + k * 0.06);
        g.strokeStyle = COLS[(k * 2) % 6]; g.lineWidth = (1.5 + k * 0.6) * D; g.shadowBlur = 14 * D; g.shadowColor = COLS[(k * 2) % 6]; g.globalAlpha = 0.6;
        g.beginPath(); g.arc(0, 0, R * (1.45 + k * 0.3), 0, 6.283); g.stroke(); g.restore();
      }
      var S = 120;
      for (i = 0; i < S; i++) {
        var an = i / S * 6.283 - 1.5708, h = (0.06 + 0.94 * wave(i, T) * L) * R * 0.42 * (0.4 + v);
        g.globalAlpha = 0.85; g.strokeStyle = COLS[Math.floor(i / S * 12) % 6]; g.lineWidth = R * 0.028; g.lineCap = "round"; g.shadowBlur = 8 * D; g.shadowColor = g.strokeStyle;
        g.beginPath(); g.moveTo(cx + Math.cos(an) * R * 1.12, cy + Math.sin(an) * R * 1.12); g.lineTo(cx + Math.cos(an) * (R * 1.12 + h), cy + Math.sin(an) * (R * 1.12 + h)); g.stroke();
      }
      g.shadowBlur = 0; g.globalAlpha = 1;
      for (i = 0; i < particles.length; i++) {
        var p = particles[i]; p.r += p.s * 0.004 * (0.3 + L); if (p.r > 1) p.r = 0;
        var rr = R * 1.1 + p.r * Math.max(W, H) * 0.55, x = cx + Math.cos(p.a + T * 0.1) * rr, y = cy + Math.sin(p.a + T * 0.1) * rr * 0.78;
        g.fillStyle = COLS[p.k]; g.globalAlpha = (1 - p.r) * 0.9 * (0.35 + L * 0.65); g.beginPath(); g.arc(x, y, (1.2 + p.r * 3) * D, 0, 6.283); g.fill();
      }
      g.globalAlpha = 1; g.globalCompositeOperation = "source-over";
    },

    tunnel: function (T, L, v) {
      bg("#05040c", 0.34);
      var cx = W / 2, hy = H * (small() ? 0.30 : 0.36), N = 16, i, k;
      for (i = 0; i < N; i++) {
        var z = ((i / N) + T * 0.12) % 1, s = Math.pow(z, 2.2), w = W * (0.04 + 1.25 * s), h = H * (0.03 + 0.95 * s) * 0.9, a = Math.min(1, z * 2) * (1 - z * 0.35), col = COLS[i % 6];
        g.strokeStyle = col; g.globalAlpha = a * (0.22 + 0.4 * wave(i * 2, T) * L); g.lineWidth = (1 + 3.2 * s) * D; g.shadowBlur = 14 * D; g.shadowColor = col;
        var x = cx - w / 2, y = hy - h / 2, r = 22 * s * D;
        g.beginPath(); g.moveTo(x + r, y); g.lineTo(x + w - r, y); g.quadraticCurveTo(x + w, y, x + w, y + r); g.lineTo(x + w, y + h - r); g.quadraticCurveTo(x + w, y + h, x + w - r, y + h); g.lineTo(x + r, y + h); g.quadraticCurveTo(x, y + h, x, y + h - r); g.lineTo(x, y + r); g.quadraticCurveTo(x, y, x + r, y); g.stroke();
      }
      g.globalAlpha = 1; g.shadowBlur = 0;
      for (i = -14; i <= 14; i++) { g.strokeStyle = COLS[(i + 14) % 6]; g.globalAlpha = 0.16; g.lineWidth = D; g.beginPath(); g.moveTo(cx, hy + H * 0.05); g.lineTo(cx + i * W * 0.12, H); g.stroke(); }
      for (k = 0; k < 10; k++) { var zz = ((k / 10) + T * 0.2) % 1, yy = hy + H * 0.05 + (H - hy) * zz * zz; g.globalAlpha = 0.25 * zz; g.strokeStyle = "#8a5cf6"; g.beginPath(); g.moveTo(0, yy); g.lineTo(W, yy); g.stroke(); }
      g.globalAlpha = 1;
      var cnt = small() ? 7 : 16, side, px, hh, c2;
      for (side = -1; side <= 1; side += 2) for (i = 0; i < cnt; i++) {
        px = cx + side * (W * 0.09 + i * (W * (small() ? 0.062 : 0.027)));
        hh = (0.04 + 0.96 * wave(i + (side > 0 ? 9 : 0), T) * L) * H * 0.3 * (0.4 + v); c2 = COLS[(i + (side > 0 ? 3 : 0)) % 6];
        g.fillStyle = c2; g.globalAlpha = 0.78; g.shadowBlur = 14 * D; g.shadowColor = c2; g.fillRect(px - W * 0.006, hy + H * 0.28 - hh, W * 0.012, hh);
      }
      g.globalAlpha = 1; g.shadowBlur = 0;
      for (k = 0; k < 5; k++) { var rr = Math.min(W, H) * (0.06 + 0.055 * k) * (1 + 0.07 * wave(k * 2, T) * L); g.strokeStyle = COLS[k % 6]; g.lineWidth = (1.5 + k * 0.7) * D; g.shadowBlur = 14 * D; g.shadowColor = COLS[k % 6]; g.globalAlpha = 0.85 - k * 0.12; g.beginPath(); g.arc(cx, hy, rr, 0, 6.283); g.stroke(); }
      var cg = g.createRadialGradient(cx, hy, 0, cx, hy, Math.min(W, H) * 0.07); cg.addColorStop(0, "#ffe9c9"); cg.addColorStop(0.45, "#ff9a3c"); cg.addColorStop(1, "#ff3d86");
      g.globalAlpha = 1; g.shadowBlur = 40 * D; g.shadowColor = "#ff5a3c"; g.fillStyle = cg; g.beginPath(); g.arc(cx, hy, Math.min(W, H) * 0.045, 0, 6.283); g.fill(); g.shadowBlur = 0;
    },

    glass: function (T, L, v) {
      var gr = g.createLinearGradient(0, 0, W, H); gr.addColorStop(0, "#2a0f7a"); gr.addColorStop(0.45, "#5a14a8"); gr.addColorStop(1, "#c01c8a");
      g.globalCompositeOperation = "source-over"; g.fillStyle = gr; g.fillRect(0, 0, W, H);
      var defs = [[0.12, 0.15, 0.30, "#6f4bff", "#3b1fd6", 0], [0.88, 0.12, 0.28, "#ff3d86", "#ff1f6e", 1.7], [0.5, 1.0, 0.30, "#ff7a1a", "#ff3d86", 3.1], [0.82, 0.86, 0.20, "#12b9d6", "#3b7bff", 4.4], [0.1, 0.82, 0.14, "#f5a300", "#ff7a1a", 5.5]];
      defs.forEach(function (d) {
        var rr = Math.min(W, H) * d[2] * 1.5, x = W * d[0] + Math.sin(T * 0.25 + d[5]) * 60 * D, y = H * d[1] + Math.cos(T * 0.2 + d[5]) * 45 * D;
        var rg = g.createRadialGradient(x - rr * 0.2, y - rr * 0.2, rr * 0.05, x, y, rr); rg.addColorStop(0, d[3]); rg.addColorStop(1, d[4]);
        g.fillStyle = rg; g.beginPath(); g.arc(x, y, rr, 0, 6.283); g.fill();
      });
      g.strokeStyle = "rgba(255,255,255,.65)"; g.lineWidth = 2 * D;
      [[0.04, 0.3, 0.07], [0.97, 0.78, 0.12]].forEach(function (c) { g.beginPath(); g.arc(W * c[0], H * c[1], Math.min(W, H) * c[2], 0, 6.283); g.stroke(); });
      // glass panel with the lights inside
      var pw = Math.min(W * (small() ? 0.88 : 0.42), 520 * D * 1.3), ph = Math.min(H * 0.34, pw * 0.8), px = (W - pw) / 2, py = H * (small() ? 0.14 : 0.13);
      g.fillStyle = "rgba(255,255,255,.14)"; g.strokeStyle = "rgba(255,255,255,.5)"; g.lineWidth = 1.5 * D;
      g.beginPath(); g.roundRect(px, py, pw, ph, 26 * D); g.fill(); g.stroke();
      var n = small() ? 20 : 30, gap = pw / (n + 1), i;
      for (i = 0; i < n; i++) {
        var h = (0.06 + 0.94 * wave(i, T) * L) * ph * 0.55 * (0.4 + v), x = px + gap * (i + 1), y = py + ph * 0.62;
        g.fillStyle = "rgba(255,255,255,.92)"; g.shadowBlur = 14 * D; g.shadowColor = COLS[i % 6]; g.beginPath(); g.roundRect(x - gap * 0.2, y - h, gap * 0.4, h * 1.45, gap * 0.2); g.fill();
      }
      g.shadowBlur = 0;
      for (i = 0; i < 3; i++) {
        g.beginPath();
        for (var x2 = 0; x2 <= pw; x2 += 6) { var y2 = py + ph * 0.84 + Math.sin(x2 * 0.016 + T * (1.2 + i * 0.4) * (0.3 + L) + i) * ph * 0.05 * (1 + i * 0.3); if (x2) g.lineTo(px + x2, y2); else g.moveTo(px + x2, y2); }
        g.strokeStyle = COLS[i * 2]; g.globalAlpha = 0.85; g.lineWidth = 3 * D; g.shadowBlur = 12 * D; g.shadowColor = COLS[i * 2]; g.stroke(); g.globalAlpha = 1; g.shadowBlur = 0;
      }
    },

    vinyl: function (T, L, v) {
      var wood = g.createLinearGradient(0, 0, W, H); wood.addColorStop(0, "#5b3418"); wood.addColorStop(0.5, "#7a4a26"); wood.addColorStop(1, "#4a2a14");
      g.globalCompositeOperation = "source-over"; g.fillStyle = wood; g.fillRect(0, 0, W, H);
      g.strokeStyle = "rgba(0,0,0,.14)"; g.lineWidth = D;
      for (var i = 0; i < 46; i++) { var yy = i / 46 * H + Math.sin(i * 1.7) * 6 * D; g.beginPath(); g.moveTo(0, yy); g.bezierCurveTo(W * 0.3, yy + 10 * D, W * 0.7, yy - 10 * D, W, yy + 4 * D); g.stroke(); }
      var cx = W / 2, cy = H * (small() ? 0.34 : 0.4), R = Math.min(W, H) * (small() ? 0.29 : 0.30);
      var bh = (0.5 + 0.5 * wave(1, T)) * L; g.fillStyle = "rgba(255,190,110," + (0.05 + 0.16 * bh) + ")"; g.beginPath(); g.arc(cx, cy, R * 1.32, 0, 6.283); g.fill();
      g.shadowBlur = 40 * D; g.shadowColor = "rgba(0,0,0,.8)"; g.fillStyle = "#2b1709"; g.beginPath(); g.arc(cx, cy, R * 1.1, 0, 6.283); g.fill(); g.shadowBlur = 0;
      g.save(); g.translate(cx, cy); g.rotate(T * 0.9 * (0.1 + L));
      var dg = g.createRadialGradient(0, 0, R * 0.1, 0, 0, R); dg.addColorStop(0, "#1b1b1f"); dg.addColorStop(1, "#08080a");
      g.fillStyle = dg; g.beginPath(); g.arc(0, 0, R, 0, 6.283); g.fill();
      g.strokeStyle = "rgba(255,255,255,.07)"; g.lineWidth = D;
      for (var r = R * 0.34; r < R * 0.98; r += R * 0.035) { g.beginPath(); g.arc(0, 0, r, 0, 6.283); g.stroke(); }
      var sh = g.createLinearGradient(-R, -R, R, R); sh.addColorStop(0.3, "rgba(255,255,255,0)"); sh.addColorStop(0.5, "rgba(255,255,255,.14)"); sh.addColorStop(0.7, "rgba(255,255,255,0)");
      g.fillStyle = sh; g.beginPath(); g.arc(0, 0, R, 0, 6.283); g.fill();
      var lg = g.createRadialGradient(0, 0, 2, 0, 0, R * 0.3); lg.addColorStop(0, "#ff7a1a"); lg.addColorStop(1, "#b3122a");
      g.fillStyle = lg; g.beginPath(); g.arc(0, 0, R * 0.3, 0, 6.283); g.fill();
      g.fillStyle = "#fff3de"; g.font = "700 " + (R * 0.32) + "px Poppins, Inter, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("♪", 0, R * 0.02);
      g.fillStyle = "#120a08"; g.beginPath(); g.arc(0, 0, R * 0.035, 0, 6.283); g.fill();
      g.restore();
      // tone arm: rests aside when stopped, lowers onto the record when playing
      var px = cx + R * 1.25, py = cy - R * 0.95, ang = (playing() ? 2.4 : 2.84) + Math.sin(T * 1.3) * 0.006 * L;
      g.save(); g.translate(px, py); g.rotate(ang);
      g.strokeStyle = "#d9d2c6"; g.lineWidth = R * 0.045; g.lineCap = "round"; g.shadowBlur = 10 * D; g.shadowColor = "rgba(0,0,0,.7)";
      g.beginPath(); g.moveTo(0, 0); g.lineTo(R * 1.22, 0); g.stroke();
      g.fillStyle = "#b9b1a4"; g.fillRect(R * 1.16, -R * 0.07, R * 0.2, R * 0.14); g.restore();
      g.fillStyle = "#cfc7b9"; g.beginPath(); g.arc(px, py, R * 0.09, 0, 6.283); g.fill(); g.shadowBlur = 0;
    },

    sunset: function (T, L, v) {
      var sky = g.createLinearGradient(0, 0, 0, H * 0.7); sky.addColorStop(0, "#2a1650"); sky.addColorStop(0.4, "#c2406a"); sky.addColorStop(0.75, "#ff7a3c"); sky.addColorStop(1, "#ffc15e");
      g.globalCompositeOperation = "source-over"; g.fillStyle = sky; g.fillRect(0, 0, W, H);
      var sx = W * 0.5, sy = H * 0.5, sr = Math.min(W, H) * 0.13 * (1 + 0.025 * wave(0, T) * L);
      var sg = g.createRadialGradient(sx, sy, sr * 0.2, sx, sy, sr * 3); sg.addColorStop(0, "rgba(255,230,160,.9)"); sg.addColorStop(1, "rgba(255,120,60,0)");
      g.fillStyle = sg; g.beginPath(); g.arc(sx, sy, sr * 3, 0, 6.283); g.fill();
      g.fillStyle = "#fff0b8"; g.beginPath(); g.arc(sx, sy, sr, 0, 6.283); g.fill();
      var i; g.fillStyle = "rgba(60,20,60,.55)";
      for (i = 0; i < 3; i++) { g.fillRect(0, sy - sr * 0.3 + i * sr * 0.28, W, sr * 0.07); }
      g.fillStyle = "#1a0f2a";
      g.beginPath(); g.moveTo(0, H * 0.62); g.bezierCurveTo(W * 0.2, H * 0.52, W * 0.38, H * 0.6, W * 0.55, H * 0.55); g.bezierCurveTo(W * 0.75, H * 0.5, W * 0.9, H * 0.6, W, H * 0.57); g.lineTo(W, H); g.lineTo(0, H); g.closePath(); g.fill();
      var n = small() ? 46 : 90, gap = W / n;
      for (i = 0; i < n; i++) {
        var h = (0.03 + 0.97 * wave(i * 0.7, T) * L) * H * 0.18 * (0.4 + v), x = i * gap + gap / 2;
        g.fillStyle = "rgba(255,210,150," + (0.35 + 0.5 * (h / (H * 0.18))) + ")"; g.fillRect(x - gap * 0.3, H * 0.66 - h, gap * 0.6, h);
      }
      for (i = 0; i < 5; i++) { var bx = ((T * 30 * D + i * W * 0.23) % (W + 80 * D)) - 40 * D, by = H * (0.16 + 0.04 * i) + Math.sin(T * 2 + i) * 8 * D; g.strokeStyle = "rgba(20,8,30,.8)"; g.lineWidth = 2 * D; g.beginPath(); g.moveTo(bx - 8 * D, by); g.quadraticCurveTo(bx, by - 6 * D * Math.sin(T * 6 + i), bx + 8 * D, by); g.stroke(); }
    },

    edm: function (T, L, v) {
      bg("#04060f", 0.5);
      var cols = small() ? 16 : 34, segs = small() ? 12 : 16, gap = W / (cols + 1), bw = gap * 0.7, base = H * (small() ? 0.5 : 0.5), maxH = H * 0.36, sh = maxH / segs, i, s;
      for (i = 0; i < cols; i++) {
        var lvl = Math.round((0.04 + 0.96 * wave(i * 1.1, T) * L) * segs * (0.45 + v * 0.55)), x = gap * (i + 1) - bw / 2;
        for (s = 0; s < segs; s++) {
          var on = s < lvl, hue = 150 - s / segs * 150 + (i % 6) * 6;
          g.fillStyle = on ? "hsl(" + (300 - s / segs * 300 + i * 4) % 360 + ",95%,58%)" : "rgba(255,255,255,.05)";
          if (on) { g.shadowBlur = 10 * D; g.shadowColor = g.fillStyle; } else g.shadowBlur = 0;
          g.fillRect(x, base - (s + 1) * sh + sh * 0.12, bw, sh * 0.76);
        }
        g.shadowBlur = 0;
        g.fillStyle = "rgba(255,255,255,.9)"; g.fillRect(x, base - (lvl + 1.4) * sh, bw, sh * 0.3);
        g.fillStyle = "rgba(255,255,255,.05)"; g.fillRect(x, base + 4 * D, bw, Math.min(lvl, 5) * sh * 0.3);
      }
    }
  };

  // ---------- frame loop (about 30 pictures a second; rests when closed, hidden or when lights are off) ----------
  function draw(ts, once) {
    var fn = DRAW[skin] || DRAW.neon, target = playing() ? 1 : 0.06;
    level += (target - level) * 0.08;
    if (!lights) { level = playing() ? 0.55 : 0.06; }
    try { fn(t, level, vol()); } catch (e) { /* a drawing problem must never stop the radio */ }
  }
  function loop(ts) {
    raf = 0;
    if (!isOpen || document.hidden) return;
    if (lights) {
      if (ts - last >= 33) { t += 0.02; last = ts; draw(ts); }
      raf = requestAnimationFrame(loop);
    } else {
      draw(ts, true);                              // lights off: one still picture
    }
  }
  function schedule() { if (!raf) raf = requestAnimationFrame(loop); }
  window.SurNowPlaying = { open: open, close: close };
})();
