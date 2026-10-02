"""Download and update the upstream data repositories.

Both repositories are cloned as shallow, blob-less, sparse checkouts so we only
pull the Pauper files we actually need.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

DECKLIST_REPO = "https://github.com/fbettega/MTG_decklistcache.git"
FORMAT_REPO = "https://github.com/Badaro/MTGOFormatData.git"

DECKLIST_DIR = DATA_DIR / "MTG_decklistcache"
FORMAT_DIR = DATA_DIR / "MTGOFormatData"

# MTGO file names always contain the format, so we can filter by name. The other
# sites use free-text event names ("Lega Genova Lunedi"), so we take everything
# and filter on the "Formats" field when loading.
DECKLIST_PATTERNS = [
    "/Tournaments/MTGO/**/*pauper*",
    "/Tournaments/MTGmelee/",
    "/Tournaments/Topdeck/",
    "/Tournaments/CardsRealm/",
    "/Tournaments/Manatrader/",
]
FORMAT_PATTERNS = ["/Formats/card_colors.json", "/Formats/Pauper/"]


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def _sync(url: str, target: Path, patterns: list[str]) -> None:
    if (target / ".git").exists():
        _git("sparse-checkout", "set", "--no-cone", *patterns, cwd=target)
        _git("pull", "--ff-only", "--depth", "1", cwd=target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    _git("clone", "--depth", "1", "--filter=blob:none", "--sparse", url, str(target))
    _git("sparse-checkout", "set", "--no-cone", *patterns, cwd=target)


def fetch_all() -> None:
    _sync(DECKLIST_REPO, DECKLIST_DIR, DECKLIST_PATTERNS)
    _sync(FORMAT_REPO, FORMAT_DIR, FORMAT_PATTERNS)
