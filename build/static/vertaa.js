/* Koululomat: kahden kunnan lomien vertailu. Ei evästeitä, ei seurantaa. */
(function () {
  var root = document.getElementById("cmp"); if (!root) return;
  var Y = root.getAttribute("data-year") || "2026-2027";
  var HOL = [["syys", "Syysloma", "#C2410C", "#FBE4D8"], ["joulu", "Joululoma", "#15803D", "#DCF2E3"],
             ["talvi", "Hiihtoloma", "#1D6FB8", "#DDEAF7"], ["kesa", "Kesäloma", "#8A5A00", "#FFF0C7"]];
  var WD = ["su", "ma", "ti", "ke", "to", "pe", "la"];
  var sel = { a: null, b: null }, D = null;
  function q(k) { var m = new RegExp("[?&]" + k + "=([^&]+)").exec(location.search); return m ? decodeURIComponent(m[1]) : null; }
  function dt(s) { return new Date(s + "T00:00:00"); }
  function f(s) { var d = dt(s); return WD[d.getDay()] + " " + d.getDate() + "." + (d.getMonth() + 1) + "."; }
  function wk(s) { var d = dt(s); d.setDate(d.getDate() + 3 - (d.getDay() + 6) % 7); var w1 = new Date(d.getFullYear(), 0, 4);
    return 1 + Math.round(((d - w1) / 864e5 - 3 + (w1.getDay() + 6) % 7) / 7); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function weekdays(a, b) { var n = 0, d = dt(a), e = dt(b); while (d <= e) { var w = d.getDay(); if (w && w < 6) n++; d.setDate(d.getDate() + 1); } return n; }
  function line(k, r) {
    if (!r) return "–";
    var x = r[k]; if (!x) return "–";
    if (k === "kesa") return "koulu loppuu " + f(x);
    return f(x[0]) + "–" + f(x[1]) + (k === "syys" || k === "talvi" ? " · vk " + wk(x[0]) : "");
  }
  function verdict(k, ra, rb) {
    if (!ra || !rb || !ra[k] || !rb[k]) return ["", "#6B5847"];
    if (k === "kesa") return ra[k] === rb[k] ? ["Kesäloma alkaa samana päivänä", "#17602E"] : ["Kesäloma alkaa eri päivänä", "#8A5A00"];
    var a = ra[k], b = rb[k];
    if (a[0] === b[0] && a[1] === b[1]) return ["✓ Sama loma – lomailkaa yhdessä!", "#17602E"];
    var s = a[0] > b[0] ? a[0] : b[0], e = a[1] < b[1] ? a[1] : b[1];
    if (s <= e) { var n = weekdays(s, e); return ["Yhteistä lomaa " + n + " arkipäivä" + (n === 1 ? "" : "ä") + " (" + f(s) + "–" + f(e) + ")", "#8A5300"]; }
    return ["✗ Eri aikaan – ei yhteistä lomaa", "#9B1C1C"];
  }
  function render() {
    if (!sel.a || !sel.b) { root.innerHTML = '<p class="src">Valitse kaksi kuntaa, niin näet lomat vierekkäin ja montako päivää lomaa on yhtä aikaa.</p>'; return; }
    var A = D[sel.a], B = D[sel.b];
    if (!A || !B) { root.innerHTML = '<p class="src">Kuntaa ei löytynyt.</p>'; return; }
    var ra = A.y[Y], rb = B.y[Y], same = 0, html = "";
    HOL.forEach(function (h) {
      var v = verdict(h[0], ra, rb); if (v[0].indexOf("✓") === 0) same++;
      html += '<div class="card" style="--c:' + h[2] + ';margin-bottom:12px"><div class="gh"><div class="ic" style="background:' + h[3] + ';margin:0">' +
        '<b style="color:' + h[2] + ';font-size:22px">' + h[1][0] + '</b></div><b style="font-size:20px">' + h[1] + '</b></div>' +
        '<div class="cmpr"><span>' + esc(A.n) + '</span><b>' + line(h[0], ra) + '</b></div>' +
        '<div class="cmpr"><span>' + esc(B.n) + '</span><b>' + line(h[0], rb) + '</b></div>' +
        (v[0] ? '<div style="font-weight:900;color:' + v[1] + ';margin-top:6px">' + v[0] + '</div>' : "") + '</div>';
    });
    var est = [A, B].filter(function (x) { return (x.y[Y] || {}).c === "arvio"; }).map(function (x) { return x.n; });
    root.innerHTML = '<h2 style="margin-top:22px">' + esc(A.n) + ' ja ' + esc(B.n) + ' – lukuvuosi ' + Y.replace("-", "–") + '</h2>' + html +
      (est.length ? '<p class="src">' + est.map(esc).join(" ja ") + ': arvio – kunnan päätöstä ei vielä löytynyt.</p>' : "") +
      '<p class="src">Tarkat päivät ja lähteet: <a href="/fi/' + sel.a + '/">' + esc(A.n) + '</a> · <a href="/fi/' + sel.b + '/">' + esc(B.n) + '</a></p>';
    try { history.replaceState(null, "", "/vertaa/?a=" + sel.a + "&b=" + sel.b); } catch (e) {}
  }
  fetch("/lomat.json").then(function (r) { return r.json(); }).then(function (j) {
    D = j; sel.a = q("a"); sel.b = q("b");
    ["a", "b"].forEach(function (k) { var i = document.getElementById("q" + k); if (sel[k] && D[sel[k]] && i) i.value = D[sel[k]].n; });
    render();
  });
  document.addEventListener("kuntapick", function (e) {
    var k = e.target.getAttribute("data-pick"); sel[k] = e.detail.s; if (D) render();
  });
})();
