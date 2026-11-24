"""Kohtelias hakija: välimuisti levylle, robots.txt, hidastus per domain.

Yhteystieto robotin tunnisteeseen ympäristömuuttujasta KOULULOMAT_CONTACT (ei koodiin).
"""
import hashlib
import json
import os
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

CACHE = Path(os.environ.get("KOULULOMAT_CACHE", Path(__file__).resolve().parent.parent / "cache"))
CACHE.mkdir(parents=True, exist_ok=True)
CONTACT = os.environ.get("KOULULOMAT_CONTACT", "")
UA = f"KoululomatBot/0.1 (+{CONTACT})" if CONTACT else "KoululomatBot/0.1"
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
DELAY = float(os.environ.get("KOULULOMAT_DELAY", "0.7"))
MAX_BYTES = 25_000_000

_session = requests.Session()
_robots: dict = {}
_last: dict = {}


def _robots_ok(url: str) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    rp = _robots.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _session.get(base + "/robots.txt", timeout=10, headers={"User-Agent": UA})
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[base] = rp
    return rp.can_fetch("KoululomatBot", url)


def key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


def get(url: str, max_age_h: float = 24 * 7, timeout: int = 25) -> dict:
    """Palauttaa {url, final_url, status, ctype, path, error}. Sisältö tallennetaan levylle."""
    k = key(url)
    meta_p = CACHE / f"{k}.json"
    body_p = CACHE / f"{k}.bin"
    if meta_p.exists() and (time.time() - meta_p.stat().st_mtime) < max_age_h * 3600:
        m = json.loads(meta_p.read_text())
        # yhteysvirhettä ei pidetä välimuistissa viikkoa: yritetään uudelleen tunnin kuluttua
        if not (m.get("error") and "Connect" in m["error"] and (time.time() - meta_p.stat().st_mtime) > 3600):
            m["path"] = str(body_p) if body_p.exists() else None
            return m
    m = {"url": url, "final_url": url, "status": None, "ctype": "", "error": None}
    if not _robots_ok(url):
        m["error"] = "robots"
        meta_p.write_text(json.dumps(m))
        return m
    host = urlparse(url).netloc
    wait = DELAY - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    for attempt in range(2):  # hidas kuntapalvelin: yksi uusintayritys pidemmällä aikarajalla
        try:
            r = _session.get(url, timeout=timeout if attempt == 0 else timeout * 2,
                             headers={"User-Agent": BROWSER_UA + " " + UA, "Accept-Language": "fi,sv;q=0.8,en;q=0.5"},
                             stream=True, allow_redirects=True)
            data = r.raw.read(MAX_BYTES, decode_content=True)
            m.update(final_url=r.url, status=r.status_code, ctype=r.headers.get("content-type", ""), error=None)
            body_p.write_bytes(data)
            break
        except Exception as e:  # noqa: BLE001
            m["error"] = type(e).__name__ + ": " + str(e)[:200]
            if "Connect" not in m["error"] and "Timeout" not in m["error"]:
                break
            time.sleep(4)
    _last[host] = time.time()
    meta_p.write_text(json.dumps(m))
    m["path"] = str(body_p) if body_p.exists() else None
    return m


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()
