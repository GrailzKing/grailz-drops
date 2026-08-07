"""
drops_data.py — Grailz Drops Calendar Pipeline
================================================
Scrapes all configured sources, merges with manually curated drops,
builds index.html, and writes it to disk.

Run locally:  python drops_data.py
Run on CI:    same command — GitHub Action calls this automatically.

Sources scraped:
  WEB  topps.com/release-calendar
  WEB  beckett.com TCG, non-sports, sports card calendars
  WEB  funko.com/limited-edition-calendar.html
  WEB  disneypinsblog.com
  WEB  tcgradar.eu (Pokemon TCG)
  WEB  icv2.com (Pokemon TCG products)
  WEB  creations.mattel.com/pages/launch-calendar
  WEB  supremecommunity.com
  WEB  hypebeast.com/tags/weekly-drops
  TW   @ONEPIECE_tcg_EN, @wizards_magic, @PokemonRestocks,
       @DisneyPinnacle, @OPTCGAlert, @OriginalFunko, @Topps
       (searched via Google — no API key required)
"""

import datetime, re, json, os, textwrap
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser

# ── CONFIG ────────────────────────────────────────────────────────────────
MONTH       = datetime.date.today().strftime("%B %Y")   # e.g. "August 2026"
MONTH_NUM   = datetime.date.today().month               # 8
YEAR        = datetime.date.today().year                # 2026
OUTPUT_FILE = "index.html"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")

# ── CATEGORY COLORS (matches Excel) ───────────────────────────────────────
CAT_COLORS = {
    "MATTEL CREATIONS":   ("#6b2d8b", "#fff"),
    "TOPPS":              ("#1a4a6b", "#fff"),
    "POKEMON TCG":        ("#b8860b", "#1a1a2e"),
    "MTG":                ("#0e4e2a", "#fff"),
    "FUNKO POP":          ("#4e2a0e", "#fff"),
    "ONE PIECE TCG":      ("#8b1a4a", "#fff"),
    "PANINI":             ("#0e2a4e", "#fff"),
    "VINYL & MUSIC":      ("#2a0e4e", "#fff"),
    "SUPREME FW26":       ("#8b0000", "#fff"),
    "COLLAB / LIFESTYLE": ("#2a4e0e", "#fff"),
    "DISNEY PARKS PINS":  ("#00457c", "#fff"),
    "MOVIES":             ("#8b1a1a", "#fff"),
    "DISNEY LORCANA":     ("#1a3a6b", "#fff"),
    "YU-GI-OH!":          ("#6b1a1a", "#fff"),
    "NON-SPORTS CARDS":   ("#3a3a1a", "#fff"),
}

def cat_slug(cat):
    return re.sub(r"[^a-z0-9]+", "-", cat.lower()).strip("-")

# ── FETCH HELPER ──────────────────────────────────────────────────────────
def fetch(url, timeout=10):
    try:
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] fetch failed for {url}: {e}")
        return ""

# ── SCRAPERS ──────────────────────────────────────────────────────────────

def scrape_topps():
    """Pull drop names + dates from topps.com/release-calendar."""
    print("Scraping topps.com/release-calendar …")
    html = fetch("https://www.topps.com/release-calendar")
    drops = []
    # Topps renders JS — grab what we can from the raw HTML text
    # Pattern: "Month, Day YYYY" near a product title
    month_abbr = {
        "Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
        "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12
    }
    for m in re.finditer(
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+(\d{1,2})[\s,]+(\d{4})',
        html, re.I
    ):
        mon_str, day, yr = m.group(1)[:3].capitalize(), int(m.group(2)), int(m.group(3))
        if mon_str not in month_abbr or yr != YEAR or month_abbr[mon_str] != MONTH_NUM:
            continue
        # Grab text nearby for title (rough heuristic)
        start = max(0, m.start() - 200)
        chunk = html[start:m.start()]
        title_m = re.search(r'>(2\d{3}[^<]{5,80})<', chunk)
        if title_m:
            name = title_m.group(1).strip()
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:70]
            drops.append({
                "cat": "TOPPS",
                "date": f"{MONTH_NUM}-{day}",
                "name": slug,
                "url1": "https://www.topps.com/release-calendar",
                "url2": "",
            })
    print(f"  → {len(drops)} Topps drops found")
    return drops


