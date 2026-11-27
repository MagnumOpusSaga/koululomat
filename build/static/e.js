/* Koululomat: nimetön laskuri (K4-D). Lähettää vain "sivua katsottu / mitä painettiin / poistui heti" -tiedon
   päiväsummiin. Ei evästeitä, ei tunnisteita, ei IP-tallennusta. Kunnioittaa Do Not Track- ja GPC-asetusta. */
(function () {
  if (location.hostname !== "koululomat.fi" || navigator.doNotTrack === "1" || navigator.globalPrivacyControl || !navigator.sendBeacon) return;
  var b = document.body, pt = b.getAttribute("data-pt") || "muu", own = b.getAttribute("data-own") || "0";
  var t0 = Date.now(), clicks = 0, sent = false;
  function send(k, v) { try { navigator.sendBeacon("/api/e", JSON.stringify({ k: k, v: v })); } catch (e) {} }
  send("view", pt + ":" + own);
  function target(el) {
    var a = el.closest("a,button,summary,[role=tab],.aco");
    if (!a) return null;
    if (a.closest(".share")) return "jaa";
    if (a.id === "kuva") return "kuva";
    if (a.id === "tulosta") return "tulosta";
    if (a.getAttribute("role") === "tab") return "tab_" + (a.getAttribute("aria-controls") || "").replace("p-", "");
    if (a.classList.contains("aco")) return "haku_valinta";
    if (a.tagName === "SUMMARY") return "ilmoitus_auki";
    var h = a.getAttribute("href") || "";
    if (/\.ics$/.test(h)) return "kalenteri";
    if (h.indexOf("/vertaa/") === 0) return "vertaa";
    if (a.closest(".lng")) return "kieli";
    if (a.classList.contains("card")) return "kortti_" + (a.getAttribute("data-k") || "");
    if (a.classList.contains("tile")) return "lomaruutu";
    if (a.classList.contains("acard")) return "artikkeli";
    if (a.classList.contains("row")) return "vastausrivi";
    if (/^https?:/.test(h) && h.indexOf(location.host) < 0) return "lahde";
    if (/^\/(fi|sv)\/[a-z0-9-]+\/$/.test(h)) return "kuntalinkki";
    if (h.charAt(0) === "/") return "sisalinkki";
    if (h.charAt(0) === "#") return "ankkuri";
    return a.tagName === "BUTTON" ? "nappi" : null;
  }
  document.addEventListener("click", function (e) {
    var t = target(e.target);
    if (t && clicks < 20) { clicks++; send("click", pt + ">" + t); }
  }, true);
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (clicks < 20) { clicks++; send("click", pt + ">" + (f.getAttribute("action") === "/api/report" ? "ilmoitus_lahetetty" : "haku")); }
  }, true);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden" && !sent && !clicks && Date.now() - t0 < 15000) { sent = true; send("quick_exit", pt); }
  });
})();
