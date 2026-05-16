#!/usr/bin/env python3
"""Rolex Grey Market Price Tracker — Singapore (Carousell)

Scrapes Carousell SG for current grey market Rolex prices.
Outputs data.json for the index.html dashboard.

Run:  python fetch_prices.py
"""

import gzip
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

OUT_PATH = Path(__file__).parent / "data.json"
HISTORY_LIMIT = 90  # days of history to keep

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-SG,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# Carousell search queries — one per major family
SEARCH_QUERIES = [
    ("Submariner",      "rolex submariner"),
    ("GMT-Master II",   "rolex gmt master"),
    ("Daytona",         "rolex daytona"),
    ("Datejust",        "rolex datejust"),
    ("Sea-Dweller",     "rolex sea dweller"),
    ("Yacht-Master",    "rolex yacht master"),
    ("Sky-Dweller",     "rolex sky dweller"),
    ("Day-Date",        "rolex day date"),
    ("Explorer",        "rolex explorer"),
    ("Oyster Perpetual","rolex oyster perpetual"),
    ("Air-King",        "rolex air king"),
    ("Milgauss",        "rolex milgauss"),
]

# Pattern that captures url, title, price, condition from each listing block
LISTING_RE = re.compile(
    r'<a\s+[^>]*href="(/p/[^"]+)"[^>]*>.*?'   # listing URL
    r'--max-line:2">([^<]+)</p>'                # title
    r'.*?title="(S\$[0-9,]+)"'                 # price
    r'.*?color:#57585a">([^<]+)</p>',           # condition
    re.DOTALL,
)


# Keywords that must appear in a title for it to belong to each family.
# First matching family wins when re-classifying a mislabelled listing.
FAMILY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Submariner",       ["submariner"]),
    ("GMT-Master II",    ["gmt-master", "gmt master", "gmtmaster", " gmt "]),
    ("Daytona",          ["daytona"]),
    ("Datejust",         ["datejust", "date just"]),
    ("Sea-Dweller",      ["sea-dweller", "sea dweller", "seadweller", "deepsea"]),
    ("Yacht-Master",     ["yacht-master", "yacht master", "yachtmaster"]),
    ("Sky-Dweller",      ["sky-dweller", "sky dweller", "skydweller"]),
    ("Day-Date",         ["day-date", "day date", "daydate", "president"]),
    ("Explorer",         ["explorer"]),
    ("Oyster Perpetual", ["oyster perpetual"]),
    ("Air-King",         ["air-king", "air king", "airking"]),
    ("Milgauss",         ["milgauss"]),
]
_FAMILY_SET = {fam for fam, _ in FAMILY_KEYWORDS}


def detect_family(title: str) -> str | None:
    """Return the best-matching family for a title, or None if unrecognised."""
    t = title.lower()
    for fam, kws in FAMILY_KEYWORDS:
        if any(kw in t for kw in kws):
            return fam
    return None


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
        if resp.info().get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="ignore")


def parse_price(s: str) -> int:
    """'S$17,300' → 17300"""
    return int(s.replace("S$", "").replace(",", ""))


def extract_ref(title: str) -> str | None:
    """Extract Rolex reference number (6-digit starting 1/2/3, optional suffix)."""
    m = re.search(r"\b([123]\d{5}[A-Z0-9]{0,4})\b", title)
    return m.group(1) if m else None


