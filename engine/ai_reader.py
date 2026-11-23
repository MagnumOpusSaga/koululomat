"""Tekoälylukija (Claude Haiku 5.5, vaikeat Sonnet 5.5). Käytetään vain, kun sääntölukija ei
löydä tai tarkistukset hylkäävät. Avain ympäristömuuttujasta ANTHROPIC_API_KEY (GitHub-salaisuus),
ei koskaan koodiin tai dokumentteihin. Kuvat (kalenteriruudukot) luetaan visiolla.

HUOM: ei testattu 24.11.2026 (avainta ei ollut työtilassa). Muoto sama kuin paivanlounaan ai_reader.py.
"""
import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path

MODEL_FAST = os.environ.get("KOULULOMAT_MODEL_FAST", "claude-haiku-5-5")
MODEL_HARD = os.environ.get("KOULULOMAT_MODEL_HARD", "claude-sonnet-5-5")
PROMPT_VERSION = "kl-1"

SYSTEM = """Luet kunnan koulujen työ- ja loma-ajat dokumentista. Palauta VAIN JSON:
{"kunta_oikein": true|false, "dokumentti_kunta": "...", "tila": "päätetty"|"ehdotus",
 "lukuvuodet": {"2026-2027": {"koulumuoto": "perus|esi|lukio|kaikki",
   "alku": "YYYY-MM-DD", "syyslukukausi_loppu": "YYYY-MM-DD", "kevatlukukausi_alku": "YYYY-MM-DD",
   "loppu": "YYYY-MM-DD", "syysloma": ["YYYY-MM-DD","YYYY-MM-DD"], "joululoma": [...],
   "talviloma": [...], "paasiaisloma": [...], "vapaapaivat": ["YYYY-MM-DD"], "lauantaikoulupaivat": ["YYYY-MM-DD"],
   "koulupaivia_ilmoitettu": 190, "lainaukset": {"syysloma": "lyhyt kohta tekstistä", ...}, "sivu": {"syysloma": 1}}}}
Säännöt: älä arvaa. Jos päivää ei lue dokumentissa, jätä kenttä pois. Tarkista, että dokumentti koskee
kuntaa {kunta} eikä toista kuntaa tai yksittäistä koulua. Jos dokumentissa lukee ehdotus/luonnos/förslag/
forslag tai päivät ovat muotoa xx.xx, tila = ehdotus. Kalenteriruudukossa koodit: HF=høstferie, JF=juleferie,
VF=vinterferie, PF=påskeferie, SF/EF=sommer/elevfri; värikoodit selitteen mukaan."""


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


def read_with_ai(kunta: str, text: str = "", images=(), hard=False, years=("2026-2027", "2027-2028")) -> dict | None:
    c = _client()
    if c is None:
        return None
    content = []
    for img in images[:4]:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                     "data": base64.b64encode(Path(img).read_bytes()).decode()}})
    content.append({"type": "text", "text": f"Kunta: {kunta}. Lukuvuodet: {', '.join(years)}.\n\n{text[:14000]}"})
    msg = c.messages.create(model=MODEL_HARD if hard else MODEL_FAST, max_tokens=1500,
                            system=SYSTEM.replace("{kunta}", kunta),
                            messages=[{"role": "user", "content": content}])
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    try:
        return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        return {"error": "json", "raw": raw[:500]}
