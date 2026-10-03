"""Card images from Scryfall (https://scryfall.com/docs/api).

Image links are looked up with the /cards/collection endpoint (75 cards per
request) and cached in data/raw/scryfall/cards.json. Images themselves are
downloaded only when a build needs local copies, e.g. for image sheets.

Scryfall asks API clients to send a User-Agent and Accept header and to keep
to about 10 requests per second; we stay well under that.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .sources import DATA_DIR

CACHE_DIR = DATA_DIR / "scryfall"
CARDS_FILE = CACHE_DIR / "cards.json"
IMAGE_DIR = CACHE_DIR / "img"
HEADERS = {"User-Agent": "PauperResearch/0.1 (github.com/fmssn/Pauper-Research)", "Accept": "application/json"}
DELAY = 0.12  # seconds between requests


def _request(url: str, payload: dict | None = None) -> bytes:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = dict(HEADERS, **({"Content-Type": "application/json"} if data else {}))
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _image_entry(card: dict) -> dict | None:
    """Front face image of a card, also for double-faced cards."""
    uris = card.get("image_uris") or ((card.get("card_faces") or [{}])[0].get("image_uris"))
    if not uris:
        return None
    return {"id": card["id"], "normal": uris["normal"], "uri": card.get("scryfall_uri")}


def _load_cache() -> dict:
    return json.loads(CARDS_FILE.read_text(encoding="utf-8")) if CARDS_FILE.exists() else {}


def lookup(names: list[str]) -> dict[str, dict]:
    """Image info per card name; cached, so only unknown names hit the API."""
    cache = _load_cache()
    missing = [n for n in dict.fromkeys(names) if n not in cache]
    for i in range(0, len(missing), 75):
        batch = missing[i:i + 75]
        body = json.loads(_request("https://api.scryfall.com/cards/collection",
                                   {"identifiers": [{"name": n} for n in batch]}))
        found = {}
        for card in body.get("data", []):
            entry = _image_entry(card)
            if entry:
                found[card["name"]] = entry
                # Requested names can be one face of a split or double-faced card.
                for face in card.get("card_faces") or []:
                    found.setdefault(face.get("name"), entry)
        for n in batch:
            cache[n] = found.get(n)
        time.sleep(DELAY)

    # Names the collection endpoint didn't match get one fuzzy lookup each.
    for n in [n for n in missing if cache.get(n) is None]:
        try:
            card = json.loads(_request("https://api.scryfall.com/cards/named?fuzzy=" + urllib.parse.quote(n)))
            cache[n] = _image_entry(card)
        except Exception:
            cache[n] = None
        time.sleep(DELAY)

    if missing:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CARDS_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    return {n: cache[n] for n in names if cache.get(n)}


def download(entries: dict[str, dict]) -> dict[str, Path]:
    """Local copy of each card's 'normal' (488x680) image."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, entry in entries.items():
        path = IMAGE_DIR / f"{entry['id']}.jpg"
        if not path.exists():
            path.write_bytes(_request(entry["normal"]))
            time.sleep(DELAY)
        paths[name] = path
    return paths


SHEET_COLS, SHEET_ROWS = 3, 3
CARD_W, CARD_H = 488, 680


def build_sheets(names: list[str], out_dir: Path, quality: int = 74) -> dict:
    """Pack card images into JPEG sheets of SHEET_COLS x SHEET_ROWS cards.

    Published pages can't load images from other sites and can carry only a
    few hundred files, so cards ship as a few dozen sheets. Pass names in the
    order they are likely to be viewed together (e.g. grouped by deck) so a
    deck's cards share sheets. Returns the image index for the page.
    """
    from PIL import Image  # optional dependency, only needed here

    entries = lookup(names)
    paths = download(entries)
    ordered = [n for n in dict.fromkeys(names) if n in paths]
    per_sheet = SHEET_COLS * SHEET_ROWS
    out_dir.mkdir(parents=True, exist_ok=True)
    cards = {}
    sheets = []
    for s in range(0, len(ordered), per_sheet):
        chunk = ordered[s:s + per_sheet]
        rows = -(-len(chunk) // SHEET_COLS)
        sheet = Image.new("RGB", (SHEET_COLS * CARD_W, rows * CARD_H), (16, 16, 16))
        for k, name in enumerate(chunk):
            with Image.open(paths[name]) as img:
                img = img.convert("RGB")
                if img.size != (CARD_W, CARD_H):
                    img = img.resize((CARD_W, CARD_H), Image.LANCZOS)
                sheet.paste(img, ((k % SHEET_COLS) * CARD_W, (k // SHEET_COLS) * CARD_H))
            cards[name] = [len(sheets), k]
        file = f"sheet-{len(sheets):02d}.jpg"
        sheet.save(out_dir / file, "JPEG", quality=quality, optimize=True, progressive=True)
        sheets.append({"file": file, "rows": rows})
    return {"mode": "sheet", "cols": SHEET_COLS, "w": CARD_W, "h": CARD_H, "sheets": sheets, "cards": cards}


def url_index(names: list[str]) -> dict:
    """Image index that links straight to Scryfall, for pages opened outside the artifact host."""
    return {"mode": "url", "cards": {n: e["normal"] for n, e in lookup(names).items()}}
