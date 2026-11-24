/* Koululomat: kuntahaun ennakoivat ehdotukset. Ei evästeitä, ei seurantaa, ei ulkoisia kutsuja. */
(function () {
  var D = null, P = null;
  function n(v) {
    return (v || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
  }
  function load() {
    if (!P) P = fetch("/kunnat.json").then(function (r) { return r.json(); }).then(function (j) {
      D = j.map(function (x) { x.k = n(x.n); x.k2 = n(x.sv || ""); return x; });
      return D;
    });
    return P;
  }
  function nights(ds) {
    var t = new Date(ds + "T00:00:00"), d = new Date(); d.setHours(0, 0, 0, 0);
    return Math.round((t - d) / 864e5);
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function hl(name, q) {
    var k = n(name), i = k.indexOf(q);
    if (i < 0 || k.length !== name.length) return esc(name);
    return esc(name.slice(0, i)) + "<mark>" + esc(name.slice(i, i + q.length)) + "</mark>" + esc(name.slice(i + q.length));
  }
  document.querySelectorAll("form.search").forEach(function (f) {
    var i = f.querySelector("input"), L = f.querySelector(".acl"), items = [], a = -1;
    var pre = f.getAttribute("data-prefix");
    if (!i || !L) return;
    function url(x) { return pre && x.t ? pre + x.s + "/" : "/fi/" + x.s + "/"; }
    function close() { L.hidden = true; i.setAttribute("aria-expanded", "false"); i.removeAttribute("aria-activedescendant"); a = -1; }
    function render() {
      var q = n(i.value);
      if (q.length < 2 || !D) { close(); return; }
      var st = [], inc = [];
      D.forEach(function (x) {
        if (x.k.indexOf(q) === 0 || x.k2.indexOf(q) === 0) st.push(x);
        else if (x.k.indexOf(q) > 0 || (x.k2 && x.k2.indexOf(q) > 0)) inc.push(x);
      });
      items = st.concat(inc).slice(0, 6);
      if (!items.length) {
        L.innerHTML = '<div class="acn">Kuntaa ei löytynyt – tarkista kirjoitusasu.</div>';
        L.hidden = false; return;
      }
      L.innerHTML = items.map(function (x, j) {
        var sub = x.r;
        if (x.h && x.d) {
          var m = nights(x.d);
          if (m > 0) sub += " · " + x.h + "an " + m + " " + (m === 1 ? "yö" : "yötä");
          else if (m === 0) sub += " · " + x.h + " alkaa tänään!";
        }
        return '<a role="option" id="' + L.id + "-" + j + '" class="aco' + (j === a ? " on" : "") + '" href="' + url(x) + '">' +
          "<b>" + hl(x.n, q) + (x.sv && x.sv !== x.n ? " <small>(" + esc(x.sv) + ")</small>" : "") + "</b><span>" + esc(sub) + "</span></a>";
      }).join("");
      L.hidden = false;
      i.setAttribute("aria-expanded", "true");
      if (a >= 0) i.setAttribute("aria-activedescendant", L.id + "-" + a);
    }
    i.addEventListener("focus", load);
    i.addEventListener("input", function () { a = -1; load().then(render); });
    i.addEventListener("keydown", function (e) {
      if (L.hidden) return;
      if (e.key === "ArrowDown") { a = Math.min(a + 1, items.length - 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { a = Math.max(a - 1, 0); render(); e.preventDefault(); }
      else if (e.key === "Escape") close();
    });
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      load().then(function () {
        var q = n(i.value);
        if (!q) return;
        render();
        var x = (a >= 0 && items[a]) || D.filter(function (y) { return y.k === q || y.k2 === q; })[0] || items[0];
        if (x) location.href = url(x);
      });
    });
    document.addEventListener("click", function (e) { if (!f.contains(e.target)) close(); });
    var m = /[?&]q=([^&]+)/.exec(location.search);
    if (m && f.hasAttribute("data-main")) { i.value = decodeURIComponent(m[1].replace(/\+/g, " ")); load().then(render); }
  });
})();
