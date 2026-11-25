"""Automaattiset tarkistukset: koulupäivälaskenta, järkevyyssäännöt, kaksi lähdettä,
ehdotus vs. päätös, muutosvalvonta."""
import json
from datetime import date, timedelta
from pathlib import Path

from .cal import school_year_holidays, week_of, weekdays

FI_REDUCING = ("itsenäisyyspäivä", "loppiainen", "vappu")  # arkipäivälle osuessaan vähentävät 190:stä
HOLIDAY_FIELDS = ("syys", "joulu", "talvi", "paasiainen")


def _d(s):
    return date.fromisoformat(s) if s else None


ALAND = {"035", "043", "060", "062", "065", "076", "170", "295", "318", "417", "438", "478", "736", "766", "771", "941"}


def expected_days(country: str, y1: int):
    if country == "ax":
        return None  # Ahvenanmaalla oma grundskolelag; ei 190 päivän sääntöä tässä muodossa
    if country == "fi":
        h = school_year_holidays("fi", y1)
        reduce = sum(1 for d, n in h.items() if n in FI_REDUCING and d.weekday() < 5
                     and date(y1, 8, 1) <= d <= date(y1 + 1, 6, 30))
        return 190 - reduce
    if country == "no":
        return 190
    if country == "se":
        return 178  # vähintään
    return None


def count_school_days(country: str, year: str, r: dict):
    """Laskee koulupäivät luetuista päivistä. None, jos alku tai loppu puuttuu."""
    y1 = int(year[:4])
    s = _d((r.get("start") or {}).get("start"))
    e = _d((r.get("end") or {}).get("start"))
    if not s or not e:
        return None, "alku tai loppu puuttuu"
    off = set()
    for k in HOLIDAY_FIELDS:
        if k in r:
            off |= set(weekdays(_d(r[k]["start"]), _d(r[k]["end"])))
    for f in r.get("free", []):
        off |= set(weekdays(_d(f["start"]), _d(f["end"])))
    hol = school_year_holidays("fi" if country == "ax" else country, y1)
    off |= {d for d in hol if d.weekday() < 5}
    days = [d for d in weekdays(s, e) if d not in off]
    sats = {_d(x["start"]) for x in r.get("saturday", []) if _d(x["start"]).weekday() == 5 and s <= _d(x["start"]) <= e}
    # lukukauden ensimmäinen/viimeinen päivä lauantaina = koulupäivä (joulujuhla, kevätjuhla)
    for k, pos in (("term1", "end"), ("term2", "start"), ("term1", "start")):
        dd = _d((r.get(k) or {}).get(pos))
        if dd and dd.weekday() == 5 and s <= dd <= e:
            sats.add(dd)
    if e.weekday() == 5:
        sats.add(e)
    note = ""
    if "joulu" not in r:
        note = "joululoma puuttuu"
    return len(days) + len(sats), note


def plausibility(country: str, year: str, r: dict) -> list:
    """Palauttaa listan poikkeamista (ei hylkää – menee tarkistusjonoon)."""
    issues = []
    rules = {
        "ax": {"syys": (41, 44), "talvi": (7, 10), "start_week": (32, 35), "end_week": (22, 24)},
        "fi": {"syys": (41, 44), "talvi": (7, 11), "start_week": (31, 34), "end_week": (22, 22)},
        "no": {"syys": (39, 42), "talvi": (7, 10), "start_week": (33, 35), "end_week": (24, 26)},
        "se": {"syys": (43, 45), "talvi": (7, 11), "start_week": (33, 35), "end_week": (23, 25)},
        "dk": {"syys": (42, 42), "talvi": (7, 8), "start_week": (32, 33), "end_week": (25, 27)},
    }[country]
    for k in ("syys", "talvi"):
        if k in r:
            w = week_of(_d(r[k]["start"]))
            lo, hi = rules[k]
            if not lo <= w <= hi:
                issues.append(f"{k}: viikko {w} (odotettu {lo}–{hi})")
            n = len(list(weekdays(_d(r[k]["start"]), _d(r[k]["end"]))))
            if n > 6:
                issues.append(f"{k}: {n} arkipäivää (liian pitkä)")
    if "start" in r:
        w = week_of(_d(r["start"]["start"]))
        if not rules["start_week"][0] <= w <= rules["start_week"][1]:
            issues.append(f"alku viikolla {w}")
    if "end" in r:
        d = _d(r["end"]["start"])
        if not rules["end_week"][0] <= week_of(d) <= rules["end_week"][1]:
            issues.append(f"loppu viikolla {week_of(d)}")
        if country == "fi" and d.weekday() not in (4, 5):
            issues.append("loppu ei pe/la")
    if "joulu" in r:
        a, b = _d(r["joulu"]["start"]), _d(r["joulu"]["end"])
        if not (date(a.year, 12, 17) <= a <= date(a.year, 12, 28)) or not ((b.month == 1 and b.day <= 9) or (b.month == 12 and b.day >= 27)):
            issues.append(f"joululoma {a}–{b} epätavallinen")
    y1 = int(year[:4])
    for k in HOLIDAY_FIELDS + ("start", "end"):
        if k in r:
            d = _d(r[k]["start"])
            if not date(y1, 7, 15) <= d <= date(y1 + 1, 6, 30):
                issues.append(f"{k} {d} ei kuulu lukuvuoteen {year}")
    return issues


def run_checks(country: str, year: str, r: dict) -> dict:
    exp = expected_days(country, int(year[:4]))
    calc, note = count_school_days(country, year, r)
    doc = r.get("days_doc")
    res = {"expected_days": exp, "calc_days": calc, "doc_days": doc, "calc_note": note}
    if calc is None or exp is None:
        res["days_ok"] = None if doc is None or calc is None else calc == doc
    elif country == "se":
        res["days_ok"] = calc >= exp
    else:
        # kunnan oma asiakirja ilmoittaa lain mukaisen määrän ja oma laskenta eroaa ≤ 2 päivää (yleensä sanallisesti
        # ilmoitettu vapaapäivä tai lauantaityöpäivä, jota ei voi lukea päivämääränä) -> kunnan ilmoitus ratkaisee
        res["days_ok"] = calc == exp or (doc is not None and calc == doc) or (doc == exp and abs(calc - exp) <= 2)
    res["plausibility"] = plausibility(country, year, r)
    return res


def confidence(fields_sources: dict, is_proposal: bool, days_ok, official: bool, complete: bool = True) -> str:
    """varmistettu: 2 riippumatonta lähdettä samaa mieltä TAI virallinen päätös + laskenta ok.
    Puuttuva lomakenttä -> ei koskaan varmistettu."""
    if is_proposal:
        return "ehdotus"
    multi = all(len(v) >= 2 for v in fields_sources.values()) if fields_sources else False
    if days_ok is False or not complete:
        return "yksi_lähde" if fields_sources else "arvio"  # laskenta ei täsmää -> tarkistusjonoon, ei koskaan varmistettu
    if multi or (official and days_ok):
        return "varmistettu"
    return "yksi_lähde" if fields_sources else "arvio"


# ---------- muutosvalvonta ----------

class ChangeMonitor:
    """Tallentaa jokaisen lähteen sisällön tiivisteen; muuttunut -> luetaan uudelleen."""

    def __init__(self, path):
        self.path = Path(path)
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {}

    def check(self, url: str, h: str, now: str) -> str:
        prev = self.state.get(url)
        self.state[url] = {"hash": h, "seen": now, "first": (prev or {}).get("first", now)}
        if prev is None:
            return "uusi"
        return "sama" if prev["hash"] == h else "muuttunut"

    def save(self):
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=0))