# Ref number prefixes → material  (checked before keyword scan)
_REF_MATERIAL: dict[str, str] = {
    # Daytona
    "116508": "Yellow Gold", "116518": "Yellow Gold",
    "116528": "Yellow Gold", "126508": "Yellow Gold", "116505": "Rose/Everose Gold",
    "126505": "Rose/Everose Gold", "116519": "White Gold", "126519": "White Gold",
    "116503": "Two-Tone", "126503": "Two-Tone",
    # Submariner
    "116618": "Yellow Gold", "126618": "Yellow Gold",
    "116619": "White Gold", "126619": "White Gold",
    "116613": "Two-Tone",  "126613": "Two-Tone",
    # GMT-Master II
    "116718": "Yellow Gold", "116719": "White Gold", "126719": "White Gold",
    "116713": "Two-Tone",
    "126711": "Two-Tone",   # Rootbeer (Oystersteel + Everose)
    "126713": "Two-Tone",   # Guinness (Oystersteel + Yellow Gold)
    "126715": "Rose/Everose Gold",
    "126718": "Yellow Gold",
    # Datejust
    "116238": "Yellow Gold", "126238": "Yellow Gold",
    "116300": "White Gold",
    "116234": "Two-Tone",  "126234": "Two-Tone",
    "128235": "Rose/Everose Gold", "126284": "Two-Tone",
    # Yacht-Master
    "116655": "Rose/Everose Gold", "126655": "Rose/Everose Gold",
    "116688": "Yellow Gold", "116689": "White Gold",
    "126622": "Two-Tone", "126621": "Two-Tone",
    "126506": "Platinum",
    # Sea-Dweller
    "126603": "Two-Tone", "116603": "Two-Tone",
    # Sky-Dweller
    "326934": "Rose/Everose Gold", "326935": "White Gold",
    "326933": "Yellow Gold",  "326938": "Yellow Gold",
    "326939": "White Gold",
    "336935": "White Gold", "336934": "Rose/Everose Gold",
    # Day-Date
    "118238": "Yellow Gold", "118239": "White Gold", "118235": "Rose/Everose Gold",
    "128238": "Yellow Gold", "128239": "White Gold", "128235": "Rose/Everose Gold",
    "228238": "Yellow Gold", "228239": "White Gold", "228235": "Rose/Everose Gold",
    "228206": "Platinum",    "228236": "Platinum",
}

# Keyword patterns → material  (priority order: Diamond > Platinum > specific golds > Two-Tone > Steel)
_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("Diamond",         ["diamond"]),
    ("Platinum",        ["platinum"]),
    ("Yellow Gold",     ["yellow gold", "yg ", " yg ", "yellow-gold"]),
    ("Rose/Everose Gold", ["rose gold", "everose gold", "everose"]),
    ("White Gold",      ["white gold", "wg ", " wg "]),
    ("Two-Tone",        ["two tone", "two-tone", "rolesor", "half gold",
                          "half yellow gold", "half rose gold", "half white gold",
                          "gold steel", "steel gold"]),
    ("Stainless Steel", ["stainless steel", "steel", "oystersteel", "904l"]),
]


# Year regex — matches 4-digit years 1990–2029
_YEAR_RE = re.compile(r'\b(19[9][0-9]|20[0-2][0-9])\b')


def extract_year(title: str) -> str | None:
    """Extract production year from listing title, e.g. '2019 Rolex ...' → '2019'."""
    m = _YEAR_RE.search(title)
    return m.group(1) if m else None


def classify_material(title: str, ref: str | None) -> str:
    """Classify listing material from ref number or title keywords."""
    # 1. Ref-based (most reliable) — match on first 6 digits
    if ref:
        base6 = ref[:6]
        if base6 in _REF_MATERIAL:
            return _REF_MATERIAL[base6]

    # 2. Keyword scan (case-insensitive)
    t = title.lower()
    for material, keywords in _KEYWORD_RULES:
        if any(kw in t for kw in keywords):
            return material

    # 3. Default
    return "Stainless Steel"


def scrape_family(family: str, query: str) -> list[dict]:
    encoded = urllib.request.quote(query)
    url = f"https://www.carousell.sg/search/{encoded}/?sort_by=3"
    print(f"  Fetching {family} …", end=" ", flush=True)
    try:
        html = fetch_html(url)
    except Exception as e:
        print(f"ERROR: {e}")
        return []

    matches = LISTING_RE.findall(html)
    seen = set()
    listings = []
    for url_path, title, price_str, condition in matches:
        title = title.strip()
        price = parse_price(price_str)

        # Sanity check
        if price < 5_000 or price > 700_000:
            continue

        # Deduplicate by (title, price) — HTML renders each card twice
        key = (title.lower(), price)
        if key in seen:
            continue
        seen.add(key)

        ref = extract_ref(title)

        # Validate/reclassify: if the title clearly belongs to a different
        # known family, skip it (cross-contamination from broad search results).
        detected = detect_family(title)
        if detected is not None and detected != family:
            continue

        listings.append({
            "title": title,
            "price": price,
            "condition": condition.strip(),
            "ref": ref,
            "material": classify_material(title, ref),
            "year": extract_year(title),
            "url": f"https://www.carousell.sg{url_path}",
            "family": family,
        })

    print(f"{len(listings)} listings")
    return listings


def compute_stats(prices: list[int]) -> dict:
    return {
        "count": len(prices),
        "min": min(prices),
        "max": max(prices),
        "avg": round(mean(prices)),
        "median": round(median(prices)),
    }


