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
}

CAT_TIMES = {
    "FUNKO POP":"11:00","TOPPS":"12:00","PANINI":"12:00",
    "POKEMON TCG":"09:00","ONE PIECE TCG":"00:00","MTG":"00:00",
    "YU-GI-OH!":"00:00","DISNEY LORCANA":"09:00","NON-SPORTS CARDS":"12:00",
    "DISNEY PARKS PINS":"09:00","SUPREME FW26":"11:00","MATTEL CREATIONS":"09:00",
    "COLLAB / LIFESTYLE":"10:00","VINYL & MUSIC":"00:00","MOVIES":"00:00",
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
    ("TOPPS","8-17","2026-topps-museum-collection-baseball","https://www.topps.com/pages/topps-museum-collection-baseball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-18","2025-26-topps-definitive-basketball","https://www.topps.com/pages/topps-definitive-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-19","2026-topps-chrome-baseball-logofractor-edition","https://www.topps.com/pages/topps-chrome-baseball-logofractor-edition","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-19","2026-topps-mint-marvel","https://www.topps.com/pages/topps-mint-marvel","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-20","2025-26-topps-motif-basketball","https://www.topps.com/pages/topps-motif-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-27","2026-topps-chrome-black-basketball","https://www.topps.com/pages/topps-chrome-black-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-TBD","2026-topps-flagship-football","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("TOPPS","8-TBD","2026-skybox-metal-universe-space-jam-30th","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
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
    # ── NON-SPORTS CARDS ──────────────────────────────────────────────────
    ("NON-SPORTS CARDS","8-7","2026-leaf-seasons-in-the-sun-baseball","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-19","2025-26-upper-deck-clear-cut-hockey","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("NON-SPORTS CARDS","8-19","2026-upper-deck-cfl-football","https://www.checklistinsider.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-inspirations-world-of-dc","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-rittenhouse-star-trek-voyager","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-aew-wrestling","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-topps-chrome-sapphire-veefriends","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    # ── MATTEL CREATIONS ──────────────────────────────────────────────────
    ("MATTEL CREATIONS","8-TBD","mattel-creations-august-member-exclusive","https://creations.mattel.com/pages/launch-calendar","", "09:00"),
    ("MATTEL CREATIONS","8-TBD","hot-wheels-august-collector-exclusive","https://creations.mattel.com/pages/launch-calendar","", "09:00"),
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
    # ── DISNEY PARKS PINS ─────────────────────────────────────────────────
    ("DISNEY PARKS PINS","8-4","wdw-august-le-pin-week-1","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-11","wdw-august-le-pin-week-2","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-disney-pinnacle-booth","https://d23.com/d23-2026/","https://x.com/DisneyPinnacle/status/2081016173999862201", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-disney-princess-all-13-le-pin-1200","https://d23.com/d23-2026/","https://x.com/DPrincess_Facts/status/2081016173999862201", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-exclusive-pin-drops-weekend","https://d23.com/d23-2026/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-18","wdw-august-le-pin-week-3","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-25","wdw-august-le-pin-week-4","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-TBD","wdw-halloween-2026-pin-series-launch","https://disneypinsblog.com/halloween-2026-pin-releases-at-disney-store-disney-parks/","", "09:00"),
    # ── VINYL & MUSIC — pauseandplay.com ──────────────────────────────────
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
    ("VINYL & MUSIC","8-21","paul-simon-the-quiet-celebration-concert-triple-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-28","nickelback-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","nine-inch-nails-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","marilyn-manson-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-TBD","record-store-day-drops-2-2026","https://www.recordstoreday.com","", "00:00"),
    ("VINYL & MUSIC","8-TBD","august-limited-pressing-releases","https://www.plaidroomrecords.com/collections/pre-orders","", "00:00"),
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
header{{border-bottom:1px solid var(--border);padding:18px 40px;background:linear-gradient(135deg,#06060d 60%,#0e0a1a 100%);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;}}
.logo-wrap{{display:flex;align-items:center;gap:14px;}}
.logo-img{{width:52px;height:52px;border-radius:50%;filter:drop-shadow(0 0 10px #9b3fe8) drop-shadow(0 0 20px #1eb8f060);flex-shrink:0;}}
.logo{{font-family:'Space Mono',monospace;font-size:42px;font-weight:700;background:linear-gradient(90deg,#fff 0%,#c084fc 35%,#9b3fe8 60%,#1eb8f0 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:4px;line-height:1;filter:drop-shadow(0 0 18px #9b3fe870);}}
.subtitle{{font-size:12px;color:#8b6baa;letter-spacing:.16em;text-transform:uppercase;margin-top:6px;}}
.header-right{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
.month-select{{font-family:'Space Mono',monospace;font-size:11px;background:linear-gradient(135deg,#9b3fe820,#1eb8f020);border:1px solid #9b3fe860;color:#c084fc;padding:6px 12px;border-radius:20px;cursor:pointer;outline:none;}}
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
.day-drop-row{{display:flex;align-items:center;gap:10px;padding:10px 12px;background:#0a0a14;border-radius:6px;border:1px solid var(--border);margin-bottom:8px;flex-wrap:wrap;}}
.day-drop-row:last-of-type{{margin-bottom:0;}}
.day-drop-time{{font-family:'Space Mono',monospace;font-size:11px;color:var(--accent2);font-weight:700;white-space:nowrap;min-width:72px;}}
.day-drop-name{{font-size:12px;color:var(--text);flex:1;min-width:120px;}}
.day-srcs{{display:flex;gap:6px;flex-shrink:0;}}
.day-srcs a{{font-family:'Space Mono',monospace;font-size:9px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:2px 7px;border-radius:3px;}}
.divider{{max-width:1100px;margin:28px auto 0;padding:0 32px;display:flex;align-items:center;gap:12px;}}
.div-line{{flex:1;height:1px;background:var(--border);}}
.div-label{{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);white-space:nowrap;}}
.controls{{max-width:1100px;margin:16px auto 0;padding:0 32px;display:flex;flex-direction:column;gap:12px;}}
.search-wrap{{display:flex;align-items:center;gap:10px;}}
#search{{background:var(--surface);border:1px solid var(--border);color:var(--text);font-family:'Space Grotesk',sans-serif;font-size:14px;padding:9px 14px;border-radius:6px;width:280px;outline:none;}}
#search:focus{{border-color:var(--accent2);}}
#search::placeholder{{color:var(--muted);}}
.count{{font-size:12px;color:var(--muted);font-family:'Space Mono',monospace;}}
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
.time-cell{{font-family:'Space Mono',monospace;font-size:11px;color:#9b3fe8;white-space:nowrap;font-weight:600;}}
.name-cell{{font-size:13px;color:var(--text);max-width:380px;}}
.source-cell{{display:flex;gap:8px;flex-wrap:wrap;}}
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

<header>
  <div class="logo-wrap">
    {"<img src='" + logo_img_src + "' alt='Grailz' class='logo-img'>" if logo_img_src else ""}
    <div><div class="logo">GRAILZ</div><div class="subtitle">Collectibles Drop Calendar</div></div>
  </div>
  <div class="header-right">
    <select class="month-select" id="monthSelect"><option value="">Loading…</option></select>
  </div>
</header>

<div class="cal-section">
  <div class="cal-top">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
      <div class="cal-title" id="calHeading">Loading…</div>
      <div class="view-toggle">
        <button class="view-btn active" data-view="month">Month</button>
        <button class="view-btn" data-view="week">Week</button>
        <button class="view-btn" data-view="day">Day</button>
      </div>
    </div>
    <div class="cal-controls"></div>
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

<div class="divider"><div class="div-line"></div><div class="div-label">Full Drop List</div><div class="div-line"></div></div>

<div class="controls">
  <div class="search-wrap">
    <input id="search" type="text" placeholder="Search drops…" autocomplete="off">
    <span class="count" id="count"></span>
  </div>
  <div class="filters" id="filterBtns"></div>
</div>

<div class="table-wrap">
  <table class="drop-table">
    <thead><tr>
      <th data-col="0" class="sorted">Date</th>
      <th data-col="1">Time (ET)</th>
      <th data-col="2">Category</th>
      <th data-col="3">Drop</th>
      <th data-col="4">Sources</th>
      <th>Add</th>
    </tr></thead>
    <tbody id="tbody"></tbody>
  </table>
  <div class="no-results" id="noResults">No drops found.</div>
</div>

<footer>
  <span id="footerUpdated">Updated {today_str} · Grailz Discord Server</span>
  <span>topps.com · beckett.com · tcgradar.eu · disneypinsblog.com · funko.com + social</span>
</footer>

<script>
// ── Constants ─────────────────────────────────────────────────────────────
const CAT_MAP   = {cat_map_js};
const TODAY_DAY = {today_day};
const TODAY_MON = {today_month};
const TODAY_YR  = {today_year};

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
    // Load current/first month
    await loadMonth(manifest[0].month_key);
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
  document.getElementById('calHeading').textContent = MONTH_NAME;
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
        chip.title=dr.name;chip.textContent=dr.name;chips.appendChild(chip);
      }});
      if(dayDrops.length>3){{const m=document.createElement('div');m.className='cal-more';m.textContent='+'+(dayDrops.length-3)+' more';chips.appendChild(m);}}
      td.appendChild(chips);
      td.addEventListener('click',()=>openDayPanel(day,dayDrops,td));
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
        chip.style.marginBottom='2px';chip.title=dr.name;chip.textContent=dr.name;td.appendChild(chip);
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
    const dropId='dr-'+dayN+'-'+idx;
    let inner='';
    if(showTime) inner+=`<span class="day-drop-time">${{fmt12(dr.time||'09:00')}}</span>`;
    inner+=`<span class="cat-badge" style="background:${{bg}};color:#fff">${{dr.cat}}</span>`;
    inner+=`<span class="${{showTime?'day-drop-name':'panel-drop-name'}}">${{dr.name}}</span>`;
    inner+=`<span class="${{showTime?'day-srcs':'panel-srcs'}}">`;
    if(dr.url1)inner+=`<a href="${{dr.url1}}" target="_blank" rel="noopener">Source 1 ↗</a>`;
    if(dr.url2)inner+=`<a href="${{dr.url2}}" target="_blank" rel="noopener">Source 2 ↗</a>`;
    inner+='</span>';
    row.innerHTML=inner;
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
  document.getElementById('calHeading').textContent=
    v==='month'?MONTH_NAME:v==='week'?'Week View':'Day View';
}}
document.querySelectorAll('.view-btn').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
document.getElementById('weekPrev').addEventListener('click',()=>{{currentWeekStart.setDate(currentWeekStart.getDate()-7);buildWeekView();}});
document.getElementById('weekNext').addEventListener('click',()=>{{currentWeekStart.setDate(currentWeekStart.getDate()+7);buildWeekView();}});
document.getElementById('dayPrev').addEventListener('click',()=>{{currentDayDate.setDate(currentDayDate.getDate()-1);buildDayView();}});
document.getElementById('dayNext').addEventListener('click',()=>{{currentDayDate.setDate(currentDayDate.getDate()+1);buildDayView();}});

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
    tr.dataset.cat=sl;tr.dataset.date=dateSort;
    tr.innerHTML=`<td class="date-cell">${{dateDisplay}}</td><td class="time-cell">${{timeDisplay}}</td><td><span class="cat-badge cat-${{sl}}">${{d.cat}}</span></td><td class="name-cell">${{d.name}}</td><td class="source-cell">${{u1}}${{u1&&u2?' ':''}}${{u2}}</td><td class="ics-cell"><div class="tbl-cal-row"><input type="time" class="drop-time-input" id="t-${{dropId}}" value="${{dropTime}}" style="display:none"><input type="number" class="drop-alert-num" id="n-${{dropId}}" value="30" min="1" max="9999" style="display:none"><select class="drop-alert-unit" id="u-${{dropId}}" style="display:none"><option value="minutes">Min</option><option value="hours">Hrs</option><option value="days">Days</option></select><button class="btn-ics-sm" data-id="${{dropId}}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>Add</button></div></td>`;
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

let activeFilter='all',sortCol=0,sortDesc=false;
function applyFilters(){{
  const q=document.getElementById('search').value.toLowerCase();
  const rows=Array.from(document.getElementById('tbody').querySelectorAll('tr'));
  let any=false;
  rows.forEach(r=>{{
    const cm=activeFilter==='all'||r.dataset.cat===activeFilter;
    const tm=!q||r.textContent.toLowerCase().includes(q);
    r.classList.toggle('hidden',!(cm&&tm));
    if(cm&&tm)any=true;
  }});
  document.getElementById('noResults').style.display=any?'none':'block';
  const v=rows.filter(r=>!r.classList.contains('hidden')).length;
  document.getElementById('count').textContent=v+' drop'+(v!==1?'s':'');
}}
document.getElementById('search').addEventListener('input',applyFilters);
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
  const dt=new Date(YEAR_N,MONTH_N-1,day);
  const label=dt.toLocaleDateString('en-US',{{month:'long',day:'numeric',year:'numeric'}});
  const dtStr=icsDate(YEAR_N,MONTH_N,day,time);
  const[sh,sm]=time.split(':').map(Number);
  const dtEnd=icsDate(YEAR_N,MONTH_N,day,pad((sh+1)%24)+':'+pad(sm));
  const uid='grailz-'+YEAR_N+'-'+pad(MONTH_N)+'-'+pad(day)+'@grailzking.github.io';
  const desc=drops.map(d=>'['+d.cat+'] '+d.name+(d.url1?' \u2014 '+d.url1:'')).join('\\n');
  const names=drops.map(d=>d.name).join(', ');
  const ics=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Grailz//Drops Calendar//EN',
    'CALSCALE:GREGORIAN','METHOD:PUBLISH','BEGIN:VEVENT',
    'UID:'+uid,'DTSTAMP:'+icsDate(YEAR_N,MONTH_N,day,'00:00'),
    'DTSTART:'+dtStr,'DTEND:'+dtEnd,'SUMMARY:\uD83C\uDFAF Grailz Drop \u2014 '+label,
    'DESCRIPTION:'+desc.replace(/\\n/g,'\\\\n'),
    'BEGIN:VALARM','ACTION:DISPLAY','DESCRIPTION:Grailz Drop Reminder \u2014 '+names.slice(0,60),
    'TRIGGER:-PT'+alertMins+'M','END:VALARM','END:VEVENT','END:VCALENDAR'].join(CRLF);
  const blob=new Blob([ics],{{type:'text/calendar;charset=utf-8'}});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;
  a.download='grailz-drop-'+YEAR_N+'-'+pad(MONTH_N)+'-'+pad(day)+'.ics';
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
    write_json(all_drops, MONTH_KEY, MONTH_NAME)

    # 4. Build HTML shell
    html = build_html(MONTH_KEY, MONTH_NAME)
    with open(OUTPUT_HTML, "w", encoding="utf-8", errors="replace") as f:
        f.write(html)
    print(f"Written → {OUTPUT_HTML} ({len(html):,} bytes)")
    print(f"\nDone. Push index.html + data/ to GitHub to deploy.\n")
