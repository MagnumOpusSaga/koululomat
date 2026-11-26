"""Indeksointiportti (spämmisuoja, Branun pysyvä sääntö 25.11.2026, claude/kirjasto/10-spamsuoja.md).

Jokainen sivu kuuluu johonkin sivutyyppiin, ja jokaisella tyypillä on oma datakynnys. Sivu menee indeksiin ja
sivukarttaan vain, jos kynnys ylittyy; muuten noindex (sivu on silti olemassa kävijöille). Sivu ilman tyyppiä on
virhe: rakennus pysähtyy. Raportti (gate_report.json) kertoo jokaisen tyypin määrät ja jokaisen noindexin syyn.
"""
import json
from collections import Counter, defaultdict

Y1 = "2026-2027"
HOLS = ("syys", "joulu", "talvi")

# datakynnykset sivutyypeittäin
MIN_KUNNAT_LOMA = 100      # lomasivu (fi): vähintään näin monen kunnan omat päivät kyseiselle lomalle
MIN_KUNNAT_LOMA_SV = 15    # lomasivu (sv): vähintään näin monen kunnan kielikohtaiset omat päivät
MIN_KUNNAT_ART = 100       # artikkeli: vähintään näin monen kunnan omat luvut
MIN_KUNNAT_ETUSIVU = 200

TYPES = {
    "etusivu": f"Etusivu: vähintään {MIN_KUNNAT_ETUSIVU} kunnan lomat kunnan omasta lähteestä",
    "etusivu_sv": f"Ruotsinkielinen etusivu: vähintään {MIN_KUNNAT_LOMA_SV} indeksoitavaa ruotsinkielistä kuntasivua",
    "kunta": "Kuntasivu: kunnan oma lähde kuluvalle lukuvuodelle, syys-, joulu- ja talviloma luettu (ei arvio)",
    "kunta_sv": "Ruotsinkielinen kuntasivu: kunnan oma lähde + kielikohtainen data (ruotsinkielisten koulujen päivät tai ruotsinkielinen lähde)",
    "loma": f"Lomasivu: vähintään {MIN_KUNNAT_LOMA} kunnan omat päivät kyseiselle lomalle",
    "loma_sv": f"Ruotsinkielinen lomasivu: vähintään {MIN_KUNNAT_LOMA_SV} kunnan kielikohtaiset omat päivät",
    "artikkeli": f"Artikkeli: oma kysymys (ei lomasivun kaksoiskappale) ja vähintään {MIN_KUNNAT_ART} kunnan omat luvut",
    "menetelma": "Menetelmäsivu (lähteet ja tarkistus): aina, läpinäkyvyyden vuoksi",
    "navi": "Navigointi, työkalu tai juridinen sivu ilman omaa dataa: ei indeksiin",
}


def own(v):
    return bool(v) and v.get("confidence") not in (None, "arvio") and all(k in v.get("fields", {}) for k in HOLS)


def kunta(rec):
    v = rec["years"].get(Y1)
    if own(v):
        return True, "oma lähde"
    return False, "arvio – kunnan omaa päätöstä ei löytynyt" if v else "ei tietoja"


def kunta_sv(raw, view_rec):
    """raw = alkuperäinen tietue (variant + alt), view_rec = ruotsinkielinen näkymä."""
    if not own(view_rec["years"].get(Y1)):
        return False, "arvio – kunnan omaa päätöstä ei löytynyt"
    if raw.get("variant") == "sv":
        return True, "ruotsinkielinen lähde"
    if own(((raw.get("alt") or {}).get("sv") or {}).get(Y1)):
        return True, "ruotsinkielisten koulujen omat päivät"
    return False, "vain suomenkielisten koulujen päivät (käännös, ei kielikohtaista dataa)"


def count_ok(n, minimum, what):
    return (n >= minimum), f"{n} {what} (raja {minimum})"


class Gate:
    def __init__(self):
        self.pages = {}  # path -> (tyyppi, ok, syy)

    def rec(self, path, ptype, ok, reason):
        if ptype not in TYPES:
            raise ValueError(f"tuntematon sivutyyppi {ptype} ({path})")
        self.pages[path] = (ptype, bool(ok), reason)

    def indexable(self):
        return [p for p, (_, ok, _) in self.pages.items() if ok]

    def ok(self, path):
        return self.pages.get(path, (None, False, None))[1]

    def report(self):
        by = defaultdict(Counter)
        why = defaultdict(Counter)
        for p, (t, ok, r) in self.pages.items():
            by[t]["indeksiin" if ok else "noindex"] += 1
            if not ok:
                why[t][r] += 1
        return {"tyypit": {t: {"kynnys": TYPES[t], "sivuja": sum(by[t].values()), "indeksiin": by[t]["indeksiin"],
                                "noindex": by[t]["noindex"], "noindex_syyt": dict(why[t])} for t in TYPES if by[t]},
                "yhteensa": {"sivuja": len(self.pages), "indeksiin": len(self.indexable())},
                "noindex_sivut": sorted(p for p, (_, ok, _) in self.pages.items() if not ok)}

    def print_report(self):
        r = self.report()
        print(f"\nIndeksointiportti: {r['yhteensa']['indeksiin']}/{r['yhteensa']['sivuja']} sivua indeksiin")
        for t, x in r["tyypit"].items():
            print(f"  {t:10} {x['indeksiin']:4} / {x['sivuja']:4} indeksiin   {x['kynnys']}")
            for why, n in x["noindex_syyt"].items():
                print(f"  {'':10} {n:4} noindex: {why}")
        return r


def dump(gate, path):
    with open(path, "w") as f:
        json.dump(gate.report(), f, ensure_ascii=False, indent=1)
