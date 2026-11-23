"""Lähdesovittimet: muuttavat haetun dokumentin tekstiksi (sivuittain) ja linkeiksi.

Muodot: html (kuntasivu, Wilma, Peda.net), pdf (päätös, liite, koulun pdf),
pdf_scan (OCR), docx, image (OCR), ruudukko (merkitään -> visiolukija).
Järjestelmät: Dynasty (päätökset + liitteet), Wilma (julkiset tiedotteet), Lovdata (NO).
"""
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

PROPOSAL_RE = re.compile(r"\b(ehdotus|luonnos|förslag|forslag|utkast|udkast)\b|xx\.xx", re.I)
WEEKDAY_ROW_RE = re.compile(r"\b(ma|ti|ke|to|pe)\s+(ma|ti|ke|to|pe)\s+(ma|ti|ke|to|pe)\b", re.I)
GRID_CODE_RE = re.compile(r"\b(HF|JF|VF|PF|EF|SF)\b")
CONTENT_RE = re.compile(r"syysloma|joululoma|talviloma|hiihtoloma|höstlov|jullov|sportlov|lukukausi|läsåret|skolerute|høstferie", re.I)
DOC_EXT_RE = re.compile(r"\.(pdf|docx?|odt|rtf|png|jpe?g)(\?|$)", re.I)

# ---------- tunnistus ----------

def sniff_format(meta: dict) -> str:
    ct = (meta.get("ctype") or "").lower()
    url = (meta.get("final_url") or meta.get("url") or "").lower()
    head = b""
    if meta.get("path") and Path(meta["path"]).exists():
        head = Path(meta["path"]).read_bytes()[:8]
    if head.startswith(b"%PDF") or "pdf" in ct:
        return "pdf"
    if head.startswith(b"PK") and ("word" in ct or url.endswith(".docx") or "officedocument" in ct):
        return "docx"
    if ct.startswith("image/") or re.search(r"\.(png|jpe?g)$", url):
        return "image"
    return "html"


# ---------- lukijat ----------

def _ocr(png_paths, lang="fin+swe"):
    out = []
    for p in png_paths:
        try:
            r = subprocess.run(["tesseract", p, "-", "-l", lang, "--psm", "6"],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0 and "fin" in lang:
                r = subprocess.run(["tesseract", p, "-", "-l", "eng", "--psm", "6"],
                                   capture_output=True, text=True, timeout=120)
            out.append(r.stdout)
        except Exception:
            out.append("")
    return out


def read_pdf(path: str, max_pages: int = 40) -> dict:
    r = subprocess.run(["pdftotext", "-layout", "-l", str(max_pages), path, "-"],
                       capture_output=True, text=True, timeout=120)
    pages = r.stdout.split("\f")
    text = "\n".join(pages)
    fmt = "pdf"
    if len(re.sub(r"\s", "", text)) < 150:  # skannattu
        fmt = "pdf_scan"
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["pdftoppm", "-r", "200", "-png", "-l", "6", path, f"{td}/p"],
                           capture_output=True, timeout=180)
            pages = _ocr(sorted(str(p) for p in Path(td).glob("p*.png")))
        text = "\n".join(pages)
    return {"format": fmt, "pages": pages, "text": text}


def read_docx(path: str) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf8", "replace")
    except Exception:
        return {"format": "docx", "pages": [""], "text": ""}
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return {"format": "docx", "pages": [text], "text": text}


def read_image(path: str) -> dict:
    pages = _ocr([path])
    return {"format": "image", "pages": pages, "text": pages[0]}


