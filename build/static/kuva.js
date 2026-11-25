/* Koululomat: oman kunnan lomat kuvana (WhatsApp / jääkaapin ovi) ja tulostus. Kaikki tehdään selaimessa, ei palvelinkutsuja. */
(function () {
  /* koulumuotovälilehdet: ilman JS:ää kaikki taulukot näkyvät peräkkäin */
  var tl = document.querySelector(".tabs[role=tablist]");
  if (tl) {
    var tb = [].slice.call(tl.querySelectorAll("[role=tab]"));
    function sel(b, focus) {
      tb.forEach(function (x) { var on = x === b; x.setAttribute("aria-selected", on); x.tabIndex = on ? 0 : -1;
        document.getElementById(x.getAttribute("aria-controls")).hidden = !on; });
      if (focus) b.focus();
    }
    tl.hidden = false; sel(tb[0]);
    tb.forEach(function (b, i) {
      b.addEventListener("click", function () { sel(b); });
      b.addEventListener("keydown", function (e) {
        var j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? tb.length - 1 : null;
        if (j === null) return; e.preventDefault(); sel(tb[(j + tb.length) % tb.length], true);
      });
    });
  }
  var bi = document.getElementById("kuva"), bp = document.getElementById("tulosta");
  if (bp) { bp.hidden = false; bp.addEventListener("click", function () { window.print(); }); }
  if (!bi || !window.HTMLCanvasElement) return;
  bi.hidden = false;
  var slug = bi.getAttribute("data-s"), Y = bi.getAttribute("data-y") || "2026-2027";
  var HOL = [["syys", "Syysloma", "#C2410C", "#FBE4D8"], ["joulu", "Joululoma", "#15803D", "#DCF2E3"],
             ["talvi", "Hiihtoloma", "#1D6FB8", "#DDEAF7"], ["kesa", "Kesäloma", "#8A5A00", "#FFF0C7"]];
  var WD = ["su", "ma", "ti", "ke", "to", "pe", "la"];
  function dt(s) { return new Date(s + "T00:00:00"); }
  function f(s, y) { var d = dt(s); return WD[d.getDay()] + " " + d.getDate() + "." + (d.getMonth() + 1) + "." + (y ? d.getFullYear() : ""); }
  function wk(s) { var d = dt(s); d.setDate(d.getDate() + 3 - (d.getDay() + 6) % 7); var w1 = new Date(d.getFullYear(), 0, 4);
    return 1 + Math.round(((d - w1) / 864e5 - 3 + (w1.getDay() + 6) % 7) / 7); }
  function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
  function draw(rec) {
    var W = 1080, H = 1350, cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    var c = cv.getContext("2d"), r = rec.y[Y] || {};
    c.fillStyle = "#FFF6E5"; c.fillRect(0, 0, W, H);
    c.fillStyle = "#E8741E"; rr(c, 60, 60, W - 120, 250, 48); c.fill();
    c.fillStyle = "#fff"; c.font = "900 46px Nunito, sans-serif"; c.fillText("Koulujen lomat " + Y.replace("-", "–"), 110, 145);
    c.font = "900 92px Nunito, sans-serif"; var name = rec.n.length > 16 ? rec.n.slice(0, 16) + "…" : rec.n; c.fillText(name, 110, 255);
    var y0 = 360;
    HOL.forEach(function (h, i) {
      var y = y0 + i * 205;
      c.fillStyle = h[3]; rr(c, 60, y, W - 120, 180, 36); c.fill();
      c.fillStyle = h[2]; rr(c, 60, y, 22, 180, 11); c.fill();
      c.fillStyle = h[2]; c.font = "900 52px Nunito, sans-serif"; c.fillText(h[1], 120, y + 72);
      c.fillStyle = "#2A1B0F"; c.font = "800 48px Nunito, sans-serif";
      var t = "–";
      if (h[0] === "kesa" && r.kesa) t = "koulu loppuu " + f(r.kesa, true);
      else if (r[h[0]]) t = f(r[h[0]][0]) + " – " + f(r[h[0]][1], true) + ((h[0] === "syys" || h[0] === "talvi") ? "  ·  vk " + wk(r[h[0]][0]) : "");
      c.fillText(t, 120, y + 140);
    });
    c.fillStyle = "#6B5847"; c.font = "800 34px Nunito, sans-serif";
    c.fillText(r.c === "arvio" ? "Arvio – tarkista koululta" : "Tiedot kunnan omasta lähteestä", 60, H - 95);
    c.fillStyle = "#C2410C"; c.font = "900 44px Nunito, sans-serif"; c.fillText("koululomat.fi", W - 60 - c.measureText("koululomat.fi").width, H - 90);
    return cv;
  }
  bi.addEventListener("click", function () {
    var lbl = bi.querySelector("span"), o = lbl.textContent; lbl.textContent = "Tehdään kuvaa…";
    Promise.all([fetch("/lomat.json").then(function (x) { return x.json(); }), document.fonts ? document.fonts.ready : null]).then(function (a) {
      var rec = a[0][slug]; if (!rec) { lbl.textContent = o; return; }
      draw(rec).toBlob(function (blob) {
        var fn = "koululomat-" + slug + ".png", file = null;
        try { file = new File([blob], fn, { type: "image/png" }); } catch (e) {}
        lbl.textContent = o;
        if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
          navigator.share({ files: [file], title: "Koulujen lomat – " + rec.n }).catch(function () {});
        } else {
          var u = URL.createObjectURL(blob), l = document.createElement("a"); l.href = u; l.download = fn; document.body.appendChild(l); l.click();
          setTimeout(function () { URL.revokeObjectURL(u); l.remove(); }, 1000);
        }
      }, "image/png");
    });
  });
})();
