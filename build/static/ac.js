/* Koululomat: kuntahaun ennakoivat ehdotukset. Ei evästeitä, ei seurantaa, ei ulkoisia kutsuja. */
(function () {
  var D = null, P = null, SV = document.documentElement.lang === "sv";
  var HFI = { syys: "Syysloma", joulu: "Joululoma", talvi: "Hiihtoloma", kesa: "Kesäloma" },
      HSV = { syys: "Höstlov", joulu: "Jullov", talvi: "Sportlov", kesa: "Sommarlov" };
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
  function ed(a, b) {  // Damerau–Levenshtein (vierekkäinen vaihto = 1)
    var m = a.length, n2 = b.length, d = [], i, j;
    for (i = 0; i <= m; i++) { d[i] = [i]; }
    for (j = 0; j <= n2; j++) d[0][j] = j;
    for (i = 1; i <= m; i++) for (j = 1; j <= n2; j++) {
      var c = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
    return d[m][n2];
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
    var pre = f.getAttribute("data-prefix"), pickMode = f.hasAttribute("data-pick");
    if (!i || !L) return;
    function url(x) { return SV && x.ss ? "/sv/" + x.ss + "/" : pre && x.t ? pre + x.s + "/" : "/fi/" + x.s + "/"; }
    function pick(x) {  // vertailusivu: valinta täyttää kentän eikä siirry sivulle
      i.value = x.n; close();
      f.dispatchEvent(new CustomEvent("kuntapick", { detail: x, bubbles: true }));
    }
    if (pickMode) L.addEventListener("click", function (e) {
      var o = e.target.closest(".aco"); if (!o) return;
      e.preventDefault(); var j = parseInt(o.id.split("-").pop(), 10); if (items[j]) pick(items[j]);
    });
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
      if (!items.length && q.length >= 3) {  // kirjoitusvirhe ("helsnki", "jyvaskla"): lähimmät nimet
        var lim = q.length <= 5 ? 1 : 2;
        items = D.map(function (x) {
          var dd = Math.min(ed(q, x.k.slice(0, q.length)), ed(q, x.k.slice(0, q.length + 1)), ed(q, x.k), x.k2 ? ed(q, x.k2.slice(0, q.length)) : 99);
          return [dd, x];
        }).filter(function (p) { return p[0] <= lim; }).sort(function (p, r) { return p[0] - r[0] || p[1].k.length - r[1].k.length; })
          .slice(0, 6).map(function (p) { return p[1]; });
      }
      if (SV) {  // svenska: kommuner med svensk sida först
        items = st.concat(inc).sort(function (p, q) { return (q.ss ? 1 : 0) - (p.ss ? 1 : 0); }).slice(0, 6);
      }
      if (!items.length) {
        L.innerHTML = '<div class="acn">' + (SV ? "Ingen kommun hittades – kontrollera stavningen." : "Kuntaa ei löytynyt – tarkista kirjoitusasu.") + '</div>';
        L.hidden = false; return;
      }
      L.innerHTML = items.map(function (x, j) {
        var sub = SV && !x.ss ? "på finska" : x.r;
        // seuraava loma lasketaan tästä päivästä (sivu voi olla rakennettu päiviä sitten)
        var nx = (x.u || []).filter(function (h) { return nights(h[2]) >= 0; })[0];
        if (nx && !(SV && !x.ss)) {
          var m = nights(nx[1]), hn = (SV ? HSV : HFI)[nx[0]];
          if (SV) sub = m > 0 ? "Till " + hn.toLowerCase() + "et " + m + " " + (m === 1 ? "natt" : "nätter") : hn + " nu!";
          else sub += " · " + (m > 0 ? hn.toLowerCase() + "an " + m + " " + (m === 1 ? "yö" : "yötä") : m === 0 ? hn.toLowerCase() + " alkaa tänään!" : hn.toLowerCase() + " nyt!");
        }
        var p1 = SV && x.sv ? x.sv : x.n, p2 = SV && x.sv ? x.n : x.sv;
        return '<a role="option" id="' + L.id + "-" + j + '" class="aco' + (j === a ? " on" : "") + '" href="' + url(x) + '">' +
          "<b>" + hl(p1, q) + (p2 && p2 !== p1 ? " <small>(" + esc(p2) + ")</small>" : "") + "</b><span>" + esc(sub) + "</span></a>";
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
        if (x) { if (pickMode) pick(x); else location.href = url(x); }
      });
    });
    document.addEventListener("click", function (e) { if (!f.contains(e.target)) close(); });
    var m = /[?&]q=([^&]+)/.exec(location.search);
    if (m && f.hasAttribute("data-main")) { i.value = decodeURIComponent(m[1].replace(/\+/g, " ")); load().then(render); }
  });
})();

/* Jakonappi: puhelimessa avaa jakovalikon (WhatsApp, viestit…), muuten kopioi linkin. Ei seurantaparametreja. */
(function () {
  document.querySelectorAll("button.share").forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () {
      var cd = document.getElementById("cd"), txt = b.getAttribute("data-text") || document.title;
      if (cd && b.getAttribute("data-hol")) {
        var n = parseInt(cd.textContent, 10);
        txt = document.documentElement.lang === "sv"
          ? b.getAttribute("data-name") + ": till " + b.getAttribute("data-hol") + " " + n + " " + (n === 1 ? "natt" : "nätter") + "!"
          : b.getAttribute("data-name") + ": " + b.getAttribute("data-hol") + "an " + n + " " + (n === 1 ? "yö" : "yötä") + "!";
      }
      var url = location.origin + location.pathname;
      if (navigator.share) {
        navigator.share({ title: document.title, text: txt, url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(txt + " " + url).then(function () {
          var l = b.querySelector("span"), o = l.textContent;
          l.textContent = document.documentElement.lang === "sv" ? "Länken kopierad!" : "Linkki kopioitu!";
          setTimeout(function () { l.textContent = o; }, 2200);
        });
      }
    });
  });
})();
