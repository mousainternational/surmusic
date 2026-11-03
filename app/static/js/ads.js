// Sur Music — fill Google AdSense units (also after in-site navigation).
(function () {
  "use strict";
  function fill() {
    document.querySelectorAll("ins.adsbygoogle:not([data-adsbygoogle-status])").forEach(function (el) {
      if (el.dataset.smPushed) return;
      if (el.closest("[hidden]")) return;            // e.g. the big player while it is closed: filled when it opens
      el.dataset.smPushed = "1";
      try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) { /* ad blocked or not ready */ }
    });
  }
  window.SurAds = { fill: fill };
  document.addEventListener("DOMContentLoaded", fill);
  document.addEventListener("page:load", fill);
  if (document.readyState !== "loading") fill();
})();
