// Sur Music: draws the setup QR code for 2-step sign-in in the browser (the secret never leaves this page).
(function () {
  "use strict";
  var box = document.getElementById("qr");
  if (!box || typeof qrcode !== "function") return;
  var qr = qrcode(0, "M");
  qr.addData(box.getAttribute("data-uri"));
  qr.make();
  var n = qr.getModuleCount(), q = 4, size = n + q * 2;
  var NS = "http://www.w3.org/2000/svg";
  var svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 " + size + " " + size);
  svg.setAttribute("width", "220"); svg.setAttribute("height", "220");
  svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "QR code for your authenticator app");
  svg.setAttribute("shape-rendering", "crispEdges");
  var bg = document.createElementNS(NS, "rect");
  bg.setAttribute("width", size); bg.setAttribute("height", size); bg.setAttribute("fill", "#ffffff");
  svg.appendChild(bg);
  var d = "";
  for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) if (qr.isDark(r, c)) d += "M" + (c + q) + " " + (r + q) + "h1v1h-1z";
  var path = document.createElementNS(NS, "path");
  path.setAttribute("d", d); path.setAttribute("fill", "#000000");
  svg.appendChild(path);
  box.appendChild(svg);
})();
