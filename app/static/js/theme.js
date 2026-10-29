// Apply the saved theme before first paint (avoids a flash of the wrong theme).
(function () {
  try {
    var t = localStorage.getItem("sm-theme");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage blocked: follow the system setting */ }
})();
