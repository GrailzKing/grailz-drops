"""
drops_data.py — Grailz Drops Calendar Pipeline
================================================
Writes data/<YYYY-MM>.json from MANUAL_DROPS,
updates data/index.json manifest,
and builds index.html (lightweight shell — no data baked in).

Run locally:  python drops_data.py
GitHub Action calls this every Monday at 9am CT.

Sources scraped (when not 403'd):
  WEB  topps.com/release-calendar
  WEB  beckett.com TCG, non-sports, sports calendars
  WEB  funko.com/limited-edition-calendar.html (LE only)
  WEB  disneypinsblog.com, mypincentral.com, wdwnt.com
  WEB  tcgradar.eu, icv2.com, creations.mattel.com
  WEB  supremecommunity.com, hypebeast.com/tags/weekly-drops
  TW   @ONEPIECE_tcg_EN, @wizards_magic, @PokemonRestocks,
       @DisneyPinnacle, @OPTCGAlert, @OriginalFunko, @Topps
       (searched via Google — no API key required)
  NOTE pauseandplay.com blocks robots — search via Google manually
  NOTE Funko: funko.com/limited-edition-calendar.html ONLY
       Do NOT use pops.today, amazon.com, or any aggregator
"""

import datetime, re, json, os
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── CONFIG ────────────────────────────────────────────────────────────────
MONTH_NUM   = datetime.date.today().month
YEAR        = datetime.date.today().year
MONTH_KEY   = f"{YEAR}-{MONTH_NUM:02d}"
MONTH_NAME  = datetime.date(YEAR, MONTH_NUM, 1).strftime("%B %Y")
OUTPUT_HTML = "index.html"
DATA_DIR    = "data"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")

# ── LOGO (base64 embedded) ────────────────────────────────────────────────
_logo_dir = os.path.dirname(os.path.abspath(__file__))

def _load_b64(name):
    p = os.path.join(_logo_dir, name)
    if os.path.exists(p):
        with open(p) as f:
            return f.read().strip()
    # fallback: try parent
    p2 = os.path.join(os.path.dirname(_logo_dir), name)
    if os.path.exists(p2):
        with open(p2) as f:
            return f.read().strip()
    return ""

LOGO_64  = _load_b64("logo_64.b64")
LOGO_FAV = _load_b64("logo_fav.b64")

# ── CATEGORY COLORS ───────────────────────────────────────────────────────
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
    "US MINT":            ("#1a3a1a", "#7fff7f"),
}

CAT_TIMES = {
    "FUNKO POP":"11:00","TOPPS":"12:00","PANINI":"12:00",
    "POKEMON TCG":"09:00","ONE PIECE TCG":"00:00","MTG":"00:00",
    "YU-GI-OH!":"00:00","DISNEY LORCANA":"09:00","NON-SPORTS CARDS":"12:00",
    "DISNEY PARKS PINS":"09:00","SUPREME FW26":"11:00","MATTEL CREATIONS":"09:00",
    "COLLAB / LIFESTYLE":"10:00","VINYL & MUSIC":"00:00","MOVIES":"00:00",
    "US MINT":"12:00",
}

def cslug(c): return re.sub(r"[^a-z0-9]+"," ",c.lower()).strip().replace(" ","-")

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
    print("Scraping topps.com/release-calendar …")
    html = fetch("https://www.topps.com/release-calendar")
    drops = []
    month_abbr = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                  "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    for m in re.finditer(
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+(\d{1,2})[\s,]+(\d{4})',
        html, re.I):
        mon, day, yr = m.group(1)[:3].capitalize(), int(m.group(2)), int(m.group(3))
        if mon not in month_abbr or yr != YEAR or month_abbr[mon] != MONTH_NUM:
            continue
        start = max(0, m.start()-200)
        chunk = html[start:m.start()]
        title_m = re.search(r'>(2\d{3}[^<]{5,80})<', chunk)
        if title_m:
            name = re.sub(r"[^a-z0-9]+"," ", title_m.group(1).lower()).strip()[:70].replace(" ","-")
            drops.append({"cat":"TOPPS","date":f"{MONTH_NUM}-{day}","name":name,
                          "url1":"https://www.topps.com/release-calendar","url2":"","time":"12:00"})
    print(f"  → {len(drops)} Topps drops found")
    return drops