def group_by_ref(listings: list[dict]) -> dict:
    """Group listings by ref number within a family."""
    by_ref: dict[str, list] = {}
    for item in listings:
        ref = item["ref"] or "Unknown"
        by_ref.setdefault(ref, []).append(item)
    result = {}
    for ref, items in sorted(by_ref.items()):
        prices = [i["price"] for i in items]
        result[ref] = {
            "listings": sorted(items, key=lambda x: x["price"]),
            "stats": compute_stats(prices),
        }
    return result


def group_by_year(listings: list[dict]) -> dict:
    """Group listings by production year; returns years sorted descending."""
    by_yr: dict[str, list] = {}
    for item in listings:
        yr = item["year"] or "Unknown"
        by_yr.setdefault(yr, []).append(item)
    result = {}
    for yr in sorted(by_yr.keys(), reverse=True):
        items = by_yr[yr]
        prices = [i["price"] for i in items]
        result[yr] = {
            "stats": compute_stats(prices),
        }
    return result


# Material display order for tables
MATERIAL_ORDER = [
    "Stainless Steel", "Two-Tone", "Rose/Everose Gold",
    "White Gold", "Yellow Gold", "Platinum", "Diamond",
]


def group_by_material(listings: list[dict]) -> dict:
    """Group listings by material within a family."""
    by_mat: dict[str, list] = {}
    for item in listings:
        by_mat.setdefault(item["material"], []).append(item)
    result = {}
    for mat in MATERIAL_ORDER:
        if mat not in by_mat:
            continue
        items = by_mat[mat]
        prices = [i["price"] for i in items]
        result[mat] = {
            "listings": sorted(items, key=lambda x: x["price"]),
            "stats": compute_stats(prices),
        }
    # Any unlisted material
    for mat, items in by_mat.items():
        if mat not in result:
            prices = [i["price"] for i in items]
            result[mat] = {
                "listings": sorted(items, key=lambda x: x["price"]),
                "stats": compute_stats(prices),
            }
    return result


def main() -> None:
    print("=" * 60)
    print("Rolex Grey Market Tracker — Carousell SG")
    print("=" * 60)

    all_families: dict[str, dict] = {}

    for family, query in SEARCH_QUERIES:
        listings = scrape_family(family, query)
        if not listings:
            continue
        prices = [i["price"] for i in listings]
        all_families[family] = {
            "listings": sorted(listings, key=lambda x: x["price"]),
            "stats": compute_stats(prices),
            "by_ref": group_by_ref(listings),
            "by_material": group_by_material(listings),
            "by_year": group_by_year(listings),
        }
        time.sleep(1.5)  # be polite

    total = sum(d["stats"]["count"] for d in all_families.values())
    print(f"\nTotal listings: {total}")

    now = datetime.now(timezone.utc)
    today = datetime.now(timezone(datetime.now().astimezone().utcoffset())).strftime("%Y-%m-%d")

    # Load existing data to preserve history
    existing: dict = {}
    if OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text())
        except Exception:
            pass

    history: list[dict] = existing.get("history", [])

    # Today's snapshot (family → stats only, for trend charting)
    today_snap = {
        "date": today,
        "families": {
            fam: data["stats"] for fam, data in all_families.items()
        },
    }
    history = [h for h in history if h["date"] != today]
    history.append(today_snap)
    history = sorted(history, key=lambda x: x["date"])[-HISTORY_LIMIT:]

    out = {
        "updated": now.isoformat(),
        "snapshot_date": today,
        "total_listings": total,
        "source": "Carousell SG",
        "families": all_families,
        "history": history,
    }

    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n✓ Saved → {OUT_PATH}")

    # Summary table
    print("\n── Summary ─────────────────────────────────────────────────")
    print(f"  {'Model':<22} {'#':>3}  {'Min':>8}  {'Avg':>8}  {'Max':>8}")
    print(f"  {'-'*22}  {'-'*3}  {'-'*8}  {'-'*8}  {'-'*8}")
    for fam, data in sorted(all_families.items(), key=lambda x: -x[1]["stats"]["count"]):
        s = data["stats"]
        print(f"  {fam:<22} {s['count']:>3}  S${s['min']:>6,}  S${s['avg']:>6,}  S${s['max']:>6,}")


if __name__ == "__main__":
    main()
