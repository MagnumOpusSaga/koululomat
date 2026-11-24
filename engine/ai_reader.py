"""Tekoälylukija (Claude Haiku 5.5, vaikeat Sonnet 5.5). Käytetään vain, kun sääntölukija ei
löydä tai tarkistukset hylkäävät. Avain ympäristömuuttujasta ANTHROPIC_API_KEY (GitHub-salaisuus),
ei koskaan koodiin tai dokumentteihin. Kuvat (kalenteriruudukot) luetaan visiolla.

24.11.: max_tokens 1500 katkaisi vastauksia (json-virhe ~70 %:ssa kunnista) -> 4096, virheitä ei välimuistiin.
"""
import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path

MODEL_FAST = os.environ.get("KOULULOMAT_MODEL_FAST", "claude-haiku-5-5")
MODEL_HARD = os.environ.get("KOULULOMAT_MODEL_HARD", "claude-sonnet-5-5")
PROMPT_VERSION = "kl-2"

SYSTEM = """Luet kunnan koulujen työ- ja loma-ajat dokumentista. Palauta VAIN JSON:
{"kunta_oikein": true|false, "dokumentti_kunta": "...", "tila": "päätetty"|"ehdotus",
 "lukuvuodet": {"2026-2027": {"koulumuoto": "perus|esi|lukio|kaikki",
   "alku": "YYYY-MM-DD", "syyslukukausi_loppu": "YYYY-MM-DD", "kevatlukukausi_alku": "YYYY-MM-DD",
   "loppu": "YYYY-MM-DD", "syysloma": ["YYYY-MM-DD","YYYY-MM-DD"], "joululoma": [...],
   "talviloma": [...], "paasiaisloma": [...], "vapaapaivat": ["YYYY-MM-DD"], "lauantaikoulupaivat": ["YYYY-MM-DD"],
   "koulupaivia_ilmoitettu": 190, "lainaukset": {"syysloma": "enintään 8 sanaa tekstistä", ...}}}}
Säännöt: älä arvaa. Jos päivää ei lue dokumentissa, jätä kenttä pois. Tarkista, että dokumentti koskee
kuntaa {kunta} eikä toista kuntaa tai yksittäistä koulua. Jos dokumentissa lukee ehdotus/luonnos/förslag/
forslag tai päivät ovat muotoa xx.xx, tila = ehdotus. Kalenteriruudukossa koodit: HF=høstferie, JF=juleferie,
VF=vinterferie, PF=påskeferie, SF/EF=sommer/elevfri; värikoodit selitteen mukaan. Kaksipalstaisessa
ruudukossa syksy (elo–joulu) ja kevät (tammi–kesä) ovat eri palstoissa: syysloma on loka-marraskuussa, talviloma helmi-maaliskuussa.
Ei selityksiä, ei koodilohkoja: vastaus alkaa merkillä { ja päättyy merkkiin }."""


def _client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=key)


def pdf_pages_png(pdf_path: str, max_pages=4, dpi=110) -> list:
    td = tempfile.mkdtemp()
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-l", str(max_pages), pdf_path, f"{td}/p"],
                   capture_output=True, timeout=120)
    return sorted(str(p) for p in Path(td).glob("p*.png"))


CACHE = Path(os.environ.get("KOULULOMAT_CACHE", Path(__file__).resolve().parent.parent / "cache"))


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def read_with_ai(kunta: str, text: str = "", images=(), hard=False, years=("2026-2027", "2027-2028"), key=None) -> dict | None:
    c = _client()
    if c is None:
        return None
    import hashlib
    ck = CACHE / ("ai_" + hashlib.sha1(f"{PROMPT_VERSION}|{hard}|{kunta}|{key or text[:20000]}|{len(images)}".encode()).hexdigest() + ".json")
    if ck.exists():
        cached = json.loads(ck.read_text())
        if not cached.get("error"):
            return cached
    content = []
    for img in images[:4]:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                     "data": base64.b64encode(Path(img).read_bytes()).decode()}})
    content.append({"type": "text", "text": f"Kunta: {kunta}. Lukuvuodet: {', '.join(years)}.\n\n{text[:14000]}"})
    import time
    msg = None
    for attempt in range(4):
        try:
            msg = c.messages.create(model=MODEL_HARD if hard else MODEL_FAST, max_tokens=4096,
                                    system=SYSTEM.replace("{kunta}", kunta),
                                    messages=[{"role": "user", "content": content}])
            break
        except Exception as e:  # ylikuorma / rajoitus: odota ja yritä uudelleen
            err = type(e).__name__
            time.sleep(5 * (attempt + 1))
    if msg is None:
        return {"error": f"api {err}"}
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    try:
        out = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        # virheellistä vastausta ei tallenneta välimuistiin -> luetaan uudelleen seuraavalla ajolla
        return {"error": f"json ({msg.stop_reason}, {msg.usage.output_tokens} t)", "raw": raw[-300:]}
    out["_usage"] = {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens, "model": msg.model}
    CACHE.mkdir(parents=True, exist_ok=True)
    ck.write_text(json.dumps(out, ensure_ascii=False))
    return out


def to_records(ai: dict) -> dict:
    """Tekoälyn JSON -> sama muoto kuin sääntölukijalla (extract_fi)."""
    from .extract_fi import _derive
    out = {}
    if not ai or ai.get("error") or ai.get("kunta_oikein") is False:
        return out
    for y, v in (ai.get("lukuvuodet") or {}).items():
        if not isinstance(v, dict) or v.get("koulumuoto") not in (None, "perus", "kaikki"):
            continue
        q = v.get("lainaukset") or {}
        r = {}
        def put(f, a, b=None, src=None):
            if a:
                r[f] = {"start": a, "end": b or a, "quote": ("AI: " + str(q.get(src or f, "")))[:180]}
        put("start", v.get("alku"), src="alku")
        put("end", v.get("loppu"), src="loppu")
        put("term1_end", v.get("syyslukukausi_loppu"))
        put("term2_start", v.get("kevatlukukausi_alku"))
        for f, k in (("syys", "syysloma"), ("joulu", "joululoma"), ("talvi", "talviloma"), ("paasiainen", "paasiaisloma")):
            x = v.get(k)
            if isinstance(x, list) and len(x) == 2 and all(x):
                put(f, x[0], x[1], src=k)
        r["free"] = [{"start": d, "end": d, "quote": "AI"} for d in (v.get("vapaapaivat") or []) if d]
        r["saturday"] = [{"start": d, "end": d, "quote": "AI"} for d in (v.get("lauantaikoulupaivat") or []) if d]
        if isinstance(v.get("koulupaivia_ilmoitettu"), int):
            r["days_doc"] = v["koulupaivia_ilmoitettu"]
        try:
            out[y] = _derive(y, r)
        except Exception:
            continue
    return out
