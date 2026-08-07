# Grailz Drops Calendar

Monthly collectibles drop tracker for the Grailz Discord server. Auto-published to GitHub Pages every Monday.

## 🔗 Live Site
### **[grailzking.github.io/grailz-drops](https://grailzking.github.io/grailz-drops)**

---

## What's Tracked
- Funko Pop (Limited Edition, SDCC, Fan Rewards, Hot Topic, EE exclusives)
- Pokémon TCG
- One Piece TCG
- Magic: The Gathering
- Yu-Gi-Oh!
- Disney Lorcana
- Topps (Baseball, Basketball, Football, UFC, Marvel, WWE, Soccer)
- Panini
- Non-Sports Cards (Marvel, Star Wars, DC, Entertainment)
- Disney Parks Pins (WDW & DLR weekly LE releases, D23 events)
- Mattel Creations (Hot Wheels, Barbie, MOTU)
- Supreme FW/SS drops
- Collabs & Lifestyle

## How It Works
Each month `drops_data.py` is run — it scrapes all configured sources, merges with the curated manual drops list, builds a fresh `index.html`, and pushes it here. GitHub Pages serves it instantly.

The site has:
- Category filter buttons
- Live search
- Sortable columns (click any header)
- Mobile-friendly layout

## Sources
**Web:** topps.com/release-calendar · beckett.com · tcgradar.eu · icv2.com · disneypinsblog.com · funko.com · creations.mattel.com · supremecommunity.com · hypebeast.com

**Social (X/Twitter):** @Topps · @ONEPIECE_tcg_EN · @wizards_magic · @OriginalFunko · @PokemonRestocks · @DisneyPinsBlog · @DisneyPinnacle · @OPTCGAlert · @Gamegenic_ · @YuGiOh_TCG · @DisneyLorcana · @PaniniAmerica · @MattelCreations

## Auto-Deploy
The GitHub Action runs every **Monday at 9am CT** and on any push to `main`. It calls `drops_data.py`, rebuilds `index.html`, commits, and deploys. Pages goes live in ~60 seconds.

To update manually:
```bash
python drops_data.py   # rebuilds index.html
git add index.html
git commit -m "Update drops — Month YYYY"
git push
```

## Setup (first time)
1. Fork or clone this repo
2. Go to **Settings → Pages → Source → Deploy from branch → main / root**
3. Go to **Actions → Enable Actions**
4. Done — live at `https://grailzking.github.io/grailz-drops/`

---
*Grailz Discord · Not affiliated with any brands listed.*
