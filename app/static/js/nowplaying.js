// © 2026 Mousa International Software House. All rights reserved.
// Sur Music — the 15 Now Playing themes. Each theme draws its own scene on a canvas and picks a layout (see np.css).
// The beat is simulated (a radio stream's sound cannot be read), so it looks alive but is not tied to the music.
(function () {
  'use strict';
  var TAU = Math.PI * 2;

  // free: shown to everyone. The others are for people with the app (trial or paid).
  var LIST = [
    { id: 'aurora',   name: 'Aurora Glass',     free: true,  layout: 'glass', fg: '#ffffff', acc: '#00f5a0', acc2: '#00d9f5' },
    { id: 'mint',     name: 'Mint Light',       free: true,  layout: 'pill',  fg: '#0b3b2e', acc: '#3ddc97', acc2: '#5af2c3', light: true },
    { id: 'rose',     name: 'Rose Soft Card',   free: true,  layout: 'soft',  fg: '#ffffff', acc: '#ff7eb6', acc2: '#c77dff' },
    { id: 'tokyo',    name: 'Neon Tokyo',       free: false, layout: 'plain', fg: '#ffffff', acc: '#ff2bd6', acc2: '#ff6a3d' },
    { id: 'hud',      name: 'Cyber HUD',        free: false, layout: 'hud',   fg: '#bcd0ff', acc: '#a855ff', acc2: '#5b8cff' },
    { id: 'ocean',    name: 'Deep Ocean',       free: false, layout: 'plain', fg: '#ffffff', acc: '#00c6ff', acc2: '#0072ff' },
    { id: 'emerald',  name: 'Emerald Ring',     free: false, layout: 'plain', fg: '#ffffff', acc: '#1fd67a', acc2: '#c6ff5a' },
    { id: 'gold',     name: 'Golden Turntable', free: false, layout: 'left',  fg: '#fff3d6', acc: '#ffb300', acc2: '#ff6a00' },
    { id: 'sunset',   name: 'Sunset Poster',    free: false, layout: 'poster', fg: '#ffffff', acc: '#ffc371', acc2: '#ff512f' },
    { id: 'arctic',   name: 'Arctic Crystal',   free: false, layout: 'glass', fg: '#e8f8ff', acc: '#9be7ff', acc2: '#6fb1ff' },
    { id: 'galaxy',   name: 'Galaxy Orbit',     free: false, layout: 'plain', fg: '#ffffff', acc: '#d946ef', acc2: '#6a3df5' },
    { id: 'lava',     name: 'Lava Bold',        free: false, layout: 'poster', fg: '#ffd60a', acc: '#ff9500', acc2: '#ff3b30' },
    { id: 'dunes',    name: 'Desert Dunes',     free: false, layout: 'left',  fg: '#fff1dc', acc: '#ffb35c', acc2: '#ff6f61' },
    { id: 'rain',     name: 'Monsoon Rain',     free: false, layout: 'glass', fg: '#e6f0ff', acc: '#7aa7ff', acc2: '#b0c8ff' },
    { id: 'cassette', name: 'Retro Cassette',   free: false, layout: 'plain', fg: '#3a2410', acc: '#e0622e', acc2: '#f2b84b', light: true }
  ];

  // ---------------------------------------------------------------- helpers
  function lg(c, x0, y0, x1, y1, stops) {
    var g = c.createLinearGradient(x0, y0, x1, y1);
    stops.forEach(function (s) { g.addColorStop(s[0], s[1]); });
    return g;
  }
  function rg(c, x, y, r0, r1, stops) {
    var g = c.createRadialGradient(x, y, r0, x, y, r1);
    stops.forEach(function (s) { g.addColorStop(s[0], s[1]); });
    return g;
  }
  function blob(c, x, y, r, col, a) {            // soft glowing colour cloud
    c.save(); c.globalAlpha = a;
    c.fillStyle = rg(c, x, y, 0, r, [[0, col], [1, 'rgba(0,0,0,0)']]);
    c.fillRect(x - r, y - r, r * 2, r * 2);
    c.restore();
  }
  function rr(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  }
  function bars(c, x, base, w, h, B, n, fill, gap, glowCol) {
    var bw = (w - (n - 1) * gap) / n;
    c.save();
    if (glowCol) { c.shadowColor = glowCol; c.shadowBlur = 14; }
    c.fillStyle = fill;
    for (var i = 0; i < n; i++) {
      var bh = Math.max(4, B[i % B.length] * h);
      rr(c, x + i * (bw + gap), base - bh, bw, bh, Math.min(bw / 2, 8));
      c.fill();
    }
    c.restore();
  }
  function disc(c, x, y, r, rot, a, b) {         // a vinyl record with a coloured label
    c.save(); c.translate(x, y); c.rotate(rot);
    c.fillStyle = '#0b0b0f'; c.beginPath(); c.arc(0, 0, r, 0, TAU); c.fill();
    c.strokeStyle = 'rgba(255,255,255,.07)'; c.lineWidth = 1;
    for (var k = r * .36; k < r * .97; k += r * .055) { c.beginPath(); c.arc(0, 0, k, 0, TAU); c.stroke(); }
    c.fillStyle = 'rgba(255,255,255,.10)';
    c.beginPath(); c.moveTo(0, 0); c.arc(0, 0, r * .96, -.5, .0); c.closePath(); c.fill();
    c.fillStyle = lg(c, -r * .3, -r * .3, r * .3, r * .3, [[0, a], [1, b]]);
    c.beginPath(); c.arc(0, 0, r * .3, 0, TAU); c.fill();
    c.fillStyle = '#0b0b0f'; c.beginPath(); c.arc(0, 0, r * .045, 0, TAU); c.fill();
    c.restore();
  }
  // fixed pseudo-random numbers, so stars / rain do not jump around between frames
  var R = []; (function () { var s = 12345; for (var i = 0; i < 400; i++) { s = (s * 1664525 + 1013904223) % 4294967296; R.push(s / 4294967296); } })();

  // ---------------------------------------------------------------- the 15 scenes
  var DRAW = {
    aurora: function (c, w, h, s) {
      c.fillStyle = '#0a1030'; c.fillRect(0, 0, w, h);
      blob(c, w * (.2 + .1 * Math.sin(s.t * .3)), h * .16, w * .75, '#00f5a0', .55);
      blob(c, w * (.88 + .06 * Math.cos(s.t * .25)), h * .3, w * .65, '#00d9f5', .42);
      blob(c, w * .5, h * (.62 + .03 * Math.sin(s.t * .2)), w * .9, '#7b2cff', .38);
      var cx = w / 2, cy = h * .27, r = w * .19 * (1 + .09 * s.level);
      c.save(); c.shadowColor = '#00f5a0'; c.shadowBlur = 50;
      c.fillStyle = rg(c, cx - r * .2, cy - r * .2, 0, r, [[0, '#b8ffe6'], [.55, '#00f5a0'], [1, '#00b3d6']]);
      c.beginPath(); c.arc(cx, cy, r, 0, TAU); c.fill(); c.restore();
      bars(c, w * .12, h * .5, w * .76, h * .16, s.bars, 14, lg(c, 0, h * .34, 0, h * .5, [[0, '#00f5a0'], [1, '#7b2cff']]), w * .012);
    },
    mint: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, 0, h, [[0, '#e9fff7'], [1, '#bff5e0']]); c.fillRect(0, 0, w, h);
      blob(c, w * .9, h * .1, w * .6, '#8fe3ff', .5); blob(c, w * .1, h * .45, w * .5, '#5af2c3', .4);
      var x = w * .08, y = h * .08, aw = w * .84, ah = h * .38;
      c.save(); c.shadowColor = 'rgba(61,220,151,.45)'; c.shadowBlur = 40; c.shadowOffsetY = 18;
      c.fillStyle = lg(c, x, y, x + aw, y + ah, [[0, '#5af2c3'], [1, '#8fe3ff']]); rr(c, x, y, aw, ah, 34); c.fill(); c.restore();
      bars(c, x + aw * .12, y + ah * .86, aw * .76, ah * .6, s.bars, 9, 'rgba(255,255,255,.85)', aw * .035);
    },
    rose: function (c, w, h, s) {
      c.fillStyle = '#2a1b2e'; c.fillRect(0, 0, w, h);
      blob(c, w * .2, h * .2, w * .6, '#ff7eb6', .22); blob(c, w * .85, h * .5, w * .6, '#c77dff', .2);
      var cw = w * .86, ch = h * .56, cx = (w - cw) / 2, cy = h * .05;
      c.save(); c.shadowColor = '#170e1d'; c.shadowBlur = 30; c.shadowOffsetX = 10; c.shadowOffsetY = 12;
      c.fillStyle = lg(c, cx, cy, cx + cw, cy + ch, [[0, '#33223a'], [1, '#241830']]); rr(c, cx, cy, cw, ch, 36); c.fill(); c.restore();
      var a = w * .36 * (1 + .04 * s.level), ax = w / 2 - a / 2, ay = cy + ch * .1;
      c.save(); c.shadowColor = 'rgba(255,126,182,.5)'; c.shadowBlur = 36; c.shadowOffsetY = 14;
      c.fillStyle = lg(c, ax, ay, ax + a, ay + a, [[0, '#ff7eb6'], [1, '#c77dff']]); rr(c, ax, ay, a, a, 34); c.fill(); c.restore();
      c.fillStyle = 'rgba(255,255,255,.9)';
      for (var i = 0; i < 5; i++) { var bh = 10 + s.bars[i * 2] * a * .35; rr(c, ax + a * .2 + i * a * .15, ay + a * .62 - bh / 2 + 10, a * .07, bh, 4); c.fill(); }
    },
    tokyo: function (c, w, h, s) {
      var hor = h * .43;
      c.fillStyle = lg(c, 0, 0, 0, hor, [[0, '#1a0536'], [1, '#6b0f7a']]); c.fillRect(0, 0, w, hor);
      c.fillStyle = lg(c, 0, hor, 0, h, [[0, '#2a0540'], [1, '#12061f']]); c.fillRect(0, hor, w, h - hor);
      var cx = w / 2, r = w * .3 * (1 + .03 * s.level), cy = hor - r * .15;
      c.save(); c.beginPath(); c.rect(0, 0, w, hor); c.clip();
      c.shadowColor = '#ff2bd6'; c.shadowBlur = 40;
      c.fillStyle = lg(c, 0, cy - r, 0, cy + r, [[0, '#ffe45e'], [.5, '#ff6a3d'], [1, '#ff2bd6']]);
      c.beginPath(); c.arc(cx, cy, r, 0, TAU); c.fill(); c.shadowBlur = 0;
      c.globalCompositeOperation = 'destination-out';                       // cut the stripes into the lower half of the sun
      for (var k = 0; k < 7; k++) { var yy = cy + r * (.05 + k * .14) + ((s.t * 6) % 1) * 0; c.fillRect(cx - r, yy, r * 2, 2 + k * 1.6); }
      c.restore();
      c.fillStyle = '#ff2bd6'; c.fillRect(0, hor - 1, w, 2);
      c.strokeStyle = 'rgba(255,43,214,.55)'; c.lineWidth = 1;
      for (var i = -12; i <= 12; i++) { c.beginPath(); c.moveTo(cx + i * 6, hor); c.lineTo(cx + i * w * .13, h); c.stroke(); }
      for (var j = 0; j < 9; j++) { var p = ((j + (s.t * .6 % 1)) / 9), y = hor + (h - hor) * p * p; c.beginPath(); c.moveTo(0, y); c.lineTo(w, y); c.stroke(); }
    },
    hud: function (c, w, h, s) {
      c.fillStyle = '#05030f'; c.fillRect(0, 0, w, h);
      c.fillStyle = 'rgba(168,85,255,.07)'; for (var y = 0; y < h; y += 4) c.fillRect(0, y, w, 1);
      var cx = w / 2, cy = h * .27, r = w * .26;
      c.save(); c.translate(cx, cy);
      c.shadowColor = '#a855ff'; c.shadowBlur = 24; c.strokeStyle = '#a855ff'; c.lineWidth = 3;
      c.beginPath(); c.arc(0, 0, r, 0, TAU); c.stroke(); c.shadowBlur = 0;
      c.strokeStyle = '#ff4fd8'; c.lineWidth = 2; c.setLineDash([7, 9]); c.rotate(s.t * .5);
      c.beginPath(); c.arc(0, 0, r * .78, 0, TAU); c.stroke(); c.setLineDash([]); c.rotate(-s.t * .5);
      c.strokeStyle = '#5b8cff'; c.lineWidth = 6;
      for (var a = 0; a < 3; a++) { c.beginPath(); c.arc(0, 0, r * 1.1, s.t * .8 + a * 2.1, s.t * .8 + a * 2.1 + .8); c.stroke(); }
      for (var i = 0; i < 48; i++) {                                           // radial bars around the ring
        var ang = i / 48 * TAU, len = 6 + s.bars[i % 16] * r * .28;
        c.strokeStyle = 'rgba(91,140,255,.8)'; c.lineWidth = 3;
        c.beginPath(); c.moveTo(Math.cos(ang) * r * 1.2, Math.sin(ang) * r * 1.2);
        c.lineTo(Math.cos(ang) * (r * 1.2 + len), Math.sin(ang) * (r * 1.2 + len)); c.stroke();
      }
      c.fillStyle = rg(c, 0, 0, 0, r * .3, [[0, '#ffffff'], [1, '#a855ff']]);
      c.beginPath(); c.arc(0, 0, r * .3 * (1 + .12 * s.level), 0, TAU); c.fill();
      c.restore();
    },
    ocean: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, 0, h, [[0, '#031428'], [1, '#005fa8']]); c.fillRect(0, 0, w, h);
      blob(c, w / 2, h * .2, w * .7, '#00c6ff', .3);
      disc(c, w / 2, h * .24, w * .27, s.t * .9, '#00ffd5', '#0072ff');
      for (var k = 0; k < 3; k++) {
        c.fillStyle = ['rgba(0,114,255,.5)', 'rgba(0,198,255,.45)', 'rgba(0,255,213,.35)'][k];
        c.beginPath(); c.moveTo(0, h);
        for (var x = 0; x <= w; x += 8) c.lineTo(x, h * (.72 + k * .05) + Math.sin(x / (50 + k * 20) + s.t * (1 + k * .4)) * (8 + 5 * s.level));
        c.lineTo(w, h); c.closePath(); c.fill();
      }
    },
    emerald: function (c, w, h, s) {
      c.fillStyle = '#04140f'; c.fillRect(0, 0, w, h); blob(c, w / 2, h * .27, w * .8, '#0fa37f', .35);
      var cx = w / 2, cy = h * .27, r = w * .26;
      c.lineWidth = 12; c.strokeStyle = '#143a2c'; c.beginPath(); c.arc(cx, cy, r, 0, TAU); c.stroke();
      c.save(); c.strokeStyle = '#c6ff5a'; c.lineCap = 'round'; c.shadowColor = '#c6ff5a'; c.shadowBlur = 16;
      var p = (s.t * .08) % 1; c.beginPath(); c.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + TAU * (.1 + p * .9)); c.stroke(); c.restore();
      for (var i = 0; i < 40; i++) {
        var a = i / 40 * TAU, l = 4 + s.bars[i % 16] * 20;
        c.strokeStyle = 'rgba(31,214,122,.55)'; c.lineWidth = 3;
        c.beginPath(); c.moveTo(cx + Math.cos(a) * (r + 18), cy + Math.sin(a) * (r + 18));
        c.lineTo(cx + Math.cos(a) * (r + 18 + l), cy + Math.sin(a) * (r + 18 + l)); c.stroke();
      }
      c.save(); c.shadowColor = '#1fd67a'; c.shadowBlur = 36;
      c.fillStyle = lg(c, cx - r, cy - r, cx + r, cy + r, [[0, '#1fd67a'], [1, '#0fa37f']]);
      c.beginPath(); c.arc(cx, cy, r * .72 * (1 + .03 * s.level), 0, TAU); c.fill(); c.restore();
    },
    gold: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, w, h, [[0, '#2a1604'], [1, '#0e0702']]); c.fillRect(0, 0, w, h);
      blob(c, w * .3, h * .25, w * .8, '#ffb300', .18);
      disc(c, w * .38, h * .26, w * .34, s.t * 1.1, '#fff3c4', '#ff6a00');
      c.save(); c.translate(w * .86, h * .08); c.rotate(.38); c.shadowColor = '#ffb300'; c.shadowBlur = 12;
      c.fillStyle = lg(c, 0, 0, 8, 0, [[0, '#ffe27a'], [1, '#b07a00']]); rr(c, -4, 0, 8, h * .26, 4); c.fill(); c.restore();
      for (var i = 0; i < 26; i++) {                                           // golden dust
        var x = R[i] * w, y = ((R[i + 30] * h) + s.t * (6 + R[i + 60] * 10)) % h;
        c.fillStyle = 'rgba(255,200,90,' + (.15 + R[i + 90] * .35) + ')'; c.beginPath(); c.arc(x, y, 1 + R[i + 120] * 2, 0, TAU); c.fill();
      }
    },
    sunset: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, 0, h, [[0, '#1a0610'], [.62, '#dd2476'], [1, '#ff512f']]); c.fillRect(0, 0, w, h);
      var cx = w / 2, cy = h * .5, r = w * .36 * (1 + .02 * s.level);
      c.save(); c.beginPath(); c.rect(0, 0, w, cy); c.clip();
      c.fillStyle = lg(c, 0, cy - r, 0, cy, [[0, '#ffc371'], [1, '#ff512f']]); c.beginPath(); c.arc(cx, cy, r, 0, TAU); c.fill();
      c.globalCompositeOperation = 'destination-out';
      for (var k = 0; k < 6; k++) { c.fillRect(cx - r, cy - r * .1 - k * r * .16 + (s.t * 4 % (r * .16)), r * 2, 3 + (5 - k) * 1.2); }
      c.restore();
      c.fillStyle = '#12040a'; c.beginPath(); c.moveTo(0, h * .56);
      for (var x = 0; x <= w; x += 10) c.lineTo(x, h * .56 - Math.abs(Math.sin(x * .02 + 1)) * h * .05 - Math.sin(x * .007) * h * .03);
      c.lineTo(w, h * .56); c.lineTo(w, h * .6); c.lineTo(0, h * .6); c.closePath(); c.fill();
    },
    arctic: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, w, h, [[0, '#0a2a44'], [1, '#071826']]); c.fillRect(0, 0, w, h);
      blob(c, w / 2, h * .28, w * .7, '#6fb1ff', .25);
      var cx = w / 2, cy = h * .27, r = w * .2 * (1 + .04 * s.level), rot = s.t * .5, sx = Math.cos(rot);
      c.strokeStyle = '#9be7ff'; c.lineWidth = 1.6; c.shadowColor = '#9be7ff'; c.shadowBlur = 10;
      c.beginPath(); c.moveTo(cx, cy - r * 1.3); c.lineTo(cx + r * sx, cy - r * .2); c.lineTo(cx, cy + r * 1.3); c.lineTo(cx - r * sx, cy - r * .2); c.closePath(); c.stroke();
      c.beginPath(); c.moveTo(cx, cy - r * 1.3); c.lineTo(cx + r * sx * .45, cy - r * .2); c.lineTo(cx, cy + r * 1.3); c.lineTo(cx - r * sx * .45, cy - r * .2); c.closePath(); c.stroke();
      c.beginPath(); c.moveTo(cx - r * sx, cy - r * .2); c.lineTo(cx + r * sx, cy - r * .2); c.stroke();
      c.shadowBlur = 0; c.setLineDash([3, 6]); c.beginPath(); c.arc(cx, cy, r * 1.7, 0, TAU); c.stroke(); c.setLineDash([]);
      for (var i = 0; i < 40; i++) {                                           // snow
        var x = (R[i] * w + Math.sin(s.t + i) * 10) % w, y = (R[i + 50] * h + s.t * (14 + R[i + 100] * 18)) % h;
        c.fillStyle = 'rgba(255,255,255,' + (.25 + R[i + 150] * .5) + ')'; c.beginPath(); c.arc(x, y, 1 + R[i + 200] * 1.6, 0, TAU); c.fill();
      }
    },
    galaxy: function (c, w, h, s) {
      c.fillStyle = '#07041a'; c.fillRect(0, 0, w, h);
      blob(c, w * .75, h * .15, w * .6, '#d946ef', .3); blob(c, w * .2, h * .7, w * .6, '#38bdf8', .25);
      for (var i = 0; i < 90; i++) {
        c.fillStyle = 'rgba(255,255,255,' + (.25 + .6 * Math.abs(Math.sin(s.t * (.5 + R[i + 100]) + i))) + ')';
        c.fillRect(R[i] * w, R[i + 200] * h * .8, 1 + R[i + 300] * 1.5, 1 + R[i + 300] * 1.5);
      }
      var cx = w / 2, cy = h * .27, r = w * .17 * (1 + .04 * s.level);
      c.save(); c.translate(cx, cy); c.rotate(-.25);
      c.strokeStyle = 'rgba(56,189,248,.65)'; c.lineWidth = 4;
      c.beginPath(); c.ellipse(0, 0, r * 2.2, r * .6, 0, Math.PI, TAU); c.stroke();            // back half of the ring
      c.fillStyle = rg(c, -r * .3, -r * .3, 0, r, [[0, '#ffffff'], [.35, '#a78bfa'], [.7, '#6a3df5'], [1, '#1b0b4d']]);
      c.beginPath(); c.arc(0, 0, r, 0, TAU); c.fill();
      c.strokeStyle = 'rgba(56,189,248,.9)'; c.beginPath(); c.ellipse(0, 0, r * 2.2, r * .6, 0, 0, Math.PI); c.stroke();   // front half
      var ma = s.t * .9; c.fillStyle = '#e9d5ff'; c.beginPath(); c.arc(Math.cos(ma) * r * 2.2, Math.sin(ma) * r * .6, 5, 0, TAU); c.fill();
      c.restore();
    },
    lava: function (c, w, h, s) {
      c.fillStyle = '#140503'; c.fillRect(0, 0, w, h); blob(c, w / 2, h * .7, w, '#ff3b30', .25);
      bars(c, 0, h * .6, w, h * .4, s.bars, 6, lg(c, 0, h * .2, 0, h * .6, [[0, '#ffd60a'], [.45, '#ff9500'], [1, '#ff3b30']]), w * .035, '#ff9500');
      c.fillStyle = '#ff3b30'; c.fillRect(0, h * .6, w, 4);
    },
    dunes: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, 0, h * .6, [[0, '#2b1745'], [.55, '#ff6f61'], [1, '#ffb35c']]); c.fillRect(0, 0, w, h);
      for (var i = 0; i < 40; i++) { c.fillStyle = 'rgba(255,255,255,' + (.2 + .5 * Math.abs(Math.sin(s.t + i))) + ')'; c.fillRect(R[i] * w, R[i + 50] * h * .25, 1.5, 1.5); }
      var sx = w * .68, sy = h * .3, sr = w * .13 * (1 + .03 * s.level);
      c.save(); c.shadowColor = '#ffe27a'; c.shadowBlur = 40; c.fillStyle = rg(c, sx, sy, 0, sr, [[0, '#fff6c8'], [1, '#ffb35c']]);
      c.beginPath(); c.arc(sx, sy, sr, 0, TAU); c.fill(); c.restore();
      var cols = ['#a8452f', '#7a2c24', '#3d1519'];
      for (var k = 0; k < 3; k++) {
        c.fillStyle = cols[k]; c.beginPath(); c.moveTo(0, h);
        for (var x = 0; x <= w; x += 8) c.lineTo(x, h * (.5 + k * .08) - Math.sin(x * (.008 + k * .004) + k * 2 + s.t * .08) * h * (.06 - k * .01));
        c.lineTo(w, h); c.closePath(); c.fill();
      }
    },
    rain: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, 0, h, [[0, '#0b1220'], [1, '#1c2a44']]); c.fillRect(0, 0, w, h);
      var flash = s.level > .92 ? .18 : 0; if (flash) { c.fillStyle = 'rgba(190,210,255,' + flash + ')'; c.fillRect(0, 0, w, h); }
      c.strokeStyle = 'rgba(176,200,255,.45)'; c.lineWidth = 1.2;
      for (var i = 0; i < 110; i++) {
        var x = (R[i] * w * 1.2 + s.t * 40 * (.5 + R[i + 100] * .5)) % (w * 1.2) - w * .1, y = (R[i + 150] * h + s.t * (260 + R[i + 250] * 220)) % h, l = 12 + R[i + 300] * 16;
        c.beginPath(); c.moveTo(x, y); c.lineTo(x - l * .25, y + l); c.stroke();
      }
      var cx = w / 2, cy = h * .26;
      for (var k = 0; k < 4; k++) {                                            // ripples
        var p = ((s.t * .5 + k * .25) % 1); c.strokeStyle = 'rgba(122,167,255,' + (1 - p) * .6 + ')'; c.lineWidth = 2;
        c.beginPath(); c.ellipse(cx, cy, w * .08 + p * w * .3, (w * .08 + p * w * .3) * .35, 0, 0, TAU); c.stroke();
      }
      bars(c, w * .25, h * .44, w * .5, h * .08, s.bars, 10, 'rgba(176,200,255,.7)', w * .01);
    },
    cassette: function (c, w, h, s) {
      c.fillStyle = lg(c, 0, 0, 0, h, [[0, '#f6e7c8'], [1, '#e8cf9f']]); c.fillRect(0, 0, w, h);
      var cw = w * .84, ch = cw * .62, x = (w - cw) / 2, y = h * .06;
      c.save(); c.shadowColor = 'rgba(80,40,10,.35)'; c.shadowBlur = 26; c.shadowOffsetY = 14;
      c.fillStyle = '#3a2410'; rr(c, x, y, cw, ch, 22); c.fill(); c.restore();
      c.fillStyle = lg(c, x, y, x, y + ch * .55, [[0, '#f2b84b'], [1, '#e0622e']]); rr(c, x + cw * .08, y + ch * .1, cw * .84, ch * .5, 12); c.fill();
      c.fillStyle = '#fff4dc'; rr(c, x + cw * .14, y + ch * .16, cw * .72, ch * .14, 6); c.fill();
      c.fillStyle = '#3a2410'; c.font = '700 ' + Math.round(cw * .06) + 'px sans-serif'; c.textAlign = 'center'; c.fillText('SUR MUSIC · LIVE', w / 2, y + ch * .27);
      var rx = [x + cw * .3, x + cw * .7], ry = y + ch * .42;
      rx.forEach(function (px, i) {
        c.save(); c.translate(px, ry); c.rotate(s.t * (i ? 1.4 : 1.1));
        c.fillStyle = '#fff4dc'; c.beginPath(); c.arc(0, 0, ch * .13, 0, TAU); c.fill();
        c.fillStyle = '#3a2410'; for (var k = 0; k < 6; k++) { c.rotate(TAU / 6); c.fillRect(ch * .03, -2, ch * .08, 4); } c.restore();
      });
      c.fillStyle = '#c9b184'; rr(c, x + cw * .22, y + ch * .72, cw * .56, ch * .2, 8); c.fill();
      c.fillStyle = '#3a2410'; for (var j = 0; j < 4; j++) c.fillRect(x + cw * (.3 + j * .13), y + ch * .78, cw * .04, ch * .08);
      bars(c, x, y + ch + h * .12, cw, h * .06, s.bars, 16, '#e0622e', cw * .012);
    }
  };

  window.SurThemes = {
    list: LIST,
    byId: function (id) { for (var i = 0; i < LIST.length; i++) if (LIST[i].id === id) return LIST[i]; return LIST[0]; },
    draw: function (id, ctx, w, h, state) { (DRAW[id] || DRAW.aurora)(ctx, w, h, state); }
  };
})();

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

  var TH0 = window.SurThemes, SKINS = TH0.list.map(function (x) { return x.id; });
  var ALL = ov.getAttribute("data-all") === "1";             // paid app owners (and the owner) can use every look
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var slowNet = document.documentElement.classList.contains("slow-net");
  var skin = "aurora", lights = !reduce && !slowNet, W = 0, H = 0, D = 1, t = 0, level = 0, raf = 0, last = 0, isOpen = false;
  var opener = null;

  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, v) { try { localStorage.setItem(key, v); } catch (e) { /* private window */ } }

  var saved = load("sm-skin");
  if (SKINS.indexOf(saved) >= 0 && (ALL || TH0.byId(saved).free)) skin = saved;
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
    if (SKINS.indexOf(k) < 0) k = "aurora";
    var th = TH0.byId(k);
    if (!ALL && !th.free) { k = "aurora"; th = TH0.byId(k); }
    skin = k; ov.setAttribute("data-skin", k); $("np-skin").value = k; save("sm-skin", k);
    ov.style.setProperty("--np-fg", th.fg); ov.style.setProperty("--np-acc", th.acc); ov.style.setProperty("--np-acc2", th.acc2);
    ov.classList.toggle("np-light", !!th.light);
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
    if (window.SurAds && $("np-ad")) window.SurAds.fill();      // one ad per opening, never refreshed
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
  $("np-skin").addEventListener("change", function (e) {
    var k = e.target.value, lockMsg = $("np-lock");
    if (!ALL && !TH0.byId(k).free) {                // locked look: stay on the current one and show how to get it
      e.target.value = skin; if (lockMsg) { lockMsg.hidden = false; }
      return;
    }
    if (lockMsg) lockMsg.hidden = true;
    setSkin(k);
  });
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


  // ---------- the 15 looks (scenes live in the themes code above) ----------
  var TH = window.SurThemes, bstate = { t: 0, level: 0, bars: [], playing: false }, bi;
  for (bi = 0; bi < 16; bi++) bstate.bars.push(0.1);
  var oc = null, sideFill = "#0b0818", sideSkin = "";
  var DRAW = {
    scene: function (T, L, v) {
      var tt = T * 50, beat = Math.pow(Math.max(0, Math.sin(tt * 0.13 * 2.1)), 3), sum = 0, i;
      for (i = 0; i < 16; i++) {
        var w = 0.5 + 0.5 * Math.sin(tt * 0.06 * (1.8 + i * 0.37) + i * 1.7), wob = 0.5 + 0.5 * Math.sin(tt * 0.03 + i * 2.3);
        var target = L > 0.3 ? (0.12 + 0.88 * w * (0.35 + 0.65 * wob)) * (0.6 + 0.4 * beat) * (0.45 + v * 0.55) : 0.06;
        bstate.bars[i] += (target - bstate.bars[i]) * 0.35; sum += bstate.bars[i];
      }
      bstate.t = T * 1.0; bstate.level = L > 0.3 ? Math.min(1, sum / 16 * 1.6 + beat * 0.25) : 0; bstate.playing = L > 0.3;
      if (W / H > 1.15) {                              // wide screen: the picture is drawn tall and centred, the sides carry its colours
        var pw = Math.round(H * 0.62);
        if (!oc) oc = document.createElement("canvas");
        if (oc.width !== pw || oc.height !== H) { oc.width = pw; oc.height = H; sideSkin = ""; }
        var o = oc.getContext("2d");
        o.setTransform(D, 0, 0, D, 0, 0); o.clearRect(0, 0, pw / D, H / D);
        TH.draw(skin, o, pw / D, H / D, bstate);
        if (sideSkin !== skin) {
          try {
            var a1 = o.getImageData(1, 1, 1, 1).data, a2 = o.getImageData(1, Math.round(H * 0.5), 1, 1).data, a3 = o.getImageData(1, H - 2, 1, 1).data;
            var gr = g.createLinearGradient(0, 0, 0, H);
            gr.addColorStop(0, "rgb(" + a1[0] + "," + a1[1] + "," + a1[2] + ")");
            gr.addColorStop(0.5, "rgb(" + a2[0] + "," + a2[1] + "," + a2[2] + ")");
            gr.addColorStop(1, "rgb(" + a3[0] + "," + a3[1] + "," + a3[2] + ")");
            sideFill = gr; sideSkin = skin;
          } catch (e) { sideFill = "#0b0818"; sideSkin = skin; }
        }
        g.setTransform(1, 0, 0, 1, 0, 0); g.fillStyle = sideFill; g.fillRect(0, 0, W, H);
        g.drawImage(oc, Math.round((W - pw) / 2), 0);
        return;
      }
      g.setTransform(D, 0, 0, D, 0, 0); g.clearRect(0, 0, W / D, H / D);
      TH.draw(skin, g, W / D, H / D, bstate);
      g.setTransform(1, 0, 0, 1, 0, 0);
    }
  };

  // ---------- frame loop (about 30 pictures a second; rests when closed, hidden or when lights are off) ----------
  function draw(ts, once) {
    var fn = DRAW.scene, target = playing() ? 1 : 0.06;
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
