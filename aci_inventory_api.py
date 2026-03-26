from __future__ import annotations

import csv
import io
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware


BASE = "https://aciautosale.com"
LIST_URL = f"{BASE}/newandusedcars?clearall=1"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SESSION = requests.Session()
# Avoid picking up system HTTP(S)_PROXY / corporate proxy env vars.
SESSION.trust_env = False
SESSION.headers.update(BROWSER_HEADERS)


def _abs_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"{BASE}{href}"
    return f"{BASE}/{href}"


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _extract_vdp_kv(soup: BeautifulSoup) -> Dict[str, str]:
    kv: Dict[str, str] = {}
    for p in soup.select('p[class^="opt"], p[class*=" opt"]'):
        lab = p.find("label")
        if not lab:
            continue
        k = _clean_text(lab.get_text(" ", strip=True)).rstrip(":")
        lab.extract()
        v = _clean_text(p.get_text(" ", strip=True))
        if k and v:
            kv[k] = v
    return kv


def _extract_options(soup: BeautifulSoup) -> List[str]:
    h = soup.find(["h2", "h3", "h4"], string=re.compile(r"Vehicle Options", re.I))
    if not h:
        return []

    container = h.parent
    for _ in range(10):
        lis = container.select("li")
        if len(lis) >= 5:
            return [_clean_text(li.get_text(" ", strip=True)) for li in lis if _clean_text(li.get_text(" ", strip=True))]
        if container.parent:
            container = container.parent
        else:
            break
    return []


def _extract_price(soup: BeautifulSoup) -> Optional[str]:
    el = soup.select_one("[data-sales-price]")
    return el.get("data-sales-price") if el else None


def _extract_main_image(soup: BeautifulSoup) -> Optional[str]:
    for imgtag in soup.select("img[src]"):
        src = imgtag.get("src") or ""
        if "imagescdn.dealercarsearch.com/Media/" in src:
            return src
    return None


def _parse_vdp(url: str) -> Dict[str, Any]:
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    price = _extract_price(soup)
    kv = _extract_vdp_kv(soup)
    options = _extract_options(soup)
    image = _extract_main_image(soup)

    return {
        "url": url,
        "title": title,
        "price": price,
        "Year": kv.get("Year"),
        "Make": kv.get("Make"),
        "Model": kv.get("Model"),
        "Trim": kv.get("Trim"),
        "Type": kv.get("Type"),
        "Mileage": kv.get("Mileage"),
        "Vin": kv.get("Vin"),
        "Stock #": kv.get("Stock #"),
        "Trans": kv.get("Trans"),
        "Drive Train": kv.get("Drive Train"),
        "Engine": kv.get("Engine"),
        "Color": kv.get("Color"),
        "Interior": kv.get("Interior"),
        "Interior Color": kv.get("Interior Color"),
        "State": kv.get("State"),
        "image": image,
        "options": options,
    }


def _get_vdp_links(limit: int) -> List[str]:
    r = SESSION.get(LIST_URL, timeout=45)
    if r.status_code != 200:
        return []
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    seen = set()
    for a in soup.select('a[href^="/bhphvdp/"]'):
        href = a.get("href") or ""
        href = href.split("?", 1)[0]
        if not href or href in seen:
            continue
        seen.add(href)
        links.append(_abs_url(href))
        if len(links) >= limit:
            break
    if not links:
        for m in re.finditer(r'href="(/bhphvdp/\d+/[^"?#]+)"', html):
            href = m.group(1).split("?", 1)[0]
            if href in seen:
                continue
            seen.add(href)
            links.append(_abs_url(href))
            if len(links) >= limit:
                break
    return links


_CACHE: Dict[str, Any] = {"ts": 0.0, "limit": 0, "data": []}
_CACHE_TTL_S = 300.0


def get_inventory(limit: int) -> List[Dict[str, Any]]:
    now = time.time()
    if (
        _CACHE["data"]
        and _CACHE["limit"] == limit
        and (now - float(_CACHE["ts"])) < _CACHE_TTL_S
    ):
        return _CACHE["data"]

    urls = _get_vdp_links(limit=limit)
    out: List[Dict[str, Any]] = []
    for u in urls:
        try:
            out.append(_parse_vdp(u))
        except Exception:
            out.append({"url": u, "title": "", "price": None})

    _CACHE.update({"ts": now, "limit": limit, "data": out})
    return out


app = FastAPI(title="ACI Auto Sales Inventory API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/inventory")
def inventory(limit: int = Query(20, ge=1, le=200)) -> List[Dict[str, Any]]:
    return get_inventory(limit=limit)


@app.get("/inventory.csv")
def inventory_csv(limit: int = Query(20, ge=1, le=200)) -> Response:
    rows = get_inventory(limit=limit)
    cols = [
        "url",
        "title",
        "price",
        "Year",
        "Make",
        "Model",
        "Trim",
        "Type",
        "Mileage",
        "Vin",
        "Stock #",
        "Trans",
        "Drive Train",
        "Engine",
        "Color",
        "Interior",
        "Interior Color",
        "State",
        "image",
        "options",
    ]

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        flat = dict(r)
        if isinstance(flat.get("options"), list):
            flat["options"] = " | ".join([x for x in flat["options"] if x])
        w.writerow({k: (flat.get(k) or "") for k in cols})

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="aci_inventory.csv"'},
    )

