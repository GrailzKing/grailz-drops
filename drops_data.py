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

# ── LOGO (base64 embedded — no external hosting needed) ───────────────────
LOGO_64  = "data:image/png;base64,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"
LOGO_FAV = "data:image/png;base64,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"


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

        clean_name = re.sub(r'^\d+-(?:TBD|\d+)-', '', name)
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

    LOGO_64_VAL  = LOGO_64
    LOGO_FAV_VAL = LOGO_FAV
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" href="{LOGO_FAV_VAL}">
<title>Grailz — {MONTH} Drops Calendar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#06060d;--surface:#0e0e1a;--border:#1e1230;
    --accent:#1eb8f0;--accent2:#9b3fe8;--accent3:#00e5ff;
    --text:#e8e8f8;--muted:#6b6b90;--row-alt:#0a0a14;
  }}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Space Grotesk',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
  header{{
    border-bottom:1px solid var(--border);
    padding:24px 40px;
    background:linear-gradient(135deg,#06060d 60%,#0e0a1a 100%);
  }}
  .header-inner{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;}}
  .logo-wrap{{display:flex;align-items:center;gap:16px;}}
  .logo-img{{width:64px;height:64px;border-radius:50%;filter:drop-shadow(0 0 10px #9b3fe8) drop-shadow(0 0 20px #1eb8f060);flex-shrink:0;}}
  .logo{{
    font-family:'Space Mono',monospace;
    font-size:30px;font-weight:700;
    background:linear-gradient(90deg,#ffffff 0%,#c084fc 40%,#1eb8f0 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;
    letter-spacing:2px;line-height:1;
    text-shadow:none;
    filter:drop-shadow(0 0 12px #9b3fe880);
  }}
  .subtitle{{font-size:11px;color:var(--muted);letter-spacing:.12em;text-transform:uppercase;margin-top:4px;}}
  .pill{{
    font-family:'Space Mono',monospace;font-size:11px;
    background:linear-gradient(135deg,#9b3fe820,#1eb8f020);
    border:1px solid #9b3fe860;color:#c084fc;
    padding:6px 16px;border-radius:20px;white-space:nowrap;
  }}
  .controls{{padding:20px 40px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:14px;}}
  .search-wrap{{display:flex;align-items:center;gap:10px;}}
  #search{{background:var(--surface);border:1px solid var(--border);color:var(--text);font-family:'Space Grotesk',sans-serif;font-size:14px;padding:9px 14px;border-radius:6px;width:280px;outline:none;transition:border-color .15s;}}
  #search:focus{{border-color:var(--accent2);box-shadow:0 0 0 2px #9b3fe820;}}
  #search::placeholder{{color:var(--muted);}}
  .count{{font-size:12px;color:var(--muted);font-family:'Space Mono',monospace;}}
  .filters{{display:flex;flex-wrap:wrap;gap:6px;}}
  .filter-btn{{font-family:'Space Grotesk',sans-serif;font-size:11px;font-weight:600;padding:5px 12px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;letter-spacing:.04em;text-transform:uppercase;}}
  .filter-btn:hover{{border-color:var(--text);color:var(--text);}}
  .filter-btn.active{{background:var(--accent2);color:#fff;border-color:var(--accent2);}}
  {btn_css}
  .table-wrap{{padding:0 40px 60px;overflow-x:auto;}}
  table{{width:100%;border-collapse:collapse;margin-top:24px;font-size:13px;}}
  thead th{{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 16px;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none;}}
  thead th:hover{{color:var(--text);}}
  thead th.sorted::after{{content:' ↑';color:var(--accent3);}}
  thead th.sorted.desc::after{{content:' ↓';}}
  tbody tr{{border-bottom:1px solid #1e1e26;transition:background .1s;}}
  tbody tr:nth-child(even){{background:var(--row-alt);}}
  tbody tr:hover{{background:#100d1e;box-shadow:inset 3px 0 0 var(--accent2);}}
  tbody tr.hidden{{display:none;}}
  td{{padding:11px 16px;vertical-align:middle;}}
  .cat-badge{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:4px;white-space:nowrap;}}
  {badge_css}
  .date-cell{{font-family:'Space Mono',monospace;font-size:12px;color:var(--muted);white-space:nowrap;}}
  .name-cell{{font-size:13px;color:var(--text);max-width:420px;}}
  .source-cell{{white-space:nowrap;display:flex;gap:8px;flex-wrap:wrap;}}
  .source-cell a{{font-family:'Space Mono',monospace;font-size:10px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:3px 8px;border-radius:4px;transition:all .15s;}}
  .source-cell a:hover{{background:#0d1a20;box-shadow:0 0 6px #1eb8f040;}}
  .no-results{{text-align:center;padding:60px 0;color:var(--muted);font-family:'Space Mono',monospace;font-size:13px;display:none;}}
  footer{{border-top:1px solid var(--border);padding:20px 40px;font-size:11px;color:var(--muted);font-family:'Space Mono',monospace;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;background:linear-gradient(135deg,#06060d,#0a0814);}}
  @media(max-width:680px){{header,.controls,.table-wrap,footer{{padding-left:16px;padding-right:16px;}}#search{{width:100%;}}}}
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <div class="logo-wrap">
      <img src="{LOGO_64_VAL}" alt="Grailz" class="logo-img">
      <div>
        <div class="logo">GRAILZ</div>
        <div class="subtitle">Collectibles Drop Calendar</div>
      </div>
    </div>
    <div class="pill">{MONTH}</div>
  </div>
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
