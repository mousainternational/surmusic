// © 2026 Mousa International Software House. All rights reserved.
// Sur Music — talk to the radio: press the microphone (or the V key) and say, for example, "play Radio Pakistan",
// "naat chalao", "AI podcast", "next", "volume up". The browser's own speech service listens; nothing is stored by us.
(function () {
  "use strict";
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var P = { "top-pakistan": "/podcasts" };
  var bar = document.getElementById("pl-play") && document.getElementById("pl-play").parentNode;
  if (!bar) return;
  var live = document.createElement("span"); live.className = "sr"; live.setAttribute("role", "status"); live.setAttribute("aria-live", "polite"); bar.appendChild(live);
  function say(t) { live.textContent = ""; setTimeout(function () { live.textContent = t; }, 40); }
  function lang() { try { return localStorage.getItem("sm-voice-lang") || "en-IN"; } catch (e) { return "en-IN"; } }
  var btn = document.createElement("button");
  btn.type = "button"; btn.id = "pl-mic"; btn.className = "pl-btn pl-mic"; btn.title = "Speak a command (key V)";
  btn.setAttribute("aria-label", "Speak a command. For example: play Radio Pakistan, next, volume up. Shortcut: V");
  btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V21h2v-3.1A7 7 0 0 0 19 11z"/></svg>';
  var share = document.getElementById("pl-share"); bar.insertBefore(btn, share || null);
  if (!SR) { btn.addEventListener("click", function () { say("Voice commands need Chrome or Edge on this device."); }); }
  var rec = null, on = false;
  function go(href, autoplay) {
    try { if (autoplay) sessionStorage.setItem("sm-voice-autoplay", String(Date.now())); } catch (e) { /* ignore */ }
    if (window.SurNav) window.SurNav(href); else location.href = href;
  }
  function click(id) { var e = document.getElementById(id); if (e) e.click(); }
  function vol(d) { var v = document.getElementById("pl-vol"); if (!v) return; v.value = Math.max(0, Math.min(1, Number(v.value) + d)); v.dispatchEvent(new Event("input")); say("Volume " + Math.round(v.value * 100) + " percent"); }
  function run(text) {
    var c = window.SurVoice && window.SurVoice.parse(text);
    if (!c) { say("I did not understand " + text + ". Try again."); return; }
    var playing = (document.getElementById("player") || document.body).getAttribute("data-state") === "playing" || document.querySelector("[data-state=playing]");
    if (c.cmd === "stop" || c.cmd === "pause") { if (playing) click("pl-play"); say("Stopped."); }
    else if (c.cmd === "resume") { if (!playing) click("pl-play"); say("Playing."); }
    else if (c.cmd === "next") { click("pl-next"); say("Next station."); }
    else if (c.cmd === "prev") { click("pl-prev"); say("Previous station."); }
    else if (c.cmd === "vol+") vol(0.15);
    else if (c.cmd === "vol-") vol(-0.15);
    else if (c.cmd === "podcast") { say("Opening " + c.slug + " podcasts."); go(P[c.slug] || "/podcasts/c/" + encodeURIComponent(c.slug), false); }
    else if (c.cmd === "category") { say("Playing " + c.cat + "."); go("/search?q=" + encodeURIComponent(c.cat), true); }
    else if (c.cmd === "play") { say("Looking for " + c.q + "."); go("/search?q=" + encodeURIComponent(c.q), true); }
  }
  function listen() {
    if (!SR) { say("Voice commands need Chrome or Edge on this device."); return; }
    if (on && rec) { try { rec.stop(); } catch (e) { /* ignore */ } return; }
    rec = new SR(); rec.lang = lang(); rec.interimResults = false; rec.maxAlternatives = 1;
    rec.onstart = function () { on = true; btn.classList.add("on"); btn.setAttribute("aria-pressed", "true"); say("Listening. Say your command."); };
    rec.onend = function () { on = false; btn.classList.remove("on"); btn.setAttribute("aria-pressed", "false"); };
    rec.onerror = function (e) { say(e.error === "not-allowed" ? "Please allow the microphone for this site." : e.error === "no-speech" ? "I did not hear anything. Press V and try again." : "Voice is not available right now."); };
    rec.onresult = function (e) { var t = e.results[0] && e.results[0][0] && e.results[0][0].transcript; if (t) { say("You said: " + t); setTimeout(function () { run(t); }, 700); } };
    try { rec.start(); } catch (e) { say("Voice is busy. Try again."); }
  }
  btn.addEventListener("click", listen);
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.defaultPrevented) return;
    var t = e.target, tag = (t && t.tagName) || "", typing = /^(INPUT|TEXTAREA|SELECT)$/.test(tag) || (t && t.isContentEditable);
    var combo = e.altKey && e.shiftKey; if (typing && !combo) return; if (e.altKey && !combo) return;
    if ((e.code || "") === "KeyV" || (e.key || "").toLowerCase() === "v") { listen(); e.preventDefault(); }
  });
  // after "play ..." the search page opens; start the first station there
  function autoplay() {
    var stamp = 0; try { stamp = Number(sessionStorage.getItem("sm-voice-autoplay") || 0); } catch (e) { return; }
    if (!stamp || Date.now() - stamp > 15000) return;
    var tries = 0, t = setInterval(function () {
      var b = document.querySelector("main ul.stations li.st .st-play");
      if (b) { clearInterval(t); try { sessionStorage.removeItem("sm-voice-autoplay"); } catch (e) { /* ignore */ } b.click(); say("Playing."); }
      else if (++tries > 30) clearInterval(t);
    }, 300);
  }
  autoplay(); document.addEventListener("page:load", autoplay);
  var lsel = document.getElementById("voice-lang");
  if (lsel) { lsel.value = lang(); lsel.addEventListener("change", function () { try { localStorage.setItem("sm-voice-lang", lsel.value); } catch (e) { /* ignore */ } say("Voice language saved."); }); }
})();
