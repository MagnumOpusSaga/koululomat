/* Koululomat: laskuri, kortit ja väriprofiili lasketaan selaimessa kuluvasta päivästä,
   jotta sivu on oikein myös rakennusten välillä (esim. joululoman alettua). Ei ulkoisia kutsuja. */
(function () {
  var el = document.getElementById("hd");
  var SV = document.documentElement.lang === "sv";
  var S = SV
    ? { hol: { syys: "Höstlov", joulu: "Jullov", talvi: "Sportlov", kesa: "Sommarlov" }, n1: "natt", n2: "nätter",
        to: function (k) { return "Till " + S.hol[k].toLowerCase() + "et är det"; }, now: function (k) { return S.hol[k] + " nu!"; },
        starts: "börjar", week: "vecka", est: "uppskattning", past: "Redan över!", on: "Lov nu!", bar: "Från lov till lov: avklarat",
        wd: ["sö", "må", "ti", "on", "to", "fr", "lö"], over: "är över", aria: "Nedräkning" }
    : { hol: { syys: "Syysloma", joulu: "Joululoma", talvi: "Hiihtoloma", kesa: "Kesäloma" }, n1: "yö", n2: "yötä",
        to: function (k) { return S.hol[k] + "an on"; }, now: function (k) { return S.hol[k] + " on nyt!"; },
        starts: "alkaa", week: "viikko", est: "arvio", past: "Ohi jo!", on: "Nyt lomalla!", bar: "Lomasta lomaan: matkaa takana",
        wd: ["su", "ma", "ti", "ke", "to", "pe", "la"], over: "on ohi", aria: "Lähtölaskuri" };
  function D(s) { return new Date(s + "T00:00:00"); }
  var T = new Date(); T.setHours(0, 0, 0, 0);
  function days(a, b) { return Math.round((b - a) / 864e5); }
  function nn(n) { return n === 1 ? S.n1 : S.n2; }
  function wk(d) { d = new Date(d); d.setDate(d.getDate() + 3 - (d.getDay() + 6) % 7); var w1 = new Date(d.getFullYear(), 0, 4);
    return 1 + Math.round(((d - w1) / 864e5 - 3 + (w1.getDay() + 6) % 7) / 7); }
  function f1(d, y) { return d.getDate() + "." + (d.getMonth() + 1) + "." + (y ? d.getFullYear() : ""); }
  function range(a, b) { return a.getFullYear() === b.getFullYear() ? f1(a) + "–" + f1(b, 1) : f1(a, 1) + "–" + f1(b, 1); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  // pelkkä hiihtolomasivu tms.: #cd + data-e (loppu) + data-k
  if (!el) {
    var cd = document.getElementById("cd");
    if (!cd) return;
    var a = D(cd.dataset.d), e = cd.dataset.e ? D(cd.dataset.e) : null, k = cd.dataset.k, x = days(T, a);
    var lead = cd.previousElementSibling, unit = cd.nextElementSibling;
    if (x >= 0) { cd.textContent = x; if (unit) unit.textContent = nn(x) + "!"; }
    else if (k && e && T <= e) { if (lead) lead.textContent = S.now(k); cd.textContent = "🎉"; if (unit) unit.textContent = ""; }
    else if (k) { if (lead) lead.textContent = S.hol[k] + " " + S.over; cd.textContent = "✓"; if (unit) unit.textContent = ""; }
    return;
  }
  var H = JSON.parse(el.textContent);
  var all = H.h.map(function (h) { return { k: h[0], a: D(h[1]), b: D(h[2]), y: h[3], c: h[4], s: h[1] }; });
  var nxt = all.filter(function (h) { return h.b >= T; })[0];

  // kortit
  document.querySelectorAll(".card[data-k]").forEach(function (c) {
    var a = D(c.dataset.a), b = D(c.dataset.b), n = c.querySelector(".n"), past = b < T;
    c.classList.toggle("past", past);
    c.classList.toggle("now", !!(nxt && nxt.k === c.dataset.k && nxt.y === H.cy));
    if (!n) return;
    if (past) { n.textContent = S.past; n.style.color = "#6B5847"; }
    else if (a <= T) n.textContent = S.on;
    else { var x = days(T, a); n.textContent = x + " " + nn(x); }
  });

  // ylin rivi (K4-B): "Joululoma alkaa ma 21.12. – 25 yötä" / "Joululoma on nyt – koulu jatkuu to 7.1."
  var tl = document.getElementById("tl");
  if (tl) {
    if (!nxt) { tl.hidden = true; }
    else {
      var ka = nxt.a, txt;
      if (ka <= T) {
        var bk = new Date(nxt.b); bk.setDate(bk.getDate() + 1);
        while (bk.getDay() === 0 || bk.getDay() === 6) bk.setDate(bk.getDate() + 1);
        txt = SV ? S.hol[nxt.k] + " nu – skolan fortsätter " + S.wd[bk.getDay()] + " " + f1(bk)
                 : S.hol[nxt.k] + " on nyt – koulu jatkuu " + S.wd[bk.getDay()] + " " + f1(bk);
      } else {
        var nd = days(T, ka);
        if (SV && nxt.k === "kesa") { var le = new Date(ka); le.setDate(le.getDate() - 1);
          txt = "Skolan slutar " + S.wd[le.getDay()] + " " + f1(le) + " – " + nd + " " + nn(nd) + " till sommarlovet"; }
        else txt = S.hol[nxt.k] + (SV ? " börjar " : " alkaa ") + S.wd[ka.getDay()] + " " + f1(ka) + " – " + nd + " " + nn(nd);
      }
      tl.className = "topline" + (nxt.c === "arvio" ? " est" : "");
      tl.innerHTML = esc(txt) + (nxt.c === "arvio" ? " " + H.bd.arvio : "");
    }
  }

  // laskuri
  var hero = document.querySelector(".hero[data-live]");
  if (!hero) return;
  if (!nxt) { hero.hidden = true; return; }
  var k = nxt.k, a = nxt.a, b = nxt.b, on = a <= T, n = days(T, a), est = nxt.c === "arvio";
  var prev = all.filter(function (h) { return h.b < a; }).map(function (h) { var d = new Date(h.b); d.setDate(d.getDate() + 1); return d; });
  if (H.s[nxt.y]) prev.push(D(H.s[nxt.y]));
  prev = prev.filter(function (d) { return d < a; });
  var bar = "";
  if (prev.length && !on) {
    var s0 = new Date(Math.max.apply(null, prev));
    if (s0 <= T) {
      var pct = Math.max(0, Math.min(100, Math.round(100 * days(s0, T) / Math.max(1, days(s0, a)))));
      bar = '<div class="bar"><div><i style="width:' + pct + '%"></i></div><p>' + S.bar + " " + pct + " %</p></div>";
    }
  }
  var when = (k === "kesa" ? S.starts + " " + S.wd[a.getDay()] + " " + f1(a, 1) : range(a, b)) +
             (k === "syys" || k === "talvi" ? " · " + S.week + " " + wk(a) : "");
  var hv = SV ? S.hol[k].toLowerCase() + "et" : S.hol[k].toLowerCase();
  var share = function (attrs) { return '<button class="share" type="button" hidden data-name="' + esc(H.n) + '"' + attrs + ">" + H.sh + "</button>"; };
  var body = on
    ? '<p class="lead">' + S.now(k) + '</p><div class="big" aria-hidden="true">🎉</div>' + share(' data-text="' + esc(H.n + ": " + S.now(k)) + '"')
    : '<p class="lead">' + S.to(k) + '</p><div class="big" id="cd" data-d="' + nxt.s + '">' + n + '</div><p class="unit">' + nn(n) + "!</p>" + share(' data-hol="' + hv + '"');
  hero.className = "hero" + (est ? " est" : "");
  hero.innerHTML = H.i[k] + body + '<p class="when">' + when + (est ? " (" + S.est + ")" : "") + '</p><p style="margin:6px 0 0">' + H.bd[nxt.c] + "</p>" + bar;
  // väriprofiili seuraavan loman mukaan (arvio = brändiväri)
  var th = H.th[est ? "brand" : k];
  if (th) { document.body.setAttribute("style", th); var m = document.querySelector('meta[name="theme-color"]'); if (m) m.content = th.match(/--hero:([^;]+)/)[1]; }
})();
