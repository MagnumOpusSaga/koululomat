"""NO: Lovdatan avoin data (Norsk Lovtidend avd. II) -> kuntien skolerute-asetukset.

Lähde: https://api.lovdata.no/v1/publicData/list (ei avainta). Tiedostot lovtidend-avd2-<vuosi>.tar.bz2
päivittyvät öisin. Sama norjalainen lukija käy myös kuntien omille forskrift-pdf:ille.
"""
import io
import re
import tarfile
from datetime import date

import requests

from .cal import clip_to_weekdays

API = "https://api.lovdata.no/v1/publicData"
MONTHS = {"januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7, "august": 8,
          "september": 9, "oktober": 10, "november": 11, "desember": 12}
MON = "|".join(MONTHS)
TITLE_RE = re.compile(r"(skole|skule)[- ]?og[- ]?feriedag|skolerut|skulerut", re.I)


def list_files():
    return requests.get(API + "/list", timeout=30).json()


def iter_forskrifter(filename: str):
    data = requests.get(f"{API}/get/{filename}", timeout=300).content
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:bz2") as tf:
        for m in tf:
            if not m.isfile():
                continue
            html = tf.extractfile(m).read().decode("utf8", "replace")
            t = re.search(r'<dd class="title">(.*?)</dd>', html, re.S)
            if t and TITLE_RE.search(t.group(1)):
                yield html


def meta(html: str) -> dict:
    def f(c):
        m = re.search(rf'<dd class="{c}">(.*?)</dd>', html, re.S)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else None
    return {"dokid": f("dokid"), "title": f("title"), "applies_to": f("appliesTo"),
            "in_force": f("dateInForce"), "published": f("dateOfPublication"),
            "url": "https://lovdata.no/" + (f("dokid") or "").replace("LTII/", "LTII/")}


def text_of(html: str) -> str:
    html = re.sub(r"</(tr|p|article|h\d|li)>", "\n", html)
    html = re.sub(r"</t[dh]>", " | ", html)
    return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", " ", html))


KW_NO = {
    "start": r"første\s+skoledag|fyrste\s+skuledag|skolestart|skulestart",
    "end": r"siste\s+skoledag(?!\s+før)|siste\s+skuledag(?!\s+før)",
    "term1_end": r"siste\s+skoledag\s+før\s+jul|siste\s+skuledag\s+før\s+jul",
    "term2_start": r"første\s+skoledag\s+etter\s+(jul|nyttår)\w*|fyrste\s+skuledag\s+etter\s+jul\w*",
    "syys": r"høstferie|haustferie",
    "joulu": r"(?<!etter )(?<!etter )juleferie(?!\s*\d+\.\s*januar)",
    "talvi": r"vinterferie",
    "paasiainen": r"påskeferie|påskefri",
    "free": r"elevfri|fridag|planleggingsdag",
}
DATE_NO = re.compile(rf"(\d{{1,2}})\.\s*({MON})?(?:\s*(20\d\d))?\s*(?:[–-]\s*(\d{{1,2}})\.\s*({MON})(?:\s*(20\d\d))?)?", re.I)


def extract_no(text: str, years=("2026-2027", "2027-2028")) -> dict:
    """Taulukko 'Skoleruta 2027–2028' -> kentät. Vuosi päätellään lukuvuoden otsikosta."""
    out = {}
    blocks = re.split(r"(?i)(?:skoleruta?|skuleruta?|skoleåret|skuleåret)\s*(20\d\d)\s*[–/-]\s*(20\d\d|\d\d)", text)
    for i in range(1, len(blocks) - 2, 3):
        y1 = int(blocks[i])
        key = f"{y1}-{y1 + 1}"
        if key not in years or key in out:
            continue
        body = blocks[i + 2][:4000]
        r = {}
        for f, rx in KW_NO.items():
            for m in re.finditer(rx, body, re.I):
                win = body[m.end():m.end() + 60]
                d = DATE_NO.search(win)
                if not d or (not d.group(2) and not d.group(5)):
                    continue
                d1, m1, _, d2, m2, _ = d.groups()
                mo2 = MONTHS[(m2 or m1).lower()]
                mo1 = MONTHS[(m1 or m2).lower()]
                yy = lambda mo: y1 if mo >= 7 else y1 + 1  # noqa: E731
                try:
                    a = date(yy(mo1), mo1, int(d1))
                    b = date(yy(mo2), mo2, int(d2)) if d2 else a
                except ValueError:
                    continue
                q = " ".join(body[max(0, m.start() - 5):m.end() + d.end() + 5].split())
                if f == "free":
                    r.setdefault("free", []).append({"start": a.isoformat(), "end": b.isoformat(), "quote": q})
                    continue
                elif f not in r:
                    r[f] = {"start": a.isoformat(), "end": b.isoformat(), "quote": q}
                break
        n = re.search(r"(?i)totalt?\s+antall\s+(skole|skule)dag\w*\s*\|?\s*(\d{3})", body)
        if n:
            r["days_doc"] = int(n.group(2))
        if "joulu" not in r and "term1_end" in r and "term2_start" in r:
            from datetime import timedelta
            s, e = clip_to_weekdays(date.fromisoformat(r["term1_end"]["start"]) + timedelta(1),
                                    date.fromisoformat(r["term2_start"]["start"]) - timedelta(1))
            if s:
                r["joulu"] = {"start": s.isoformat(), "end": e.isoformat(), "quote": "avledet", "derived": True}
        for k in ("syys", "joulu", "talvi", "paasiainen"):
            if k in r:
                s, e = clip_to_weekdays(date.fromisoformat(r[k]["start"]), date.fromisoformat(r[k]["end"]))
                if s:
                    r[k]["start"], r[k]["end"] = s.isoformat(), e.isoformat()
        out[key] = r
    return out