def scrape_beckett_tcg():
    print("Scraping Beckett TCG calendar …")
    url = "https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/"
    html = fetch(url)
    drops = []
    cat_map = {"pokemon":"POKEMON TCG","one piece":"ONE PIECE TCG","magic":"MTG",
               "yu-gi-oh":"YU-GI-OH!","lorcana":"DISNEY LORCANA"}
    month_name = datetime.date(YEAR,MONTH_NUM,1).strftime("%B")
    in_month = False
    for line in html.splitlines():
        clean = re.sub(r"<[^>]+>","",line).strip()
        if month_name in clean and str(YEAR) in clean: in_month = True
        elif re.match(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", clean):
            if in_month: break
        if not in_month or len(clean)<8 or clean.startswith("http"): continue
        for kw, cat in cat_map.items():
            if kw in clean.lower() and len(clean)<120:
                slug = re.sub(r"[^a-z0-9]+"," ",clean.lower()).strip()[:70].replace(" ","-")
                drops.append({"cat":cat,"date":f"{MONTH_NUM}-TBD","name":slug,
                              "url1":url,"url2":"","time":CAT_TIMES.get(cat,"09:00")})
                break
    print(f"  → {len(drops)} Beckett TCG drops found")
    return drops

def scrape_beckett_nonsports():
    print("Scraping Beckett Non-Sports calendar …")
    url = "https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/"
    html = fetch(url)
    drops = []
    month_name = datetime.date(YEAR,MONTH_NUM,1).strftime("%B")
    in_month = False
    for line in html.splitlines():
        clean = re.sub(r"<[^>]+>","",line).strip()
        if month_name in clean and str(YEAR) in clean: in_month = True
        elif re.match(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", clean):
            if in_month: break
        if not in_month or len(clean)<8 or clean.startswith("http"): continue
        if any(kw in clean.lower() for kw in ["topps","upper deck","panini","leaf","rittenhouse"]) and len(clean)<120:
            slug = re.sub(r"[^a-z0-9]+"," ",clean.lower()).strip()[:70].replace(" ","-")
            drops.append({"cat":"NON-SPORTS CARDS","date":f"{MONTH_NUM}-TBD","name":slug,
                          "url1":url,"url2":"","time":"12:00"})
    print(f"  → {len(drops)} Beckett Non-Sports drops found")
    return drops

def search_twitter(account, keywords):
    query = f"site:x.com {account} " + " OR ".join(f'"{k}"' for k in keywords)
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=5"
    html = fetch(url)
    results = []
    for m in re.finditer(r'<a href="(https://x\.com/[^"]+)"', html):
        tweet_url = m.group(1)
        start = m.start()
        chunk = re.sub(r"<[^>]+"," ",html[start:start+300]).strip()
        if any(k.lower() in chunk.lower() for k in keywords):
            results.append((tweet_url, chunk[:140]))
    return results[:3]

def scrape_social():
    print("Searching social accounts …")
    month_name = datetime.date(YEAR,MONTH_NUM,1).strftime("%B")
    drops = []
    tasks = [
        ("@ONEPIECE_tcg_EN","ONE PIECE TCG",["release",month_name,str(YEAR),"booster"]),
        ("@wizards_magic","MTG",["release",month_name,str(YEAR),"prerelease"]),
        ("@PokemonRestocks","POKEMON TCG",["releasing",month_name,str(YEAR),"tin"]),
        ("@DisneyPinsBlog","DISNEY PARKS PINS",["pin","limited edition",month_name,str(YEAR)]),
        ("@DisneyPinnacle","DISNEY PARKS PINS",["D23","release",month_name,str(YEAR)]),
        ("@OPTCGAlert","ONE PIECE TCG",["release",month_name,str(YEAR),"promo"]),
        ("@OriginalFunko","FUNKO POP",["releasing",month_name,str(YEAR),"exclusive"]),
        ("@Topps","TOPPS",["releasing",month_name,str(YEAR)]),
    ]
    for account, cat, keywords in tasks:
        for tweet_url, text in search_twitter(account, keywords):
            day_m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text)
            day = day_m.group(1) if day_m else "TBD"
            slug = re.sub(r"[^a-z0-9]+"," ",text.lower()[:60]).strip().replace(" ","-")
            drops.append({"cat":cat,"date":f"{MONTH_NUM}-{day}","name":slug,
                          "url1":tweet_url,"url2":"","time":CAT_TIMES.get(cat,"09:00"),
                          "_social":True})
    print(f"  → {len(drops)} social drops found")
    return drops

# ── MANUAL / CURATED DROPS ────────────────────────────────────────────────
# Format: (cat, date, name, url1, url2, time_et)
# Funko: funko.com/limited-edition-calendar.html ONLY — no pops.today/amazon

MANUAL_DROPS = [
    # ── FUNKO POP — funko.com/limited-edition-calendar.html only ─────────
    # Funko.com Exclusives
    ("FUNKO POP","8-4","funko-pop-comic-covers-batman-black-and-white-funko-exclusive","https://funko.com/limited-edition-calendar.html","", "12:00"),
    ("FUNKO POP","8-11","funko-pop-tmnt-michelangelo-eating-pizza-with-pop-protector-funko-exclusive","https://funko.com/limited-edition-calendar.html","", "12:00"),
    # Retailer Exclusives
    ("FUNKO POP","8-5","funko-pop-one-piece-toy-temple-collectibles-le-exclusive-9500-pcs","https://funko.com/limited-edition-calendar.html","", "12:00"),
    ("FUNKO POP","8-5","funko-pop-sonic-the-hedgehog-gamestop-le-exclusive-9500-pcs","https://funko.com/limited-edition-calendar.html","", "12:00"),
    ("FUNKO POP","8-12","funko-pop-harry-potter-target-le-exclusive-7500-pcs","https://funko.com/limited-edition-calendar.html","", "12:00"),
    ("FUNKO POP","8-19","funko-pop-alice-in-wonderland-box-lunch-le-exclusive-9500-pcs","https://funko.com/limited-edition-calendar.html","", "12:00"),
    ("FUNKO POP","8-26","funko-pop-wwe-walmart-le-exclusive-7500-pcs","https://funko.com/limited-edition-calendar.html","", "12:00"),
    # ── POKEMON TCG ───────────────────────────────────────────────────────
    ("POKEMON TCG","8-7","first-partner-collection-series-3-hoenn-kalos-paldea","https://icv2.com/articles/news/view/61079/pokemon-tcg-2026-product-calendar","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026", "09:00"),
    ("POKEMON TCG","8-13","pokemon-center-legendary-moments-cosmoem-monthly-pin","https://www.pokemon.com/us/news/go-legendary-with-pokemon-centers-2026-monthly-pins","https://www.pokemoncenter.com", "09:00"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-dragonite-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149", "09:00"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-darkrai-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149", "09:00"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-zeraora-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149", "09:00"),
    ("POKEMON TCG","8-TBD","pokemon-tcg-storm-emerald-mega-rayquaza-ex-english-preview","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://www.cardrake.com/guides/upcoming-sets", "09:00"),
    # ── ONE PIECE TCG ─────────────────────────────────────────────────────
    ("ONE PIECE TCG","8-3","one-piece-round1-arcade-exclusive-promo-pack-phase-3-entry","https://x.com/OPTCGAlert/status/2083597291852607623","", "00:00"),
    ("ONE PIECE TCG","8-28","one-piece-tcg-op-17-the-worlds-strongest-warriors-global-simultaneous","https://en.onepiece-cardgame.com/products/","https://x.com/ONEPIECE_tcg_EN/status/2075989349028508136", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-eb-05-heroines-edition-vol-2","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647","", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-premium-card-collection-best-selection-vol-7","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647","", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-premium-booster-vol-2","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/","", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-limited-card-sleeve-premium-matte-vol-6","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647","", "00:00"),
    # ── MTG ───────────────────────────────────────────────────────────────
    ("MTG","8-7","mtg-the-hobbit-prerelease","https://magic.wizards.com/en/products/the-hobbit","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/", "00:00"),
    ("MTG","8-14","mtg-the-hobbit-global-release","https://magic.wizards.com/en/products/the-hobbit","https://x.com/wizards_magic/status/2082179288032219416", "00:00"),
    ("MTG","8-14","mtg-the-hobbit-gamegenic-18-pocket-zip-up-album-5-designs","https://x.com/Gamegenic_/status/2084308251391226217","", "00:00"),
    ("MTG","8-14","mtg-the-hobbit-gamegenic-premium-art-sleeves","https://x.com/Gamegenic_/status/2083221156203573464","", "00:00"),

    # ── MTG SECRET LAIR ───────────────────────────────────────────────────
    # Source: secretlair.wizards.com / magic.wizards.com/en/news
    # 24-hr window orders — all times ET
    ("MTG","8-10","mtg-secret-lair-commander-deck-hatsune-miku","https://magic.wizards.com/en/news/announcements/secret-lair-commander-deck-hatsune-miku-decklist","https://secretlair.wizards.com/us/", "12:00"),
    ("MTG","8-17","mtg-secret-lair-x-the-hobbit-marvelous-mathoms-superdrop","https://magic.wizards.com/en/news/announcements/secret-lair-a-marvelous-mathom-superdrop","https://secretlair.wizards.com/us/", "12:00"),
    # ── YU-GI-OH! ─────────────────────────────────────────────────────────
    ("YU-GI-OH!","8-7","yu-gi-oh-blissful-eternity","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/","", "00:00"),
    # ── DISNEY LORCANA ────────────────────────────────────────────────────
    ("DISNEY LORCANA","8-TBD","disney-lorcana-attack-of-the-vine","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/","", "09:00"),
    # ── TOPPS ─────────────────────────────────────────────────────────────
    ("TOPPS","8-10","2026-topps-universe-wwe","https://www.topps.com/pages/topps-universe-wwe","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-10","2026-bowman-chrome-baseball","https://www.topps.com/pages/bowman-chrome-baseball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-10","2026-topps-wacky-packages-all-new-series","https://www.topps.com/pages/2026-topps-wacky-packages-all-new-series","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-11","2026-topps-vault-marvel","https://www.topps.com/pages/topps-vault-marvel","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-11","topps-flagship-premier-league-2026-27","https://www.topps.com/pages/topps-flagship-premier-league","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-11","2026-topps-chrome-mls","https://www.topps.com/pages/topps-mls-chrome","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-12","2026-topps-pristine-baseball","https://www.topps.com/pages/topps-pristine-baseball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-12","2026-star-wars-chrome-galaxy","https://www.topps.com/pages/star-wars-chrome-galaxy","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-14","2026-topps-stadium-club-ufc","https://www.topps.com/pages/topps-stadium-club-ufc","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-14","2025-26-topps-chrome-update-basketball","https://www.topps.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("TOPPS","8-24","2026-topps-museum-collection-baseball","https://www.topps.com/pages/topps-museum-collection-baseball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-18","2025-26-topps-definitive-basketball","https://www.topps.com/pages/topps-definitive-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-19","2026-topps-chrome-baseball-logofractor-edition","https://www.topps.com/pages/topps-chrome-baseball-logofractor-edition","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-19","2026-topps-mint-marvel","https://www.topps.com/pages/topps-mint-marvel","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-20","2025-26-topps-motif-basketball","https://www.topps.com/pages/topps-motif-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-27","2026-topps-chrome-black-basketball","https://www.topps.com/pages/topps-chrome-black-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-21","2026-topps-flagship-football","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),

    ("TOPPS","8-18","2026-topps-royalty-premier-league","https://www.topps.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("TOPPS","8-25","2025-26-topps-pristine-basketball","https://www.topps.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("TOPPS","8-25","2026-topps-chrome-star-wars","https://www.topps.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("TOPPS","8-26","2026-topps-chrome-baseball-sapphire-edition","https://www.topps.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("TOPPS","8-26","2026-topps-chrome-team-japan-samurai-collection","https://www.topps.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),    ("TOPPS","8-TBD","2026-skybox-metal-universe-space-jam-30th","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    # ── PANINI ────────────────────────────────────────────────────────────
    ("PANINI","8-5","2026-panini-contenders-pfl","https://www.overtimecardsandcollectibles.com/product-release-schedule","", "12:00"),
    ("PANINI","8-12","2026-panini-prizm-baseball","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-12","2026-panini-revolution-k-league-soccer","https://www.checklistinsider.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-12","2026-panini-turn-four-nascar-racing","https://www.checklistinsider.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-19","2026-panini-donruss-wnba-basketball","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-19","2025-26-panini-origins-basketball","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-TBD","2026-panini-flawless-fifa-world-cup","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("PANINI","8-TBD","2025-26-panini-select-road-to-fifa-world-cup-soccer","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("PANINI","8-TBD","2026-panini-impeccable-wnba","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("PANINI","8-TBD","2026-donruss-optic-nwsl-soccer","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),

    # ── US MINT ────────────────────────────────────────────────────────────
    # Source: usmint.gov/product-schedule/2026 — August releases only
    # All drop at 12:00 PM ET on release date
    ("US MINT","8-3","comic-art-three-medal-set-2025-super-heroes","https://www.usmint.gov/comic-art-three-medal-set-2025-super-heroes-M25DC3.html","https://www.usmint.gov/product-schedule/2026/?start=0&sz=64", "12:00"),
    ("US MINT","8-6","best-of-the-mint-1916-walking-liberty-half-dollar-gold-coin-silver-medal-set","https://www.usmint.gov/best-of-the-mint-1916-walking-liberty-half-dollar-gold-coin-and-silver-medal-set-26BM3.html","https://www.usmint.gov/product-schedule/2026/?start=0&sz=64", "12:00"),
    ("US MINT","8-25","morgan-silver-dollar-2026-enhanced-uncirculated-coin","https://www.usmint.gov/morgan-silver-dollar-2026-enhanced-uncirculated-coin-26XE.html","https://www.usmint.gov/product-schedule/2026/?start=0&sz=64", "12:00"),
    ("US MINT","8-25","peace-silver-dollar-2026-enhanced-uncirculated-coin","https://www.usmint.gov/peace-silver-dollar-2026-enhanced-uncirculated-coin-26XH.html","https://www.usmint.gov/product-schedule/2026/?start=0&sz=64", "12:00"),
    ("US MINT","8-26","semiquincentennial-quarters-2026-rolls-and-bags-us-constitution","https://www.usmint.gov/semiquincentennial-quarters-2026-rolls-and-bags-us-constitution-MASTER_SEMIQC.html","https://www.usmint.gov/product-schedule/2026/?start=0&sz=64", "12:00"),
    ("US MINT","8-27","best-of-the-mint-1804-silver-dollar-gold-coin-silver-medal-set","https://www.usmint.gov/best-of-the-mint-1804-silver-dollar-gold-coin-and-silver-medal-set-26BM4.html","https://www.usmint.gov/product-schedule/2026/?start=0&sz=64", "12:00"),
    # ── NON-SPORTS CARDS ──────────────────────────────────────────────────
    ("NON-SPORTS CARDS","8-7","2026-leaf-seasons-in-the-sun-baseball","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-19","2025-26-upper-deck-clear-cut-hockey","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("NON-SPORTS CARDS","8-19","2026-upper-deck-cfl-football","https://www.checklistinsider.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-inspirations-world-of-dc","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-rittenhouse-star-trek-voyager","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-aew-wrestling","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-topps-chrome-sapphire-veefriends","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    # ── MATTEL CREATIONS ──────────────────────────────────────────────────

    # ── MATTEL CREATIONS — confirmed from launch calendar ─────────────────
    # 8/18: Hot Wheels RLC Member Exclusive Ferrari F40 @ 9am PT (12pm ET)
    ("MATTEL CREATIONS","8-18","hot-wheels-rlc-exclusive-ferrari-f40","https://creations.mattel.com/products/hot-wheels-rlc-exclusive-ferrari-f40-jjy72","https://creations.mattel.com/pages/launch-calendar", "12:00"),
    # 8/18: Barbie Signature Creations Exclusive @ 9pm PT (12am ET 8/19)
    ("MATTEL CREATIONS","8-18","barbie-signature-creations-exclusive-design-august","https://creations.mattel.com/pages/launch-calendar","", "00:00"),
    # 8/19: Monster High Skullector Member Only Access 24 Hours @ 9am PT (12pm ET)
    ("MATTEL CREATIONS","8-19","monster-high-skullector-member-only-august","https://creations.mattel.com/pages/launch-calendar","", "12:00"),
    # 8/20: Hot Wheels Collector Creations Exclusive Design @ 9am PT (12pm ET)
    ("MATTEL CREATIONS","8-20","hot-wheels-collector-creations-exclusive-design-august-20","https://creations.mattel.com/pages/launch-calendar","", "12:00"),
    # 8/25: Hot Wheels Collector Member Exclusive @ 9am PT (12pm ET)
    ("MATTEL CREATIONS","8-25","hot-wheels-collector-member-exclusive-august-25","https://creations.mattel.com/pages/launch-calendar","", "12:00"),
    # 8/28: Hot Wheels Collector Creations Exclusive Design @ 6am PT (9am ET)
    ("MATTEL CREATIONS","8-28","hot-wheels-collector-creations-exclusive-design-august-28","https://creations.mattel.com/pages/launch-calendar","", "09:00"),
    # ── SUPREME FW26 ──────────────────────────────────────────────────────
    ("SUPREME FW26","8-TBD","supreme-fw26-preview-lookbook","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops", "11:00"),
    ("SUPREME FW26","8-TBD","supreme-fw26-week-1","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops", "11:00"),
    ("SUPREME FW26","8-TBD","supreme-fw26-week-2","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops", "11:00"),
    # ── COLLAB / LIFESTYLE ────────────────────────────────────────────────
    ("COLLAB / LIFESTYLE","8-6","jjjjound-x-new-balance-740n-mushroom","https://jjjjound.com","https://hypebeast.com/tags/weekly-footwear-drops", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","bobby-hundreds-x-disney-collab","https://thehundreds.com","https://supremedroplist.com/", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","hellstar-x-adidas","https://www.adidas.com","https://hypebeast.com/tags/weekly-footwear-drops", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","kith-august-monthly-drop","https://kith.com","https://hypebeast.com/tags/weekly-drops", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","perks-and-mini-x-asics-collab","https://www.asics.com","https://hypebeast.com/tags/weekly-footwear-drops", "10:00"),
    ("COLLAB / LIFESTYLE","9-1","walmart-rotisserie-chicken-purse","https://www.sparkshop.com/store.html?vid=20241204519&cid=99373&utm_source=GlobalComms&utm_medium=GlobalCommsChickenPurseMedia&utm_campaign=ChickenPurse2026","https://corporate.walmart.com/news/2026/08/31/walmart-serves-up-a-limited-edition-rotisserie-chicken-purse-for-national-chicken-month", "08:00"),
    # ── DISNEY PARKS PINS ─────────────────────────────────────────────────
    ("DISNEY PARKS PINS","8-4","wdw-august-le-pin-week-1","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-11","wdw-august-le-pin-week-2","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-disney-pinnacle-booth","https://d23.com/d23-2026/","https://x.com/DisneyPinnacle/status/2081016173999862201", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-disney-princess-all-13-le-pin-1200","https://d23.com/d23-2026/","https://x.com/DPrincess_Facts/status/2081016173999862201", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-exclusive-pin-drops-weekend","https://d23.com/d23-2026/","https://disneypinsblog.com", "09:00"),

    ("DISNEY PARKS PINS","8-15","d23-2026-wdi-mickeys-of-glendale-pin-releases-saturday","https://disneypinsblog.com/d23-marketplace-pin-store-pin-releases-at-d23-2026/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-15","d23-2026-disney-studio-store-hollywood-pin-releases-saturday","https://disneypinsblog.com/d23-marketplace-pin-store-pin-releases-at-d23-2026/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-16","d23-2026-wdi-mickeys-of-glendale-pin-releases-sunday","https://disneypinsblog.com/d23-marketplace-pin-store-pin-releases-at-d23-2026/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-16","d23-2026-disney-studio-store-hollywood-pin-releases-sunday","https://disneypinsblog.com/d23-marketplace-pin-store-pin-releases-at-d23-2026/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-16","d23-2026-walt-disney-company-pin-store-releases-sunday","https://disneypinsblog.com/d23-marketplace-pin-store-pin-releases-at-d23-2026/","https://disneypinsblog.com", "09:00"),    ("DISNEY PARKS PINS","8-18","wdw-august-le-pin-week-3","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-25","wdw-august-le-pin-week-4","https://disneypinsblog.com","https://mypincentral.com", "09:00"),

    ("DISNEY PARKS PINS","8-25","wdw-hocus-pocus-sanderson-sisters-minnie-clarabelle-daisy-le-3000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-25","wdw-hocus-pocus-sanderson-sisters-mystery-set-lr","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-25","wdw-hispanic-latin-heritage-month-emperors-new-groove-artist-spotlight","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),    ("DISNEY PARKS PINS","8-TBD","wdw-halloween-2026-pin-series-launch","https://disneypinsblog.com/halloween-2026-pin-releases-at-disney-store-disney-parks/","", "09:00"),

    ("DISNEY PARKS PINS","8-4","wdw-windows-of-attraction-zurg-le-2500","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-4","wdw-ap-halloween-mickey-castle-le-4000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-4","wdw-pinocchio-kingdom-hearts-pin-le-4000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),

    ("DISNEY PARKS PINS","8-4","wdw-jose-play-along-pins-series-8-le-2000","https://disneypinsblog.com/new-disney-pins-august-2026-week-1/","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/", "09:00"),
    ("DISNEY PARKS PINS","8-4","wdw-ap-halloween-mickey-castle-le-4000-pin","https://disneypinsblog.com/new-disney-pins-august-2026-week-1/","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/", "09:00"),
    ("DISNEY PARKS PINS","8-4","wdw-windows-of-attraction-buzz-lightyear-space-ranger-spin-le-2500","https://disneypinsblog.com/new-disney-pins-august-2026-week-1/","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/", "09:00"),    ("DISNEY PARKS PINS","8-11","wdw-digitize-disney-figment-le-3000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-11","wdw-magical-theater-pinocchio-pin-of-month-le-4500","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),

    ("DISNEY PARKS PINS","8-11","wdw-digitize-disney-spaceship-earth-epcot-jumbo-le-3000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-11","wdw-digitize-disney-tower-of-terror-jumbo-le-3000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),    ("DISNEY PARKS PINS","8-18","wdw-hocus-pocus-cats-dogs-halloween-mystery-set","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-18","wdw-alice-in-wonderland-75th-anniversary-pins","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),

    ("DISNEY PARKS PINS","8-18","wdw-alice-in-wonderland-75th-anniversary-jumbo-pin-le","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-18","wdw-alice-in-wonderland-75th-anniversary-mystery-set","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-18","wdw-alice-in-wonderland-75th-anniversary-pin-series-6-pins","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-18","wdw-digitize-disney-goofy-kilimanjaro-safaris-pandora-le-3000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-18","wdw-digitize-disney-yeti-expedition-everest-festival-lion-king-le-3000","https://wdwnt.com/2026/08/august-2026-walt-disney-world-pin-releases-include-halloween-hocus-pocus-alice-in-wonderland-75th-anniversary/","https://disneypinsblog.com", "09:00"),    # ── VINYL & MUSIC — pauseandplay.com ──────────────────────────────────
    ("VINYL & MUSIC","8-7","phoebe-bridgers-new-album-2026","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-7","alice-in-chains-mtv-unplugged-double-vinyl-reissue","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-7","bob-marley-and-the-wailers-reissue-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-7","everything-but-the-girl-reissue-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-7","john-coltrane-reissue-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-8","lin-manuel-miranda-rise-up-hamilton-anthology-7lp-box-set-10th-anniversary","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","leon-bridges-happiness-anytime-white-sand-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","joy-oladokun-hope-is-a-heavy-thing-transparent-black-ice-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","nothing-but-thieves-stray-dogs-pink-rose-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","blondshell-violins-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),

    ("VINYL & MUSIC","8-14","weezer-new-album-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","sam-smith-new-album-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),    ("VINYL & MUSIC","8-21","paul-simon-the-quiet-celebration-concert-triple-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-28","nickelback-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","nine-inch-nails-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","marilyn-manson-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-TBD","record-store-day-drops-2-2026","https://www.recordstoreday.com","", "00:00"),
    ("VINYL & MUSIC","8-TBD","august-limited-pressing-releases","https://www.plaidroomrecords.com/collections/pre-orders","", "00:00"),

    ("VINYL & MUSIC","8-7","abba-dancing-queen-50th-anniversary-10-inch-sparkling-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-7","lainey-wilson-live-from-stagecoach-2026-amazon-exclusive-ep","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","editors-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","ministry-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","fuel-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    # Sound Garden Baltimore — Monday Leftovers (recurring weekly @ 10am ET)
    ("VINYL & MUSIC","8-3","sound-garden-baltimore-leftovers-8-3","https://www.instagram.com/sg_bmore/","", "10:00"),
    ("VINYL & MUSIC","8-10","sound-garden-baltimore-leftovers-8-10","https://www.instagram.com/sg_bmore/","", "10:00"),
    ("VINYL & MUSIC","8-17","sound-garden-baltimore-leftovers-8-17","https://www.instagram.com/sg_bmore/","", "10:00"),
    ("VINYL & MUSIC","8-24","sound-garden-baltimore-leftovers-8-24","https://www.instagram.com/sg_bmore/","", "10:00"),
    ("VINYL & MUSIC","8-31","sound-garden-baltimore-leftovers-8-31","https://www.instagram.com/sg_bmore/","", "10:00"),

]


# ── DEDUPLICATE ───────────────────────────────────────────────────────────
def merge(manual, scraped):
    seen = set()
    out = []
    for d in manual:
        key = d[2][:40]
        if key not in seen:
            seen.add(key)
            out.append(d)
    for d in scraped:
        key = d["name"][:40]
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def sort_key(d):
    date_str = d[1] if isinstance(d, tuple) else d.get("date","8-TBD")
    parts = str(date_str).split("-")
    try:
        return int(parts[1]) if parts[1] != "TBD" else 9999
    except:
        return 9999


# ── WRITE JSON ────────────────────────────────────────────────────────────
def write_json(drops, month_key, month_name):
    os.makedirs(DATA_DIR, exist_ok=True)

    records = []
    for item in drops:
        if isinstance(item, tuple):
            cat,date_str,name = item[0],item[1],item[2]
            url1 = item[3]
            url2 = item[4] if len(item)>4 else ""
            time_et = item[5] if len(item)>5 else CAT_TIMES.get(cat,"09:00")
        else:
            cat,date_str,name = item["cat"],item["date"],item["name"]
            url1,url2,time_et = item["url1"],item.get("url2",""),item.get("time","09:00")

        parts = str(date_str).split("-")
        try:
            day = int(parts[1]) if parts[1]!="TBD" else None
        except:
            day = None

        records.append({
            "cat":    cat,
            "date":   date_str,
            "month":  int(parts[0]) if parts[0].isdigit() else MONTH_NUM,
            "day":    day,
            "tbd":    day is None,
            "name":   name,
            "url1":   url1,
            "url2":   url2 if url2 else "",
            "time":   time_et,
        })

    month_data = {
        "month":     month_name,
        "month_key": month_key,
        "updated":   datetime.date.today().isoformat(),
        "drops":     records,
    }

    out_path = os.path.join(DATA_DIR, f"{month_key}.json")
    with open(out_path, "w") as f:
        json.dump(month_data, f, separators=(',',':'))
    print(f"  Written {out_path} ({os.path.getsize(out_path):,} bytes, {len(records)} drops)")

    # Update manifest
    idx_path = os.path.join(DATA_DIR, "index.json")
    if os.path.exists(idx_path):
        with open(idx_path) as f:
            manifest = json.load(f)
    else:
        manifest = []

    # Update or insert this month
    found = False
    for entry in manifest:
        if entry["month_key"] == month_key:
            entry["updated"] = datetime.date.today().isoformat()
            found = True
            break
    if not found:
        manifest.append({
            "month":     month_name,
            "month_key": month_key,
            "file":      f"data/{month_key}.json",
            "active":    True,
        })
    # Sort newest first
    manifest.sort(key=lambda x: x["month_key"], reverse=True)

    with open(idx_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest updated ({len(manifest)} months)")
    return month_data


# ── BUILD HTML SHELL ──────────────────────────────────────────────────────
def build_html(month_key, month_name):
    """Lightweight shell — all drop data fetched at runtime from data/*.json"""

    badge_css = btn_css = ""
    for cat,(bg,fg) in CAT_COLORS.items():
        sl = cslug(cat)
        badge_css += f".cat-{sl}{{background:{bg};color:{fg};}}\n"
        btn_css   += f'.filter-btn[data-filter="{sl}"].active{{background:{bg};color:{fg};border-color:{bg};}}\n'

    logo_img_src  = f"data:image/png;base64,{LOGO_64}"  if LOGO_64  else ""
    logo_fav_src  = f"data:image/png;base64,{LOGO_FAV}" if LOGO_FAV else ""
    today_str     = datetime.date.today().strftime("%-m/%-d/%Y")
    today_day     = datetime.date.today().day
    today_month   = datetime.date.today().month
    today_year    = datetime.date.today().year

    cat_map_js = json.dumps({cslug(k): v[0] for k,v in CAT_COLORS.items()})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{"<link rel='icon' type='image/png' href='" + logo_fav_src + "'>" if logo_fav_src else ""}
<title>Grailz — Collectibles Drop Calendar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#06060d;--surface:#0e0e1a;--border:#1e1230;--accent:#1eb8f0;--accent2:#9b3fe8;--accent3:#00e5ff;--text:#e8e8f8;--muted:#6b6b90;--row-alt:#0a0a14;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Space Grotesk',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
body::before{{content:'';position:fixed;inset:0;background:url('data:image/jpeg;base64,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') center/cover no-repeat;opacity:0.18;pointer-events:none;z-index:0;}}
.bg-watermark{{
  position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
  width:60vw;max-width:600px;height:auto;aspect-ratio:1;
  background-image:url({logo_img_src});
  background-size:contain;background-repeat:no-repeat;background-position:center;
  opacity:0.06;pointer-events:none;z-index:0;
}}
header,main,.cal-section,.day-panel,.divider,.controls,.table-wrap,footer{{position:relative;z-index:1;}}
header{{border-bottom:1px solid var(--border);padding:18px 40px;background:linear-gradient(135deg,#06060d 60%,#0e0a1a 100%);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;}}
.logo-wrap{{display:flex;align-items:center;gap:14px;}}
.logo-img{{width:52px;height:52px;border-radius:50%;filter:drop-shadow(0 0 10px #9b3fe8) drop-shadow(0 0 20px #1eb8f060);flex-shrink:0;}}
.logo{{font-family:'Space Mono',monospace;font-size:42px;font-weight:700;background:linear-gradient(90deg,#fff 0%,#c084fc 35%,#9b3fe8 60%,#1eb8f0 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:4px;line-height:1;filter:drop-shadow(0 0 18px #9b3fe870);}}
.subtitle{{font-size:12px;color:#8b6baa;letter-spacing:.16em;text-transform:uppercase;margin-top:6px;}}

.month-select{{font-family:'Space Mono',monospace;font-size:11px;background:linear-gradient(135deg,#9b3fe820,#1eb8f020);border:1px solid #9b3fe860;color:#c084fc;padding:6px 14px;border-radius:20px;cursor:pointer;outline:none;max-width:180px;}}
.month-select option{{background:#0e0e1a;color:#e8e8f8;}}
.loading-bar{{width:100%;height:2px;background:linear-gradient(90deg,#9b3fe8,#1eb8f0);position:fixed;top:0;left:0;z-index:999;transform-origin:left;animation:loadbar 1.2s ease-in-out infinite;display:none;}}
.loading-bar.active{{display:block;}}
@keyframes loadbar{{0%{{transform:scaleX(0);opacity:1;}}80%{{transform:scaleX(0.9);opacity:1;}}100%{{transform:scaleX(1);opacity:0;}}}}
.cal-section{{max-width:1100px;margin:28px auto 0;padding:0 32px;}}
.cal-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:10px;}}
.cal-title{{font-family:'Space Mono',monospace;font-size:14px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;}}
.cal-controls{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
.view-toggle{{display:flex;gap:0;border:1px solid var(--border);border-radius:8px;overflow:hidden;}}
.view-btn{{font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:6px 14px;border:none;background:transparent;color:var(--muted);cursor:pointer;letter-spacing:.06em;text-transform:uppercase;transition:all .15s;}}
.view-btn:hover{{background:#1a1a2a;color:var(--text);}}
.view-btn.active{{background:var(--accent2);color:#fff;}}
.cal-legend{{display:none;}}
.legend-item{{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--muted);}}
.legend-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
.cal-table{{width:100%;border-collapse:collapse;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--surface);table-layout:fixed;}}
.cal-table thead th{{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:center;padding:10px 4px;background:#0a0a14;border-bottom:1px solid var(--border);width:14.28%;}}
.cal-cell{{height:100px;padding:6px 5px;vertical-align:top;border-right:1px solid var(--border);border-bottom:1px solid var(--border);cursor:default;transition:background .12s;overflow:hidden;position:relative;}}
.cal-table td{{padding:6px 5px;vertical-align:top;}}
.cal-cell.empty{{background:#08080f;}}
.cal-cell.has-drops{{background:#0d0b1a;cursor:pointer;}}
.cal-cell.has-drops:hover{{background:#12101e;}}
.cal-cell.selected{{background:#130f22;box-shadow:inset 0 0 0 2px var(--accent2);}}
.cal-cell.today .day-num{{background:var(--accent2);color:#fff;border-radius:50%;}}
.day-num{{font-family:'Space Mono',monospace;font-size:11px;font-weight:700;color:var(--muted);width:22px;height:22px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-bottom:3px;}}
.cal-cell.has-drops .day-num{{color:var(--text);}}
.cal-chips{{display:flex;flex-direction:column;gap:2px;}}
.cal-chip{{font-size:9px;font-weight:600;padding:2px 5px;border-radius:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4;}}
.cal-more{{font-size:8px;color:var(--muted);font-family:'Space Mono',monospace;padding-left:3px;}}
.week-nav,.day-nav{{display:flex;align-items:center;gap:12px;margin-bottom:14px;}}
.week-nav-btn,.day-nav-btn{{font-family:'Space Mono',monospace;font-size:18px;background:none;border:1px solid var(--border);color:var(--muted);width:32px;height:32px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;}}
.week-nav-btn:hover,.day-nav-btn:hover{{border-color:var(--accent2);color:var(--text);}}
.week-label,.day-label{{font-family:'Space Mono',monospace;font-size:12px;color:var(--text);letter-spacing:.06em;}}
.week-table{{width:100%;border-collapse:collapse;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--surface);table-layout:fixed;}}
.week-table thead th{{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:center;padding:8px 4px;background:#0a0a14;border-bottom:1px solid var(--border);}}
.week-table thead th.week-th-today{{color:var(--accent2);}}
.week-cell{{height:140px;padding:8px 6px;vertical-align:top;border-right:1px solid var(--border);cursor:default;overflow:hidden;}}
.week-cell.has-drops{{background:#0d0b1a;cursor:pointer;}}
.week-cell.has-drops:hover{{background:#12101e;}}
.week-cell.week-today{{border-top:2px solid var(--accent2);}}
.week-date{{font-family:'Space Mono',monospace;font-size:11px;font-weight:700;color:var(--muted);margin-bottom:4px;}}
.week-cell.has-drops .week-date{{color:var(--text);}}
.day-view-inner{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px 24px;min-height:200px;}}
.day-empty{{text-align:center;padding:48px 0;color:var(--muted);font-family:'Space Mono',monospace;font-size:12px;}}
.day-panel{{display:none !important;}}
.day-panel.visible{{display:block;}}
.day-panel-inner{{background:var(--surface);border:1px solid #9b3fe850;border-radius:10px;padding:16px 20px;}}
.day-panel-title{{font-family:'Space Mono',monospace;font-size:12px;color:#c084fc;margin-bottom:12px;letter-spacing:.06em;}}
.panel-drop{{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#0a0a14;border-radius:6px;border:1px solid var(--border);margin-bottom:6px;flex-wrap:wrap;}}
.panel-drop:last-of-type{{margin-bottom:0;}}
.panel-drop-name{{font-size:12px;color:var(--text);flex:1;min-width:120px;}}
.panel-srcs{{display:flex;gap:6px;flex-shrink:0;}}
.panel-srcs a{{font-family:'Space Mono',monospace;font-size:9px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:2px 7px;border-radius:3px;}}
.drop-cal-row{{display:none;}}
.drop-time-input{{background:#0e0e1a;border:1px solid var(--border);color:var(--text);font-family:'Space Mono',monospace;font-size:11px;padding:4px 8px;border-radius:5px;outline:none;-webkit-appearance:none;width:110px;}}
.drop-alert-num{{background:#0e0e1a;border:1px solid var(--border);color:var(--text);font-family:'Space Mono',monospace;font-size:11px;padding:4px 6px;border-radius:5px;outline:none;width:52px;}}
.drop-alert-unit{{background:#0e0e1a;border:1px solid var(--border);color:var(--text);font-family:'Space Mono',monospace;font-size:11px;padding:4px 6px;border-radius:5px;outline:none;cursor:pointer;}}
.btn-ics-sm{{font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:5px 10px;border-radius:5px;border:none;cursor:pointer;background:linear-gradient(135deg,#9b3fe8,#1eb8f0);color:#fff;letter-spacing:.04em;text-transform:uppercase;transition:filter .15s;display:flex;align-items:center;gap:4px;white-space:nowrap;}}
.btn-ics-sm:hover{{filter:brightness(1.2);}}
.day-drop-row{{display:flex;align-items:center;gap:10px;padding:10px 12px;background:#0a0a14;border-radius:6px;border:1px solid var(--border);margin-bottom:8px;flex-wrap:wrap;;flex-wrap:wrap;}}.day-ics-btn{{margin-left:auto;white-space:nowrap;}}
.day-drop-row:last-of-type{{margin-bottom:0;}}
.day-drop-time{{font-family:'Space Mono',monospace;font-size:11px;color:var(--accent2);font-weight:700;white-space:nowrap;min-width:72px;}}
.day-drop-name{{font-size:12px;color:var(--text);flex:1;min-width:120px;}}
.day-srcs{{display:flex;gap:6px;flex-shrink:0;}}
.day-srcs a{{font-family:'Space Mono',monospace;font-size:9px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:2px 7px;border-radius:3px;}}
.divider{{max-width:1100px;margin:28px auto 0;padding:0 32px;display:flex;align-items:center;gap:12px;cursor:pointer;user-select:none;}}
.divider:hover .div-label{{color:var(--accent2);}}
#controlsWrap{{overflow:hidden;transition:max-height .3s ease,opacity .3s ease;max-height:300px;opacity:1;}}
#controlsWrap.collapsed{{max-height:0 !important;opacity:0;pointer-events:none;}}
.div-line{{flex:1;height:1px;background:var(--border);}}
.div-label{{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);white-space:nowrap;}}
.controls{{max-width:1100px;margin:16px auto 0;padding:0 32px;display:flex;flex-direction:column;gap:12px;}}
.search-wrap{{display:flex;align-items:center;gap:10px;}}
#search{{background:var(--surface);border:1px solid var(--border);color:var(--text);font-family:'Space Grotesk',sans-serif;font-size:14px;padding:9px 14px;border-radius:6px;width:280px;outline:none;}}
#search:focus{{border-color:var(--accent2);}}
#search::placeholder{{color:var(--muted);}}
.count{{font-size:12px;color:var(--muted);font-family:'Space Mono',monospace;}}
.tbd-btn{{font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:5px 12px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;letter-spacing:.04em;text-transform:uppercase;}}
.add-all-btn{{border-color:var(--accent2);color:var(--accent2);}}
.add-all-btn:hover{{background:var(--accent2);color:#fff;}}
.tbd-btn.active{{background:var(--accent2);color:#fff;border-color:var(--accent2);}}
.filters{{display:flex;flex-wrap:wrap;gap:6px;}}
.filter-btn{{font-family:'Space Grotesk',sans-serif;font-size:11px;font-weight:600;padding:5px 12px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;letter-spacing:.04em;text-transform:uppercase;}}
.filter-btn:hover{{border-color:var(--text);color:var(--text);}}
.filter-btn.active{{background:var(--accent2);color:#fff;border-color:var(--accent2);}}
{btn_css}
.table-wrap{{max-width:1100px;margin:12px auto 0;padding:0 32px 60px;overflow-x:auto;}}
table.drop-table{{width:100%;border-collapse:collapse;font-size:13px;}}
table.drop-table thead th{{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 16px;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none;}}
table.drop-table thead th:hover{{color:var(--text);}}
table.drop-table thead th.sorted::after{{content:' ↑';color:var(--accent3);}}
table.drop-table thead th.sorted.desc::after{{content:' ↓';}}
tbody tr{{border-bottom:1px solid #1e1e26;transition:background .1s;}}
tbody tr:nth-child(even){{background:var(--row-alt);}}
tbody tr:hover{{background:#100d1e;box-shadow:inset 3px 0 0 var(--accent2);}}
tbody tr.hidden{{display:none;}}
td{{padding:10px 16px;vertical-align:middle;}}
.cat-badge{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:4px;white-space:nowrap;}}
{badge_css}
.date-cell{{font-family:'Space Mono',monospace;font-size:12px;color:var(--muted);white-space:nowrap;}}
.date-time-cell{{white-space:nowrap;min-width:115px;line-height:1;}}
.dt-date{{font-family:'Space Mono',monospace;font-size:10px;color:var(--muted);display:block;margin-bottom:3px;}}
.dt-time{{font-family:'Space Mono',monospace;font-size:13px;color:var(--accent3);font-weight:700;display:block;}}
.time-cell{{font-family:'Space Mono',monospace;font-size:11px;color:#9b3fe8;white-space:nowrap;font-weight:600;}}
.name-cell{{font-size:13px;color:var(--text);max-width:380px;}}
.source-cell{{display:flex;gap:8px;flex-wrap:wrap;}}
@media(max-width:700px){{.source-cell a:nth-child(2),.source-cell a:nth-child(n+2){{display:none;}}}}
.ics-cell{{vertical-align:middle;white-space:nowrap;}}
.tbl-cal-row{{display:flex;align-items:center;gap:4px;flex-wrap:nowrap;}}
.tbl-cal-row .drop-time-input{{width:90px;font-size:10px;padding:3px 6px;}}
.tbl-cal-row .drop-alert-num{{width:42px;font-size:10px;padding:3px 4px;}}
.tbl-cal-row .drop-alert-unit{{font-size:10px;padding:3px 4px;}}
.source-cell a{{font-family:'Space Mono',monospace;font-size:10px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:3px 8px;border-radius:4px;}}
.no-results{{text-align:center;padding:60px 0;color:var(--muted);font-family:'Space Mono',monospace;font-size:13px;display:none;}}
footer{{border-top:1px solid var(--border);padding:20px 40px;font-size:11px;color:var(--muted);font-family:'Space Mono',monospace;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;background:linear-gradient(135deg,#06060d,#0a0814);}}
@media(max-width:700px){{header,.cal-section,.day-panel,.divider,.controls,.table-wrap{{padding-left:16px;padding-right:16px;}}#search{{width:100%;}}.cal-cell{{height:72px;}}}}
</style>
</head>
<body>
<div class="loading-bar" id="loadingBar"></div>
<div class="bg-watermark"></div>

<header>
  <div class="logo-wrap">
    {"<img src='" + logo_img_src + "' alt='Grailz' class='logo-img'>" if logo_img_src else ""}
    <div><div class="logo">GRAILZ</div><div class="subtitle">Artist &amp; Collectible Drops</div></div>
  </div>
</header>

<div class="cal-section">
  <div class="cal-top">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
      <div class="view-toggle">
        <button class="view-btn active" data-view="month">Month</button>
        <button class="view-btn" data-view="week">Week</button>
        <button class="view-btn" data-view="day">Day</button>
      </div>
    </div>
    <div class="cal-controls">
        <select class="month-select" id="monthSelect"><option value="">Loading…</option></select></div>
  </div>
  <div class="cal-legend" id="legend"></div>

  <div id="viewMonth" style="margin-top:14px;">
    <table class="cal-table">
      <thead><tr><th>Sun</th><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th>Sat</th></tr></thead>
      <tbody id="calBody"></tbody>
    </table>
  </div>
  <div id="viewWeek" style="display:none;margin-top:14px;">
    <div class="week-nav">
      <button class="week-nav-btn" id="weekPrev">‹</button>
      <span class="week-label" id="weekLabel"></span>
      <button class="week-nav-btn" id="weekNext">›</button>
    </div>
    <table class="week-table"><thead id="weekHead"></thead><tbody id="weekBody"></tbody></table>
  </div>
  <div id="viewDay" style="display:none;margin-top:14px;">
    <div class="day-nav">
      <button class="day-nav-btn" id="dayPrev">‹</button>
      <span class="day-label" id="dayLabel"></span>
      <button class="day-nav-btn" id="dayNext">›</button>
    </div>
    <div class="day-view-inner" id="dayViewInner"></div>
  </div>
</div>

<div class="day-panel" id="dayPanel">
  <div class="day-panel-inner">
    <div class="day-panel-title" id="panelTitle"></div>
    <div id="panelBody"></div>
  </div>
</div>

<div class="divider" id="filterToggle" style="cursor:pointer;" title="Click to collapse/expand filters"><div class="div-line"></div><div class="div-label">Drop Filter <span id="filterChevron">▼</span></div><div class="div-line"></div></div>

<div class="controls collapsed" id="controlsWrap">
  <div class="search-wrap">
    <input id="search" type="text" placeholder="Search drops…" autocomplete="off">
    <button id="tbdToggle" class="tbd-btn">Show TBD</button>
    <button id="addAllBtn" class="tbd-btn add-all-btn">&#128197; Add All to Calendar</button>
    <span class="count" id="count"></span>
  </div>
  <div class="filters" id="filterBtns"></div>
</div>

<div class="table-wrap">
  <table class="drop-table">
    <thead><tr>
      <th>Add</th>
      <th data-col="0" class="sorted">DATE</th>
      <th data-col="1" style="display:none">Date</th>
      <th data-col="2" style="display:none">Time (CT)</th>
      <th data-col="3">Category</th>
      <th data-col="4">Drop</th>
      <th data-col="5">Sources</th>
    </tr></thead>
    <tbody id="tbody"></tbody>
  </table>
  <div class="no-results" id="noResults">No drops found.</div>
</div>

<footer>
  <span id="footerUpdated">Updated {today_str} · <em style="color:var(--accent2);font-style:normal;">The early bird gets the grail.</em></span>
  <div class="social-links">
    <a href="#" class="social-btn" id="socialLink1">Discord</a>
    <a href="#" class="social-btn" id="socialLink2">Instagram</a>
    <a href="#" class="social-btn" id="socialLink3">TikTok</a>
  </div>
</footer>

<script>
// ── Constants ─────────────────────────────────────────────────────────────
const CAT_MAP   = {cat_map_js};
const _now = new Date();
const TODAY_DAY = _now.getDate();
const TODAY_MON = _now.getMonth() + 1;
const TODAY_YR  = _now.getFullYear();

// ── State ──────────────────────────────────────────────────────────────────
let DROPS=[], MONTH_N=0, YEAR_N=0, MONTH_NAME='', byDay={{}};
let currentView='month', currentWeekStart=null, currentDayDate=null, selectedDay=null;

// ── Helpers ────────────────────────────────────────────────────────────────
const pad  = n => String(n).padStart(2,'0');
const cslug = c => c.toLowerCase().replace(/[^a-z0-9]+/g,' ').trim().replace(/ /g,'-');
function fmt12(t){{
  if(!t)return'';
  const[h,m]=t.split(':').map(Number);
  return (h%12||12)+':'+(m<10?'0'+m:m)+' '+(h<12?'AM':'PM');
}}
function fmtShort(d){{return d.toLocaleDateString('en-US',{{month:'short',day:'numeric'}});}}
function getWeekStart(d){{const s=new Date(d);s.setDate(s.getDate()-s.getDay());s.setHours(0,0,0,0);return s;}}
function icsDate(y,m,d,t){{const[h,mi]=t.split(':').map(Number);return y+pad(m)+pad(d)+'T'+pad(h)+pad(mi)+'00';}}
function loading(on){{document.getElementById('loadingBar').classList.toggle('active',on);}}

// ── Fetch JSON data ────────────────────────────────────────────────────────
async function loadMonth(monthKey){{
  loading(true);
  try{{
    const r = await fetch('data/'+monthKey+'.json?v='+Date.now());
    if(!r.ok) throw new Error('HTTP '+r.status);
    const data = await r.json();
    DROPS    = data.drops;
    MONTH_N  = DROPS[0]?.month || TODAY_MON;
    YEAR_N   = parseInt(monthKey.split('-')[0]);
    MONTH_NAME = data.month;

    // Rebuild byDay
    byDay={{}};
    DROPS.forEach(d=>{{if(d.day)(byDay[d.day]=byDay[d.day]||[]).push(d);}});

    // Reset date state to this month's today or 1st
    const isCurrentMonth = (MONTH_N===TODAY_MON && YEAR_N===TODAY_YR);
    currentDayDate  = new Date(YEAR_N, MONTH_N-1, isCurrentMonth ? TODAY_DAY : 1);
    currentWeekStart = getWeekStart(currentDayDate);

    renderAll();
    document.getElementById('footerUpdated').textContent = 'Updated '+data.updated+' · Grailz Discord Server';
  }}catch(e){{
    console.error('Failed to load',monthKey,e);
  }}finally{{
    loading(false);
  }}
}}

async function loadManifest(){{
  loading(true);
  try{{
    const r = await fetch('data/index.json?v='+Date.now());
    const manifest = await r.json();
    const sel = document.getElementById('monthSelect');
    sel.innerHTML = manifest.map(m=>
      `<option value="${{m.month_key}}">${{m.month}}</option>`
    ).join('');
    sel.addEventListener('change', e=>loadMonth(e.target.value));
    // Load current month by default, fall back to most recent
    const currentKey = TODAY_YR+'-'+(TODAY_MON<10?'0'+TODAY_MON:TODAY_MON);
    const match = manifest.find(m=>m.month_key===currentKey);
    const toLoad = match ? match.month_key : manifest[0].month_key;
    sel.value = toLoad;
    await loadMonth(toLoad);
  }}catch(e){{
    console.error('Failed to load manifest',e);
    // Fallback: try current month directly
    await loadMonth('{month_key}');
  }}finally{{
    loading(false);
  }}
}}

// ── Render all views ───────────────────────────────────────────────────────
function renderAll(){{
  const ch=document.getElementById('calHeading');if(ch)ch.textContent=MONTH_NAME;
  buildLegend();
  buildTable();
  switchView(currentView);
}}

// ── Legend ─────────────────────────────────────────────────────────────────
function buildLegend(){{
  const el = document.getElementById('legend');
  el.innerHTML='';
  const seen={{}};
  DROPS.forEach(d=>{{if(!seen[cslug(d.cat)])seen[cslug(d.cat)]={{cat:d.cat,color:CAT_MAP[cslug(d.cat)]||'#2a2a35'}};}});
  Object.entries(seen).sort((a,b)=>a[1].cat.localeCompare(b[1].cat)).forEach(([sl,info])=>{{
    const item=document.createElement('div');item.className='legend-item';
    item.innerHTML='<span class="legend-dot" style="background:'+info.color+'"></span>'+info.cat;
    el.appendChild(item);
  }});
}}

// ── Calendar (Month) ───────────────────────────────────────────────────────
function buildMonthView(){{
  const calBody=document.getElementById('calBody');
  const panel=document.getElementById('dayPanel');
  calBody.innerHTML='';
  panel.classList.remove('visible');
  selectedDay=null;

  const firstDow=new Date(YEAR_N,MONTH_N-1,1).getDay();
  const daysInMonth=new Date(YEAR_N,MONTH_N,0).getDate();
  let dayCount=0,row=document.createElement('tr');
  calBody.appendChild(row);

  for(let i=0;i<firstDow;i++){{
    const td=document.createElement('td');td.className='cal-cell empty';row.appendChild(td);dayCount++;
  }}
  for(let day=1;day<=daysInMonth;day++){{
    if(dayCount%7===0){{row=document.createElement('tr');calBody.appendChild(row);}}
    const dayDrops=byDay[day]||[];
    const isToday=(day===TODAY_DAY&&MONTH_N===TODAY_MON&&YEAR_N===TODAY_YR);
    const td=document.createElement('td');
    td.className='cal-cell'+(dayDrops.length?' has-drops':'')+(isToday?' today':'');
    td.dataset.day=day;
    const num=document.createElement('div');num.className='day-num';num.textContent=day;td.appendChild(num);
    if(dayDrops.length){{
      const chips=document.createElement('div');chips.className='cal-chips';
      dayDrops.slice(0,3).forEach(dr=>{{
        const chip=document.createElement('div');chip.className='cal-chip';
        chip.style.background=CAT_MAP[cslug(dr.cat)]||'#2a2a35';chip.style.color='#fff';
        chip.title=dr.name;chip.textContent=dr.cat;chips.appendChild(chip);
      }});
      if(dayDrops.length>3){{const m=document.createElement('div');m.className='cal-more';m.textContent='+'+(dayDrops.length-3)+' more';chips.appendChild(m);}}
      td.appendChild(chips);
      td.addEventListener('click',()=>{{
      currentDayDate=new Date(YEAR_N,MONTH_N-1,day);
      switchView('day');
    }});
    }}
    row.appendChild(td);dayCount++;
  }}
  while(dayCount%7!==0){{const td=document.createElement('td');td.className='cal-cell empty';row.appendChild(td);dayCount++;}}
}}

function openDayPanel(day,dayDrops,tdEl){{
  const panel=document.getElementById('dayPanel');
  const panelTitle=document.getElementById('panelTitle');
  const panelBody=document.getElementById('panelBody');
  if(selectedDay===day){{
    panel.classList.remove('visible');
    tdEl.classList.remove('selected');
    selectedDay=null;return;
  }}
  const prev=document.querySelector('.cal-cell.selected');
  if(prev)prev.classList.remove('selected');
  selectedDay=day;tdEl.classList.add('selected');
  const dt=new Date(YEAR_N,MONTH_N-1,day);
  panelTitle.textContent=dt.toLocaleDateString('en-US',{{weekday:'long',month:'long',day:'numeric',year:'numeric'}});
  panelBody.innerHTML='';
  buildDropRows(panelBody,dayDrops,day);
  panel.classList.add('visible');
  panel.scrollIntoView({{behavior:'smooth',block:'nearest'}});
}}

// ── Week view ──────────────────────────────────────────────────────────────
function buildWeekView(){{
  const wHead=document.getElementById('weekHead');
  const wBody=document.getElementById('weekBody');
  const wLabel=document.getElementById('weekLabel');
  const days=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const today=new Date(YEAR_N,MONTH_N-1,TODAY_DAY);
  const weekEnd=new Date(currentWeekStart);weekEnd.setDate(weekEnd.getDate()+6);
  wLabel.textContent=fmtShort(currentWeekStart)+' \u2013 '+fmtShort(weekEnd);
  wHead.innerHTML='';
  const hRow=document.createElement('tr');
  for(let i=0;i<7;i++){{
    const d=new Date(currentWeekStart);d.setDate(d.getDate()+i);
    const th=document.createElement('th');
    th.className=(d.toDateString()===today.toDateString())?'week-th-today':'';
    th.innerHTML=days[i]+'<br><span style="font-size:11px;font-weight:400">'+d.getDate()+'</span>';
    hRow.appendChild(th);
  }}
  wHead.appendChild(hRow);
  wBody.innerHTML='';
  const bRow=document.createElement('tr');
  for(let i=0;i<7;i++){{
    const d=new Date(currentWeekStart);d.setDate(d.getDate()+i);
    const dayN=d.getDate(),mN=d.getMonth()+1,yN=d.getFullYear();
    const dayDrops=(mN===MONTH_N&&yN===YEAR_N)?byDay[dayN]||[]:[];
    const isToday=d.toDateString()===today.toDateString();
    const td=document.createElement('td');
    td.className='week-cell'+(dayDrops.length?' has-drops':'')+(isToday?' week-today':'');
    const dd=document.createElement('div');dd.className='week-date';dd.textContent=mN+'/'+dayN;td.appendChild(dd);
    if(dayDrops.length){{
      dayDrops.slice(0,5).forEach(dr=>{{
        const chip=document.createElement('div');chip.className='cal-chip';
        chip.style.background=CAT_MAP[cslug(dr.cat)]||'#2a2a35';chip.style.color='#fff';
        chip.style.marginBottom='2px';chip.title=dr.name;chip.textContent=dr.cat;td.appendChild(chip);
      }});
      if(dayDrops.length>5){{const m=document.createElement('div');m.className='cal-more';m.textContent='+'+(dayDrops.length-5)+' more';td.appendChild(m);}}
      td.addEventListener('click',()=>{{currentDayDate=new Date(d);switchView('day');}});
    }}
    bRow.appendChild(td);
  }}
  wBody.appendChild(bRow);
}}

// ── Day view ───────────────────────────────────────────────────────────────
function buildDayView(){{
  const dInner=document.getElementById('dayViewInner');
  const dLabel=document.getElementById('dayLabel');
  dLabel.textContent=currentDayDate.toLocaleDateString('en-US',{{weekday:'long',month:'long',day:'numeric',year:'numeric'}});
  const dayN=currentDayDate.getDate(),mN=currentDayDate.getMonth()+1,yN=currentDayDate.getFullYear();
  const dayDrops=(mN===MONTH_N&&yN===YEAR_N)?byDay[dayN]||[]:[];
  dInner.innerHTML='';
  if(!dayDrops.length){{dInner.innerHTML='<div class="day-empty">No drops on this day.</div>';return;}}
  buildDropRows(dInner,dayDrops,dayN,true);
}}

// ── Shared drop row builder (panel + day view) ────────────────────────────
function buildDropRows(container, dayDrops, dayN, showTime=false){{
  dayDrops.forEach((dr,idx)=>{{
    const row=document.createElement('div');
    row.className=showTime?'day-drop-row':'panel-drop';
    const bg=CAT_MAP[cslug(dr.cat)]||'#2a2a35';
    const dropId='day-'+dayN+'-'+idx;
    let inner='';
    if(showTime) inner+=`<span class="day-drop-time">${{fmt12(dr.time||'09:00')}}</span>`;
    inner+=`<span class="cat-badge" style="background:${{bg}};color:#fff">${{dr.cat}}</span>`;
    inner+=`<span class="${{showTime?'day-drop-name':'panel-drop-name'}}">${{dr.name}}</span>`;
    inner+=`<span class="${{showTime?'day-srcs':'panel-srcs'}}">`;
    if(dr.url1)inner+=`<a href="${{dr.url1}}" target="_blank" rel="noopener">Source 1 ↗</a>`;
    if(dr.url2)inner+=`<a href="${{dr.url2}}" target="_blank" rel="noopener">Source 2 ↗</a>`;
    inner+='</span>';
    if(showTime) inner+=`<button class="btn-ics-sm day-ics-btn" data-id="${{dropId}}">&#128197; ADD</button>`;
    row.innerHTML=inner;
    if(showTime){{
      const btn=row.querySelector('.day-ics-btn');
      btn.addEventListener('click',()=>exportICS(dayN,dr.time||'09:00',30,[dr]));
    }}
    container.appendChild(row);
  }});
}}

// ── View toggle ────────────────────────────────────────────────────────────
function switchView(v){{
  currentView=v;
  document.querySelectorAll('.view-btn').forEach(b=>b.classList.toggle('active',b.dataset.view===v));
  document.getElementById('viewMonth').style.display=v==='month'?'block':'none';
  document.getElementById('viewWeek').style.display=v==='week'?'block':'none';
  document.getElementById('viewDay').style.display=v==='day'?'block':'none';
  if(v==='month')buildMonthView();
  if(v==='week')buildWeekView();
  if(v==='day')buildDayView();
  const _ch=document.getElementById('calHeading');
  if(_ch)_ch.textContent=v==='month'?MONTH_NAME:v==='week'?'Week View':'Day View';
  applyFilters(); // re-filter table for new view/date range
}}
document.querySelectorAll('.view-btn').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
document.getElementById('weekPrev').addEventListener('click',()=>{{currentWeekStart.setDate(currentWeekStart.getDate()-7);buildWeekView();applyFilters();}});
document.getElementById('weekNext').addEventListener('click',()=>{{currentWeekStart.setDate(currentWeekStart.getDate()+7);buildWeekView();applyFilters();}});
document.getElementById('dayPrev').addEventListener('click',()=>{{currentDayDate.setDate(currentDayDate.getDate()-1);buildDayView();applyFilters();}});
document.getElementById('dayNext').addEventListener('click',()=>{{currentDayDate.setDate(currentDayDate.getDate()+1);buildDayView();applyFilters();}});

// ── Table ──────────────────────────────────────────────────────────────────
function buildTable(){{
  const tbody=document.getElementById('tbody');
  tbody.innerHTML='';
  const cats=new Set();
  DROPS.forEach(d=>{{
    cats.add(d.cat);
    const sl=cslug(d.cat);
    let dateDisplay,dateSort;
    if(d.day){{
      const dt=new Date(YEAR_N,d.month-1,d.day);
      dateDisplay=dt.toLocaleDateString('en-US',{{month:'numeric',day:'numeric',year:'numeric'}});
      dateSort=YEAR_N*10000+d.month*100+d.day;
    }}else{{
      dateDisplay=d.month+'/TBD/'+YEAR_N;dateSort=99999999;
    }}
    let h=d.time?parseInt(d.time):9,m=d.time?parseInt(d.time.split(':')[1]):0;
    const ap=h<12?'AM':'PM';const h12=h%12||12;
    const timeDisplay=h12+':'+(m<10?'0'+m:m)+' '+ap;
    const u1=d.url1?`<a href="${{d.url1}}" target="_blank" rel="noopener">Source 1 ↗</a>`:'';
    const u2=d.url2?`<a href="${{d.url2}}" target="_blank" rel="noopener">Source 2 ↗</a>`:'';
    const dropTime=d.time||'09:00';
    const dropId='tbl-'+sl+'-'+(d.day||'tbd')+'-'+Math.random().toString(36).slice(2,6);
    const tr=document.createElement('tr');
    tr.dataset.cat=sl;tr.dataset.date=dateSort;tr.dataset.tbd=d.tbd?'true':'false';tr.dataset.day=d.day||0;
    tr.innerHTML=`<td class="ics-cell"><div class="tbl-cal-row"><input type="time" class="drop-time-input" id="t-${{dropId}}" value="${{dropTime}}" style="display:none"><input type="number" class="drop-alert-num" id="n-${{dropId}}" value="30" min="1" max="9999" style="display:none"><select class="drop-alert-unit" id="u-${{dropId}}" style="display:none"><option value="minutes">Min</option><option value="hours">Hrs</option><option value="days">Days</option></select><button class="btn-ics-sm" data-id="${{dropId}}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>Add</button></div></td><td class="date-time-cell"><span class="dt-date">${{dateDisplay}}</span><span class="dt-time">${{timeDisplay}}</span></td><td class="date-cell" style="display:none">${{dateDisplay}}</td><td class="time-cell" style="display:none">${{timeDisplay}}</td><td><span class="cat-badge cat-${{sl}}">${{d.cat}}</span></td><td class="name-cell">${{d.name}}</td><td class="source-cell">${{u1}}${{u1&&u2?' ':''}}${{u2}}</td>`;
    const dayN=d.day||1;
    tr.querySelector('.btn-ics-sm').addEventListener('click',()=>{{
      const t=document.getElementById('t-'+dropId).value||dropTime;
      const n=parseInt(document.getElementById('n-'+dropId).value)||30;
      const u=document.getElementById('u-'+dropId).value;
      const mins=u==='days'?n*1440:u==='hours'?n*60:n;
      exportICS(dayN,t,mins,[d]);
    }});
    tbody.appendChild(tr);
  }});
  // Filter buttons
  const fb=document.getElementById('filterBtns');
  fb.innerHTML='<button class="filter-btn active" data-filter="all">All</button>';
  [...cats].sort().forEach(cat=>{{
    const btn=document.createElement('button');
    btn.className='filter-btn';btn.dataset.filter=cslug(cat);btn.textContent=cat;
    fb.appendChild(btn);
  }});
  fb.querySelectorAll('.filter-btn').forEach(b=>b.addEventListener('click',()=>{{
    fb.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');activeFilter=b.dataset.filter;applyFilters();
  }}));
  applyFilters();
}}

let activeFilter='all',sortCol=0,sortDesc=false,showTBD=false;
function getViewDateRange(){{
  // Returns {{minDay, maxDay}} for the current view, or null for month view (no filter)
  if(currentView==='day'){{
    const d=currentDayDate;
    if(d.getMonth()+1!==MONTH_N||d.getFullYear()!==YEAR_N)return{{minDay:-1,maxDay:-1}};
    return{{minDay:d.getDate(),maxDay:d.getDate()}};
  }}
  if(currentView==='week'){{
    // Week spans currentWeekStart to currentWeekStart+6
    // Only include days that fall within the current month/year
    const ws=new Date(currentWeekStart);
    const we=new Date(currentWeekStart);we.setDate(we.getDate()+6);
    const monthStart=new Date(YEAR_N,MONTH_N-1,1);
    const monthEnd=new Date(YEAR_N,MONTH_N,0);
    // Clamp to current month
    const lo=ws<monthStart?monthStart:ws;
    const hi=we>monthEnd?monthEnd:we;
    if(lo.getMonth()+1!==MONTH_N||hi<lo)return{{minDay:-1,maxDay:-1}};
    return{{minDay:lo.getDate(),maxDay:hi.getDate()}};
  }}
  return null; // month view — no date filter
}}

function applyFilters(){{
  const q=document.getElementById('search').value.toLowerCase();
  const rows=Array.from(document.getElementById('tbody').querySelectorAll('tr'));
  const dateRange=getViewDateRange();
  let any=false;
  rows.forEach(r=>{{
    const cm=activeFilter==='all'||r.dataset.cat===activeFilter;
    const tm=!q||r.textContent.toLowerCase().includes(q);
    const isTbd=r.dataset.tbd==='true';
    let dm=true;
    if(dateRange){{
      const day=parseInt(r.dataset.day||'0');
      if(dateRange.minDay===-1){{dm=false;}} // week/day is outside this month
      else{{dm=!isTbd&&day>=dateRange.minDay&&day<=dateRange.maxDay;}}
    }}else{{
      dm=showTBD||!isTbd; // month view: respect TBD toggle
    }}
    r.classList.toggle('hidden',!(cm&&tm&&dm));
    if(cm&&tm&&dm)any=true;
  }});
  document.getElementById('noResults').style.display=any?'none':'block';
  const v=rows.filter(r=>!r.classList.contains('hidden')).length;
  document.getElementById('count').textContent=v+' drop'+(v!==1?'s':'');
}}
document.getElementById('search').addEventListener('input',applyFilters);

// Add All to Calendar — exports all dated (non-TBD) drops as one ICS file
function exportAllICS(){{
  const CRLF=String.fromCharCode(13,10);
  const toTitle=s=>s.replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  const datedDrops=DROPS.filter(d=>d.day&&!d.tbd);
  if(!datedDrops.length)return;

  const events=datedDrops.map(d=>{{
    const time=d.time||'09:00';
    const[sh,sm]=time.split(':').map(Number);
    const dtStart=icsDate(YEAR_N,MONTH_N,d.day,time);
    const dtEnd=icsDate(YEAR_N,MONTH_N,d.day,pad((sh+1)%24)+':'+pad(sm));
    const uid='grailz-'+d.name.slice(0,40)+'-'+YEAR_N+'-'+pad(MONTH_N)+'-'+pad(d.day)+'@grailzking.github.io';
    const[h,m]=time.split(':').map(Number);
    const ampm=h<12?'AM':'PM';const h12=h%12||12;
    const timeLabel=h12+':'+(m<10?'0':'')+m+' '+ampm+' CT';
    const title=toTitle(d.name)+' ['+d.cat+']';
    const link=d.url1||'https://grailzking.github.io/grailz-drops';
    const desc='Drop: '+toTitle(d.name)+'\\nCategory: '+d.cat+'\\nTime: '+timeLabel+'\\nLink: '+link+(d.url2?'\\nSource 2: '+d.url2:'')+'\\n\\nGrailz Drops Calendar: https://grailzking.github.io/grailz-drops';
    return [
      'BEGIN:VEVENT',
      'UID:'+uid,
      'DTSTAMP:'+icsDate(YEAR_N,MONTH_N,d.day,'00:00'),
      'DTSTART:'+dtStart,
      'DTEND:'+dtEnd,
      'SUMMARY:'+title,
      'DESCRIPTION:'+desc,
      'URL:'+link,
      'BEGIN:VALARM','ACTION:DISPLAY',
      'DESCRIPTION:Grailz Drop: '+toTitle(d.name).slice(0,60),
      'TRIGGER:-PT30M','END:VALARM',
      'END:VEVENT'
    ].join(CRLF);
  }});

  const ics=[
    'BEGIN:VCALENDAR','VERSION:2.0',
    'PRODID:-//Grailz//Drops Calendar//EN',
    'CALSCALE:GREGORIAN','METHOD:PUBLISH',
    'X-WR-CALNAME:Grailz Drops — '+MONTH_NAME,
    'X-WR-CALDESC:Collectibles drop calendar for '+MONTH_NAME,
    ...events,
    'END:VCALENDAR'
  ].join(CRLF);

  const blob=new Blob([ics],{{type:'text/calendar;charset=utf-8'}});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;
  a.download='grailz-drops-'+YEAR_N+'-'+pad(MONTH_N)+'.ics';
  document.body.appendChild(a);a.click();
  document.body.removeChild(a);URL.revokeObjectURL(url);
}}

document.getElementById('addAllBtn').addEventListener('click', exportAllICS);
document.getElementById('filterToggle').addEventListener('click',()=>{{
  const wrap=document.getElementById('controlsWrap');
  const chevron=document.getElementById('filterChevron');
  const collapsed=wrap.classList.toggle('collapsed');
  chevron.textContent=collapsed?'▼':'▲';
}});
document.getElementById('tbdToggle').addEventListener('click',()=>{{
  showTBD=!showTBD;
  document.getElementById('tbdToggle').classList.toggle('active',showTBD);
  document.getElementById('tbdToggle').textContent=showTBD?'Hide TBD':'Show TBD';
  applyFilters();
}});
document.querySelectorAll('table.drop-table thead th[data-col]').forEach(th=>{{
  th.addEventListener('click',()=>{{
    const col=+th.dataset.col;
    if(sortCol===col)sortDesc=!sortDesc;else{{sortCol=col;sortDesc=false;}}
    document.querySelectorAll('table.drop-table thead th').forEach(t=>t.classList.remove('sorted','desc'));
    th.classList.add('sorted');if(sortDesc)th.classList.add('desc');
    const rows=Array.from(document.getElementById('tbody').querySelectorAll('tr'));
    rows.sort((a,b)=>{{
      if(col===0){{const ad=+a.dataset.date||99999999,bd=+b.dataset.date||99999999;return sortDesc?bd-ad:ad-bd;}}
      const av=a.cells[col]?.textContent.trim()||'',bv=b.cells[col]?.textContent.trim()||'';
      return sortDesc?bv.localeCompare(av):av.localeCompare(bv);
    }}).forEach(r=>document.getElementById('tbody').appendChild(r));
    applyFilters();
  }});
}});

// ── ICS export ─────────────────────────────────────────────────────────────
function exportICS(day,time,alertMins,drops){{
  const CRLF=String.fromCharCode(13,10);
  const d0=drops[0];
  const toTitle=s=>s.replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  const dtStr=icsDate(YEAR_N,MONTH_N,day,time);
  const[sh,sm]=time.split(':').map(Number);
  const dtEnd=icsDate(YEAR_N,MONTH_N,day,pad((sh+1)%24)+':'+pad(sm));
  const uid='grailz-'+d0.name.slice(0,40)+'-'+YEAR_N+'-'+pad(MONTH_N)+'-'+pad(day)+'@grailzking.github.io';
  const[h,m]=time.split(':').map(Number);
  const ampm=h<12?'AM':'PM';const h12=h%12||12;
  const timeLabel=h12+':'+(m<10?'0':'')+m+' '+ampm+' CT';
  // Build title and description — handle grouped (multi-drop) entries
  let title,desc,link;
  if(drops.length===1){{
    // Single drop
    title=toTitle(d0.name)+' ['+d0.cat+']';
    link=d0.url1||'https://grailzking.github.io/grailz-drops';
    const descLines=['Drop: '+toTitle(d0.name),'Category: '+d0.cat,'Time: '+timeLabel,'Link: '+link];
    if(d0.url2)descLines.push('Source 2: '+d0.url2);
    descLines.push('');descLines.push('Grailz Drops Calendar: https://grailzking.github.io/grailz-drops');
    desc=descLines.join('\\n');
  }}else{{
    // Grouped drop — list all items
    title=toTitle(d0.name)+' + '+(drops.length-1)+' more ['+d0.cat+']';
    link=d0.url1||'https://grailzking.github.io/grailz-drops';
    const descLines=['Category: '+d0.cat,'Time: '+timeLabel,'','Items in this drop:'];
    drops.forEach((dr,i)=>{{
      descLines.push((i+1)+'. '+toTitle(dr.name));
      if(dr.url1)descLines.push('   Link: '+dr.url1);
      if(dr.url2)descLines.push('   Source 2: '+dr.url2);
    }});
    descLines.push('');descLines.push('Grailz Drops Calendar: https://grailzking.github.io/grailz-drops');
    desc=descLines.join('\\n');
  }}
  const ics=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Grailz//Drops Calendar//EN',
    'CALSCALE:GREGORIAN','METHOD:PUBLISH','BEGIN:VEVENT',
    'UID:'+uid,'DTSTAMP:'+icsDate(YEAR_N,MONTH_N,day,'00:00'),
    'DTSTART:'+dtStr,'DTEND:'+dtEnd,
    'SUMMARY:'+title,
    'DESCRIPTION:'+desc.replace(/\\n/g,'\\\\n'),
    'URL:'+link,
    'BEGIN:VALARM','ACTION:DISPLAY','DESCRIPTION:Grailz Drop: '+toTitle(d0.name).slice(0,60),
    'TRIGGER:-PT'+alertMins+'M','END:VALARM','END:VEVENT','END:VCALENDAR'].join(CRLF);
  const blob=new Blob([ics],{{type:'text/calendar;charset=utf-8'}});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;
  a.download='grailz-'+d0.name.slice(0,40)+'-'+YEAR_N+'-'+pad(MONTH_N)+'-'+pad(day)+'.ics';
  document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);
}}
// ── Boot ───────────────────────────────────────────────────────────────────
loadManifest();
</script>
</body>
</html>"""


# ── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n=== Grailz Drops Builder — {MONTH_NAME} ===\n")

    # 1. Scrape
    scraped = []
    scraped += scrape_topps()
    scraped += scrape_beckett_tcg()
    scraped += scrape_beckett_nonsports()
    scraped += scrape_social()

    # 2. Merge with manual
    all_drops = merge(MANUAL_DROPS, scraped)
    all_drops.sort(key=sort_key)
    print(f"\nTotal drops: {len(all_drops)} ({len(MANUAL_DROPS)} manual + {len(scraped)} scraped)")

    # 3. Write JSON data file
    print(f"\nWriting data files…")
    os.makedirs(DATA_DIR, exist_ok=True)
    json_path = os.path.join(DATA_DIR, f"{MONTH_KEY}.json")
    if not os.path.exists(json_path):
        write_json(all_drops, MONTH_KEY, MONTH_NAME)
        print(f"  Created {json_path}")
    else:
        # File exists — only update the manifest entry, never overwrite curated drop data
        manifest_path = os.path.join(DATA_DIR, "index.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as mf:
                manifest = json.load(mf)
            if not any(m["month_key"] == MONTH_KEY for m in manifest):
                manifest.append({"month": MONTH_NAME, "month_key": MONTH_KEY,
                                  "file": f"data/{MONTH_KEY}.json", "active": True})
                manifest.sort(key=lambda x: x["month_key"], reverse=True)
                with open(manifest_path, "w") as mf:
                    json.dump(manifest, mf, indent=2)
                print(f"  Manifest updated")
        print(f"  Skipped {json_path} (exists — managed manually)")

    # 4. Build HTML shell
    html = build_html(MONTH_KEY, MONTH_NAME)
    with open(OUTPUT_HTML, "w", encoding="utf-8", errors="replace") as f:
        f.write(html)
    print(f"Written → {OUTPUT_HTML} ({len(html):,} bytes)")
    print(f"\nDone. Push index.html + data/ to GitHub to deploy.\n")
