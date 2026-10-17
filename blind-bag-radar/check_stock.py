"""Blind Bag Radar stock checker.

Checks each shop in shops.json for the Santa Cruz x Pokemon TCG blind bag deck
and writes status.json for the page's Refresh button.

How each shop is checked:
  1. If shops.json has a known product URL, read Shopify's <product>.js (availability + price).
  2. Otherwise ask the shop's Shopify search (/search/suggest.json) for "pokemon tcg blind bag".
  3. Non-Shopify shops (or blocked requests) are marked "unchecked" and keep their manual status.

status.json is only rewritten when a result changes, or once an hour as a heartbeat,
so the scheduled workflow doesn't commit every 15 minutes for nothing.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOPS = HERE / "shops.json"
STATUS = HERE / "status.json"
HEARTBEAT_MIN = 60
TIMEOUT = 12
UA = "Mozilla/5.0 (compatible; GrailzBlindBagRadar/1.0; +https://grailzking.github.io/grailz-drops/blind-bag-radar/)"
QUERY = "pokemon tcg blind bag"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 200:
            raise ValueError(f"HTTP {r.status}")
        return json.loads(r.read().decode("utf-8", "replace"))


def is_2026_bag(title, handle=""):
    """Match the 2026 TCG bag, not the 2023 character bags."""
    t = f"{title} {handle}".lower().replace("é", "e")
    return "pokemon" in t and "blind" in t and ("tcg" in t or "2026" in t or "11117698" in t)


def price_str(cents):
    try:
        return f"${int(cents) / 100:,.2f}"
    except (TypeError, ValueError):
        return ""


def check_product(url):
    data = get_json(url.split("?")[0].rstrip("/") + ".js")
    variants = data.get("variants") or []
    available = bool(data.get("available")) or any(v.get("available") for v in variants)
    return {
        "state": "in_stock" if available else "sold_out",
        "price": price_str(data.get("price")),
        "url": url,
        "title": data.get("title", ""),
    }


def check_search(site):
    base = site.rstrip("/")
    parts = urllib.parse.urlsplit(base)
    base = f"{parts.scheme}://{parts.netloc}"
    q = urllib.parse.urlencode({"q": QUERY, "resources[type]": "product", "resources[limit]": 10})
    data = get_json(f"{base}/search/suggest.json?{q}")
    products = (((data.get("resources") or {}).get("results") or {}).get("products")) or []
    hits = [p for p in products if is_2026_bag(p.get("title", ""), p.get("handle", ""))]
    if not hits:
        return {"state": "not_listed", "price": "", "url": "", "title": ""}
    p = hits[0]
    url = p.get("url", "")
    if url.startswith("/"):
        url = base + url.split("?")[0]
    try:
        # suggest.json's "available" can lag; confirm on the product itself
        return check_product(url)
    except Exception:
        avail = p.get("available")
        return {
            "state": "in_stock" if avail else "sold_out",
            "price": "$" + str(p.get("price", "")).lstrip("$") if p.get("price") else "",
            "url": url,
            "title": p.get("title", ""),
        }


def check(shop):
    try:
        if shop.get("product"):
            try:
                res = check_product(shop["product"])
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    res = {"state": "not_listed", "price": "", "url": "", "title": ""}
                else:
                    raise
        else:
            res = check_search(shop["site"])
    except Exception as e:  # non-Shopify, blocked, timeout
        res = {"state": "unchecked", "price": "", "url": "", "title": "", "error": type(e).__name__}
    res["name"] = shop["name"]
    return res


def main():
    shops = json.loads(SHOPS.read_text())
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(check, shops))

    now = datetime.now(timezone.utc)
    new = {"checked_at": now.isoformat(timespec="seconds"), "shops": {r.pop("name"): r for r in results}}

    old = {}
    if STATUS.exists():
        try:
            old = json.loads(STATUS.read_text())
        except json.JSONDecodeError:
            old = {}

    def comparable(d):
        return {k: {kk: vv for kk, vv in v.items() if kk != "error"} for k, v in (d.get("shops") or {}).items()}

    changed = comparable(new) != comparable(old)
    stale = True
    if old.get("checked_at"):
        age = (now - datetime.fromisoformat(old["checked_at"])).total_seconds() / 60
        stale = age >= HEARTBEAT_MIN

    counts = {}
    for r in new["shops"].values():
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    print("Results:", counts)
    for name, r in new["shops"].items():
        if r["state"] == "in_stock":
            print(f"  IN STOCK: {name} {r['price']} {r['url']}")

    if changed or stale:
        STATUS.write_text(json.dumps(new, indent=1, ensure_ascii=False) + "\n")
        print("status.json written", "(changed)" if changed else "(heartbeat)")
    else:
        print("No change; status.json left as is")


if __name__ == "__main__":
    sys.exit(main())