def scrape_beckett_tcg():
    """Grab TCG release names from Beckett."""
    print("Scraping Beckett TCG calendar …")
    url = "https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/"
    html = fetch(url)
    drops = []
    cat_map = {
        "pokemon": "POKEMON TCG",
        "one piece": "ONE PIECE TCG",
        "magic": "MTG",
        "yu-gi-oh": "YU-GI-OH!",
        "lorcana": "DISNEY LORCANA",
    }
    # Look for month headers + product lines
    month_name = datetime.date(YEAR, MONTH_NUM, 1).strftime("%B")
    in_month = False
    for line in html.splitlines():
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if month_name in clean and str(YEAR) in clean:
            in_month = True
        elif re.match(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", clean):
            if in_month:
                break  # past our month
        if not in_month:
            continue
        if len(clean) < 8 or clean.startswith("http"):
            continue
        for keyword, cat in cat_map.items():
            if keyword in clean.lower() and len(clean) < 120:
                slug = re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-")[:70]
                drops.append({
                    "cat": cat,
                    "date": f"{MONTH_NUM}-TBD",
                    "name": slug,
                    "url1": url,
                    "url2": "",
                })
                break
    print(f"  → {len(drops)} Beckett TCG drops found")
    return drops


def scrape_beckett_nonsports():
    """Grab non-sports release names from Beckett."""
    print("Scraping Beckett Non-Sports calendar …")
    url = "https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/"
    html = fetch(url)
    drops = []
    month_name = datetime.date(YEAR, MONTH_NUM, 1).strftime("%B")
    in_month = False
    for line in html.splitlines():
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if month_name in clean and str(YEAR) in clean:
            in_month = True
        elif re.match(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", clean):
            if in_month:
                break
        if not in_month or len(clean) < 8 or clean.startswith("http"):
            continue
        if any(kw in clean.lower() for kw in ["topps","upper deck","panini","leaf","rittenhouse"]) and len(clean) < 120:
            slug = re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-")[:70]
            drops.append({
                "cat": "NON-SPORTS CARDS",
                "date": f"{MONTH_NUM}-TBD",
                "name": slug,
                "url1": url,
                "url2": "",
            })
    print(f"  → {len(drops)} Beckett Non-Sports drops found")
    return drops


def search_twitter(account, keywords):
    """Search Google for recent tweets from an account matching keywords."""
    query = f"site:x.com {account} " + " OR ".join(f'"{k}"' for k in keywords)
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=5"
    html = fetch(url)
    results = []
    for m in re.finditer(r'<a href="(https://x\.com/[^"]+)"', html):
        tweet_url = m.group(1)
        # Grab surrounding text
        start = m.start()
        chunk = re.sub(r"<[^>]+>", " ", html[start:start+300]).strip()
        if any(k.lower() in chunk.lower() for k in keywords):
            results.append((tweet_url, chunk[:140]))
    return results[:3]


def scrape_social():
    """Lightweight Google-based social scrape for confirmed dates."""
    print("Searching social accounts …")
    month_name = datetime.date(YEAR, MONTH_NUM, 1).strftime("%B")
    drops = []

    tasks = [
        ("@ONEPIECE_tcg_EN", "ONE PIECE TCG",
         ["release", month_name, str(YEAR), "booster"]),
        ("@wizards_magic", "MTG",
         ["release", month_name, str(YEAR), "prerelease"]),
        ("@PokemonRestocks", "POKEMON TCG",
         ["releasing", month_name, str(YEAR), "tin"]),
        ("@DisneyPinsBlog", "DISNEY PARKS PINS",
         ["pin", "limited edition", month_name, str(YEAR)]),
        ("@DisneyPinnacle", "DISNEY PARKS PINS",
         ["D23", "release", month_name, str(YEAR)]),
        ("@OPTCGAlert", "ONE PIECE TCG",
         ["release", month_name, str(YEAR), "promo"]),
        ("@OriginalFunko", "FUNKO POP",
         ["releasing", month_name, str(YEAR), "exclusive"]),
        ("@Topps", "TOPPS",
         ["releasing", month_name, str(YEAR)]),
    ]

    for account, cat, keywords in tasks:
        results = search_twitter(account, keywords)
        for tweet_url, text in results:
            # Try to extract a day number
            day_m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text)
            day = day_m.group(1) if day_m else "TBD"
            slug = re.sub(r"[^a-z0-9]+", "-",
                          text.lower()[:60]).strip("-")
            drops.append({
                "cat": cat,
                "date": f"{MONTH_NUM}-{day}",
                "name": slug,
                "url1": tweet_url,
                "url2": "",
                "_social": True,
            })

    print(f"  → {len(drops)} social drops found")
    return drops


# ── MANUAL / CURATED DROPS ────────────────────────────────────────────────
# These are the high-confidence drops curated in previous sessions.
# Update this list each month — scrapers will ADD to it, not replace it.

MANUAL_DROPS = [
    # FUNKO POP
    ("FUNKO POP","8-3","funko-marvel-collector-corps-shang-chi-box-xl","https://www.amazon.com/dp/B091JH6YTY","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-3","funko-pop-archangel-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-3","funko-pop-psylocke-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-3","funko-pop-sabretooth-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-3","funko-pop-bishop-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-3","funko-pop-mega-man-x-capcom","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-TBD","funko-pop-mystery-warner-bros-horror-icons-blind-box-retail","https://funko.com/new-featured/coming-soon/","https://sdccblog.com/2026/07/funko-san-diego-comic-con-2026-exclusives/"),
    ("FUNKO POP","8-TBD","funko-pop-chainsaw-man-movie-reze-arc-exclusive","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-TBD","funko-pop-monsters-inc-25th-anniversary-set","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-TBD","funko-pop-over-the-garden-wall-series","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html"),
    ("FUNKO POP","8-TBD","funko-pop-august-hot-topic-exclusive","https://funko.com/limited-edition-calendar.html",""),
    ("FUNKO POP","8-TBD","funko-pop-august-entertainment-earth-exclusive","https://funko.com/limited-edition-calendar.html",""),
    ("FUNKO POP","8-TBD","funko-pop-august-fan-rewards-exclusive","https://funko.com/limited-edition-calendar.html",""),
    # POKEMON TCG
    ("POKEMON TCG","8-7","first-partner-collection-series-3-hoenn-kalos-paldea","https://icv2.com/articles/news/view/61079/pokemon-tcg-2026-product-calendar","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-dragonite-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-darkrai-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-zeraora-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149"),
    ("POKEMON TCG","8-TBD","pokemon-tcg-storm-emerald-mega-rayquaza-ex-english-preview","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://www.cardrake.com/guides/upcoming-sets"),
    # ONE PIECE TCG
    ("ONE PIECE TCG","8-3","one-piece-round1-arcade-exclusive-promo-pack-phase-3-entry","https://x.com/OPTCGAlert/status/2083597291852607623",""),
    ("ONE PIECE TCG","8-28","one-piece-tcg-op-17-the-worlds-strongest-warriors-global-simultaneous","https://en.onepiece-cardgame.com/products/","https://x.com/ONEPIECE_tcg_EN/status/2075989349028508136"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-eb-05-heroines-edition-vol-2","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647",""),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-premium-card-collection-best-selection-vol-7","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647",""),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-premium-booster-vol-2","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/",""),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-limited-card-sleeve-premium-matte-vol-6","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647",""),
    # MTG
    ("MTG","8-7","mtg-the-hobbit-prerelease","https://magic.wizards.com/en/products/the-hobbit","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/"),
    ("MTG","8-14","mtg-the-hobbit-global-release","https://magic.wizards.com/en/products/the-hobbit","https://x.com/wizards_magic/status/2082179288032219416"),
    ("MTG","8-14","mtg-the-hobbit-gamegenic-18-pocket-zip-up-album-5-designs","https://x.com/Gamegenic_/status/2084308251391226217",""),
    ("MTG","8-14","mtg-the-hobbit-gamegenic-premium-art-sleeves","https://x.com/Gamegenic_/status/2083221156203573464",""),
    # YU-GI-OH!
    ("YU-GI-OH!","8-7","yu-gi-oh-blissful-eternity","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/",""),
    # DISNEY LORCANA
    ("DISNEY LORCANA","8-TBD","disney-lorcana-attack-of-the-vine","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/",""),
    # TOPPS
    ("TOPPS","8-10","2026-topps-universe-wwe","https://www.topps.com/pages/topps-universe-wwe","https://www.topps.com/release-calendar"),
    ("TOPPS","8-10","2026-bowman-chrome-baseball","https://www.topps.com/pages/bowman-chrome-baseball","https://www.topps.com/release-calendar"),
    ("TOPPS","8-10","2026-topps-wacky-packages-all-new-series","https://www.topps.com/pages/2026-topps-wacky-packages-all-new-series","https://www.topps.com/release-calendar"),
    ("TOPPS","8-11","2026-topps-vault-marvel","https://www.topps.com/pages/topps-vault-marvel","https://www.topps.com/release-calendar"),
    ("TOPPS","8-11","topps-flagship-premier-league-2026-27","https://www.topps.com/pages/topps-flagship-premier-league","https://www.topps.com/release-calendar"),
    ("TOPPS","8-11","2026-topps-chrome-mls","https://www.topps.com/pages/topps-mls-chrome","https://www.topps.com/release-calendar"),
    ("TOPPS","8-12","2026-topps-pristine-baseball","https://www.topps.com/pages/topps-pristine-baseball","https://www.topps.com/release-calendar"),
    ("TOPPS","8-12","2026-star-wars-chrome-galaxy","https://www.topps.com/pages/star-wars-chrome-galaxy","https://www.topps.com/release-calendar"),
    ("TOPPS","8-14","2026-topps-stadium-club-ufc","https://www.topps.com/pages/topps-stadium-club-ufc","https://www.topps.com/release-calendar"),
    ("TOPPS","8-17","2026-topps-museum-collection-baseball","https://www.topps.com/pages/topps-museum-collection-baseball","https://www.topps.com/release-calendar"),
    ("TOPPS","8-18","2025-26-topps-definitive-basketball","https://www.topps.com/pages/topps-definitive-basketball","https://www.topps.com/release-calendar"),
    ("TOPPS","8-19","2026-topps-chrome-baseball-logofractor-edition","https://www.topps.com/pages/topps-chrome-baseball-logofractor-edition","https://www.topps.com/release-calendar"),
    ("TOPPS","8-19","2026-topps-mint-marvel","https://www.topps.com/pages/topps-mint-marvel","https://www.topps.com/release-calendar"),
    ("TOPPS","8-20","2025-26-topps-motif-basketball","https://www.topps.com/pages/topps-motif-basketball","https://www.topps.com/release-calendar"),
    ("TOPPS","8-27","2026-topps-chrome-black-basketball","https://www.topps.com/pages/topps-chrome-black-basketball","https://www.topps.com/release-calendar"),
    ("TOPPS","8-TBD","2026-topps-flagship-football","https://www.beckett.com/news/sports-card-release-calendar-dates/",""),
    ("TOPPS","8-TBD","2026-skybox-metal-universe-space-jam-30th","https://www.beckett.com/news/sports-card-release-calendar-dates/",""),
    # PANINI
    ("PANINI","8-5","2026-panini-contenders-pfl","https://www.overtimecardsandcollectibles.com/product-release-schedule",""),
    ("PANINI","8-TBD","2026-panini-flawless-fifa-world-cup","https://www.beckett.com/news/sports-card-release-calendar-dates/",""),
    ("PANINI","8-TBD","2025-26-panini-select-road-to-fifa-world-cup-soccer","https://www.beckett.com/news/sports-card-release-calendar-dates/",""),
    ("PANINI","8-TBD","2026-panini-impeccable-wnba","https://www.beckett.com/news/sports-card-release-calendar-dates/",""),
    ("PANINI","8-TBD","2026-donruss-optic-nwsl-soccer","https://www.beckett.com/news/sports-card-release-calendar-dates/",""),
    # NON-SPORTS CARDS
    ("NON-SPORTS CARDS","8-7","2026-leaf-seasons-in-the-sun-baseball","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/",""),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-inspirations-world-of-dc","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/",""),
    ("NON-SPORTS CARDS","8-TBD","2026-rittenhouse-star-trek-voyager","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/",""),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-aew-wrestling","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/",""),
    ("NON-SPORTS CARDS","8-TBD","2026-topps-chrome-sapphire-veefriends","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/",""),
    # MATTEL CREATIONS
    ("MATTEL CREATIONS","8-TBD","mattel-creations-august-member-exclusive","https://creations.mattel.com/pages/launch-calendar",""),
    ("MATTEL CREATIONS","8-TBD","hot-wheels-august-collector-exclusive","https://creations.mattel.com/pages/launch-calendar",""),
    # SUPREME FW26
    ("SUPREME FW26","8-TBD","supreme-fw26-preview-lookbook","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops"),
    ("SUPREME FW26","8-TBD","supreme-fw26-week-1","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops"),
    ("SUPREME FW26","8-TBD","supreme-fw26-week-2","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops"),
    # COLLAB / LIFESTYLE
    ("COLLAB / LIFESTYLE","8-6","jjjjound-x-new-balance-740n-mushroom","https://jjjjound.com","https://hypebeast.com/tags/weekly-footwear-drops"),
    ("COLLAB / LIFESTYLE","8-TBD","bobby-hundreds-x-disney-collab","https://thehundreds.com","https://supremedroplist.com/"),
    ("COLLAB / LIFESTYLE","8-TBD","hellstar-x-adidas","https://www.adidas.com","https://hypebeast.com/tags/weekly-footwear-drops"),
    ("COLLAB / LIFESTYLE","8-TBD","kith-august-monthly-drop","https://kith.com","https://hypebeast.com/tags/weekly-drops"),
    ("COLLAB / LIFESTYLE","8-TBD","perks-and-mini-x-asics-collab","https://www.asics.com","https://hypebeast.com/tags/weekly-footwear-drops"),
    # DISNEY PARKS PINS
    ("DISNEY PARKS PINS","8-4","wdw-august-le-pin-week-1","https://disneypinsblog.com","https://mypincentral.com"),
    ("DISNEY PARKS PINS","8-11","wdw-august-le-pin-week-2","https://disneypinsblog.com","https://mypincentral.com"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-disney-pinnacle-booth","https://d23.com/d23-2026/","https://x.com/DisneyPinnacle/status/2081016173999862201"),
    ("DISNEY PARKS PINS","8-14","d23-2026-disney-princess-all-13-le-pin-1200","https://d23.com/d23-2026/","https://x.com/DPrincess_Facts/status/2081016173999862201"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-exclusive-pin-drops-weekend","https://d23.com/d23-2026/","https://disneypinsblog.com"),
    ("DISNEY PARKS PINS","8-18","wdw-august-le-pin-week-3","https://disneypinsblog.com","https://mypincentral.com"),
    ("DISNEY PARKS PINS","8-25","wdw-august-le-pin-week-4","https://disneypinsblog.com","https://mypincentral.com"),
    ("DISNEY PARKS PINS","8-TBD","wdw-halloween-2026-pin-series-launch","https://disneypinsblog.com/halloween-2026-pin-releases-at-disney-store-disney-parks/",""),
    # VINYL & MUSIC
    ("VINYL & MUSIC","8-TBD","record-store-day-drops-2-2026","https://www.recordstoreday.com",""),
    ("VINYL & MUSIC","8-TBD","august-limited-pressing-releases","https://www.plaidroomrecords.com/collections/pre-orders",""),
]


# ── DEDUPLICATE ───────────────────────────────────────────────────────────
def merge(manual, scraped):
    seen = set()
    out = []
    for d in manual:
        key = d[2][:40] if isinstance(d, tuple) else d["name"][:40]
        if key not in seen:
            seen.add(key)
            out.append(d)
    for d in scraped:
        key = d["name"][:40]
        if key not in seen:
            seen.add(key)
            out.append({
                "cat": d["cat"],
                "date": d["date"],
                "name": d["name"],
                "url1": d["url1"],
                "url2": d.get("url2",""),
            })
    return out


# ── SORT ──────────────────────────────────────────────────────────────────
def sort_key(d):
    if isinstance(d, tuple):
        date_str = d[1]
    else:
        date_str = d["date"]
    parts = str(date_str).split("-")
    try:
        return int(parts[1]) if parts[1] != "TBD" else 9999
    except:
        return 9999


# ── HTML BUILDER ──────────────────────────────────────────────────────────
def build_html(drops):
    cats = sorted(set(
        d[0] if isinstance(d, tuple) else d["cat"]
        for d in drops
    ))

    def get_fields(d):
        if isinstance(d, tuple):
            return d[0], d[1], d[2], d[3], d[4] if len(d) > 4 else ""
        return d["cat"], d["date"], d["name"], d["url1"], d.get("url2","")

    html_rows = ""
    for d in drops:
        cat, date_str, name, url1, url2 = get_fields(d)
        cs = cat_slug(cat)
        parts = str(date_str).split("-")
        try:
            day = parts[1]
            if day != "TBD":
                dt = datetime.date(YEAR, int(parts[0]), int(day))
                date_display = dt.strftime("%-m/%-d/%Y")
                date_sort = dt.strftime("%Y%m%d")
            else:
                date_display = f"{parts[0]}/TBD/{YEAR}"
                date_sort = "99999999"
        except:
            date_display = date_str
            date_sort = "99999999"

        u1 = (f'<a href="{url1}" target="_blank" rel="noopener">Source 1 ↗</a>'
              if url1 and url1.startswith("http") else "")
        u2 = (f'<a href="{url2}" target="_blank" rel="noopener">Source 2 ↗</a>'
              if url2 and url2.startswith("http") else "")

        clean_name = re.sub(r'^\\d+-(?:TBD|\\d+)-', '', name)
    html_rows += f"""
    <tr data-cat="{cs}" data-date="{date_sort}">
      <td class="date-cell">{date_display}</td>
      <td class="name-cell">{clean_name}</td>
      <td><span class="cat-badge cat-{cs}">{cat}</span></td>
      <td class="source-cell">{u1}{" " if u1 and u2 else ""}{u2}</td>
    </tr>"""

    filter_btns = '<button class="filter-btn active" data-filter="all">All</button>\n'
    for cat in cats:
        sl = cat_slug(cat)
        filter_btns += f'    <button class="filter-btn" data-filter="{sl}">{cat}</button>\n'

    badge_css = ""
    btn_css = ""
    for cat, (bg, fg) in CAT_COLORS.items():
        sl = cat_slug(cat)
        badge_css += f".cat-{sl} {{ background: {bg}; color: {fg}; }}\n"
        btn_css   += (f'.filter-btn[data-filter="{sl}"].active'
                      f' {{ background: {bg}; color: {fg}; border-color: {bg}; }}\n')

    today = datetime.date.today().strftime("%-m/%-d/%Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Grailz — {MONTH} Drops Calendar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0d0d10;--surface:#16161c;--border:#2a2a35;
    --accent:#e8c840;--text:#e8e8f0;--muted:#6b6b80;--row-alt:#111118;
  }}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Space Grotesk',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
  header{{border-bottom:1px solid var(--border);padding:28px 40px 24px;display:flex;align-items:flex-end;gap:24px;flex-wrap:wrap;}}
  .logo{{font-family:'Space Mono',monospace;font-size:26px;font-weight:700;color:var(--accent);letter-spacing:-0.5px;line-height:1;}}
  .logo span{{color:var(--muted);font-weight:400;}}
  .subtitle{{font-size:13px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;padding-bottom:2px;}}
  .pill{{margin-left:auto;font-family:'Space Mono',monospace;font-size:11px;background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:5px 12px;border-radius:20px;}}
  .controls{{padding:20px 40px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:14px;}}
  .search-wrap{{display:flex;align-items:center;gap:10px;}}
  #search{{background:var(--surface);border:1px solid var(--border);color:var(--text);font-family:'Space Grotesk',sans-serif;font-size:14px;padding:9px 14px;border-radius:6px;width:280px;outline:none;transition:border-color .15s;}}
  #search:focus{{border-color:var(--accent);}}
  #search::placeholder{{color:var(--muted);}}
  .count{{font-size:12px;color:var(--muted);font-family:'Space Mono',monospace;}}
  .filters{{display:flex;flex-wrap:wrap;gap:6px;}}
  .filter-btn{{font-family:'Space Grotesk',sans-serif;font-size:11px;font-weight:600;padding:5px 12px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;letter-spacing:.04em;text-transform:uppercase;}}
  .filter-btn:hover{{border-color:var(--text);color:var(--text);}}
  .filter-btn.active{{background:var(--accent);color:#0d0d10;border-color:var(--accent);}}
  {btn_css}
  .table-wrap{{padding:0 40px 60px;overflow-x:auto;}}
  table{{width:100%;border-collapse:collapse;margin-top:24px;font-size:13px;}}
  thead th{{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 16px;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none;}}
  thead th:hover{{color:var(--text);}}
  thead th.sorted::after{{content:' ↑';color:var(--accent);}}
  thead th.sorted.desc::after{{content:' ↓';}}
  tbody tr{{border-bottom:1px solid #1e1e26;transition:background .1s;}}
  tbody tr:nth-child(even){{background:var(--row-alt);}}
  tbody tr:hover{{background:#1e1e2a;}}
  tbody tr.hidden{{display:none;}}
  td{{padding:11px 16px;vertical-align:middle;}}
  .cat-badge{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:4px;white-space:nowrap;}}
  {badge_css}
  .date-cell{{font-family:'Space Mono',monospace;font-size:12px;color:var(--muted);white-space:nowrap;}}
  .name-cell{{font-size:13px;color:var(--text);max-width:420px;}}
  .source-cell{{white-space:nowrap;display:flex;gap:8px;flex-wrap:wrap;}}
  .source-cell a{{font-family:'Space Mono',monospace;font-size:10px;color:var(--accent);text-decoration:none;border:1px solid #3a3a20;padding:3px 8px;border-radius:4px;transition:background .1s;}}
  .source-cell a:hover{{background:#2a2a10;}}
  .no-results{{text-align:center;padding:60px 0;color:var(--muted);font-family:'Space Mono',monospace;font-size:13px;display:none;}}
  footer{{border-top:1px solid var(--border);padding:20px 40px;font-size:11px;color:var(--muted);font-family:'Space Mono',monospace;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}}
  @media(max-width:680px){{header,.controls,.table-wrap,footer{{padding-left:16px;padding-right:16px;}}#search{{width:100%;}}}}
</style>
</head>
<body>
<header>
  <div>
    <div class="logo">GRAILZ<span>.gg</span></div>
    <div class="subtitle">Collectibles Drop Calendar</div>
  </div>
  <div class="pill">{MONTH}</div>
</header>
<div class="controls">
  <div class="search-wrap">
    <input id="search" type="text" placeholder="Search drops…" autocomplete="off">
    <span class="count" id="count"></span>
  </div>
  <div class="filters">
    {filter_btns}
  </div>
</div>
<div class="table-wrap">
  <table id="dropsTable">
    <thead>
      <tr>
        <th data-col="0" class="sorted">Date</th>
        <th data-col="1">Drop</th>
        <th data-col="2">Category</th>
        <th data-col="3">Sources</th>
      </tr>
    </thead>
    <tbody id="tbody">
      {html_rows}
    </tbody>
  </table>
  <div class="no-results" id="noResults">No drops found — try a different filter or search.</div>
</div>
<footer>
  <span>Updated {today} · Grailz Discord Server</span>
  <span>topps.com · beckett.com · tcgradar.eu · disneypinsblog.com · funko.com + social</span>
</footer>
<script>
  const tbody=document.getElementById('tbody');
  const rows=Array.from(tbody.querySelectorAll('tr'));
  const noRes=document.getElementById('noResults');
  const count=document.getElementById('count');
  let activeFilter='all',sortCol=0,sortDesc=false;
  function updateCount(){{
    const v=rows.filter(r=>!r.classList.contains('hidden')).length;
    count.textContent=v+' drop'+(v!==1?'s':'');
  }}
  function applyFilters(){{
    const q=document.getElementById('search').value.toLowerCase();
    let any=false;
    rows.forEach(r=>{{
      const cm=activeFilter==='all'||r.dataset.cat===activeFilter;
      const tm=!q||r.textContent.toLowerCase().includes(q);
      r.classList.toggle('hidden',!(cm&&tm));
      if(cm&&tm)any=true;
    }});
    noRes.style.display=any?'none':'block';
    updateCount();
  }}
  document.querySelectorAll('.filter-btn').forEach(b=>{{
    b.addEventListener('click',()=>{{
      document.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      activeFilter=b.dataset.filter;
      applyFilters();
    }});
  }});
  document.getElementById('search').addEventListener('input',applyFilters);
  document.querySelectorAll('thead th[data-col]').forEach(th=>{{
    th.addEventListener('click',()=>{{
      const col=+th.dataset.col;
      if(sortCol===col)sortDesc=!sortDesc;
      else{{sortCol=col;sortDesc=false;}}
      document.querySelectorAll('thead th').forEach(t=>t.classList.remove('sorted','desc'));
      th.classList.add('sorted');
      if(sortDesc)th.classList.add('desc');
      rows.slice().sort((a,b)=>{{
        if(col===0){{
          const ad=a.dataset.date||'99999999',bd=b.dataset.date||'99999999';
          return sortDesc?bd.localeCompare(ad):ad.localeCompare(bd);
        }}
        const av=a.cells[col]?.textContent.trim()||'';
        const bv=b.cells[col]?.textContent.trim()||'';
        return sortDesc?bv.localeCompare(av):av.localeCompare(bv);
      }}).forEach(r=>tbody.appendChild(r));
      applyFilters();
    }});
  }});
  applyFilters();
</script>
</body>
</html>"""


# ── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n=== Grailz Drops Builder — {MONTH} ===\n")

    # 1. Scrape sources
    scraped = []
    scraped += scrape_topps()
    scraped += scrape_beckett_tcg()
    scraped += scrape_beckett_nonsports()
    scraped += scrape_social()

    # 2. Merge with curated manual list
    all_drops = merge(MANUAL_DROPS, scraped)
    all_drops.sort(key=sort_key)
    print(f"\nTotal drops: {len(all_drops)} ({len(MANUAL_DROPS)} manual + {len(scraped)} scraped)")

    # 3. Build HTML
    html = build_html(all_drops)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written → {OUTPUT_FILE}")
    print("\nDone. Push index.html to GitHub to deploy.\n")