def read_html(path: str, base_url: str) -> dict:
    raw = Path(path).read_bytes()
    soup = BeautifulSoup(raw, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].strip())
        if href.startswith("http"):
            links.append((href.split("#")[0], " ".join(a.get_text(" ").split())[:200]))
    for t in soup(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    # navigaatio ja alatunniste pois vain, jos niissä ei ole itse sisältöä (osa CMS:istä käärii kaiken <form>/<header>iin)
    for t in soup(["nav", "footer", "header", "form", "aside"]):
        if not CONTENT_RE.search(t.get_text(" ")):
            t.decompose()
    for tr in soup.find_all("tr"):  # taulukot riveiksi
        cells = [" ".join(c.get_text(" ").split()) for c in tr.find_all(["td", "th"])]
        tr.replace_with(soup.new_string("\n" + " | ".join(cells) + "\n"))
    for br in soup.find_all(["br", "p", "li", "h1", "h2", "h3", "h4", "div"]):
        br.insert_after(soup.new_string("\n"))
    title = (soup.title.get_text(" ").strip() if soup.title else "")
    text = re.sub(r"[ \t\xa0]+", " ", soup.get_text())
    text = re.sub(r"\n\s*\n+", "\n", text)
    imgs = [urljoin(base_url, i.get("src", "")) for i in soup.find_all("img") if i.get("src")]
    return {"format": "html", "pages": [text], "text": text, "title": title, "links": links, "images": imgs}


def read(meta: dict) -> dict:
    """Yhteinen sisääntulo: haettu dokumentti -> {format, pages, text, links, flags}."""
    if not meta.get("path") or meta.get("status") not in (200, 203):
        return {"format": None, "pages": [], "text": "", "links": [], "error": meta.get("error") or meta.get("status")}
    fmt = sniff_format(meta)
    url = meta.get("final_url") or meta["url"]
    if fmt == "pdf":
        doc = read_pdf(meta["path"])
    elif fmt == "docx":
        doc = read_docx(meta["path"])
    elif fmt == "image":
        doc = read_image(meta["path"])
    else:
        doc = read_html(meta["path"], url)
    doc.setdefault("links", [])
    t = doc["text"]
    doc["flags"] = {
        # ehdotus vain otsikossa / dokumentin alussa tai xx.xx-päivinä (ei "anna ehdotus" -palautelinkit)
        "proposal": bool(PROPOSAL_RE.search((doc.get("title") or "") + " " + t.strip()[:300])) or bool(re.search(r"xx\.xx", t)),
        # kalenteriruudukko: viikonpäivärivejä tai HF/VF-koodeja -> visiolukija
        "grid": len(WEEKDAY_ROW_RE.findall(t)) >= 3 or len(GRID_CODE_RE.findall(t)) >= 8
                or len(re.findall(r"(?m)^\s*(MA|TI|KE|TO|PE|LA|SU|Må|Ti|On|To|Fr)\b(\s+\d{1,2}){2,}", t)) >= 5
                or len(re.findall(r"\d+\s+työpäivää", t)) >= 6,
        "attachment_only": bool(re.search(r"liitteen\s+mukai|enligt\s+bilaga|jf\.?\s*vedlegg", t, re.I))
                           and not re.search(r"syysloma\s*:?\s*\d|höstlov\s*:?\s*\d", t, re.I),
    }
    doc["url"] = url
    return doc


# ---------- järjestelmät ----------

DYNASTY_RE = re.compile(r"(oncloudos\.com|/kokous/|paatokset|poytakirjat|dynasty|D10_)", re.I)


def classify_source(url: str) -> str:
    u = url.lower()
    if "lovdata.no" in u:
        return "lovdata"
    if "inschool.fi" in u:
        return "wilma"
    if DYNASTY_RE.search(u) or "tweb" in u or "cloudnc" in u or "/ktwebbin/" in u:
        return "paatos"
    if "peda.net" in u:
        return "koulu"
    if DOC_EXT_RE.search(u):
        return "liite"
    return "kuntasivu"


def dynasty_siblings(url: str) -> list:
    """Dynasty-asiakirjasta (…/kokous/2026924-4.PDF) myös HTM-versio, josta liitelinkit löytyvät."""
    m = re.search(r"(.*/kokous/\d+-\d+)\.(PDF|HTM)$", url, re.I)
    if not m:
        return []
    return [m.group(1) + ".HTM", m.group(1) + ".PDF"]


def attachment_links(doc: dict) -> list:
    """Liitteet ja dokumentit, joihin sivu viittaa ja jotka koskevat loma-aikoja."""
    kw = re.compile(r"loma|työaj|tyoaj|lukuvuo|läsår|lasar|skollov|kalenter|liite|bilaga|vedlegg|skolerute|ferie", re.I)
    out = []
    for href, txt in doc.get("links", []):
        if (DOC_EXT_RE.search(href) or re.search(r"/kokous/\d+-\d+-\d+\.", href, re.I)) and (kw.search(href) or kw.search(txt)):
            out.append(href)
    return list(dict.fromkeys(out))


def same_site(a: str, b: str) -> bool:
    ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return strip(ha) == strip(hb) or strip(ha).endswith("." + strip(hb)) or strip(hb).endswith("." + strip(ha))
