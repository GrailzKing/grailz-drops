# Blind Bag Radar

Live page: https://grailzking.github.io/grailz-drops/blind-bag-radar/

Tracks the Santa Cruz x Pokémon TCG blind bag deck (item 11117698) across 100 US skate shops.

- `shops.json` is the shop list (name, state, site, deck page, manual status, known product URL). Edit it to add or remove shops.
- `check_stock.py` checks each Shopify shop's product listing and writes `status.json` every run.
- `.github/workflows/blind-bag-radar.yml` runs in ~5-hour shifts that check every 15 minutes, then starts the next shift itself. A cron every 2 hours restarts the chain if it stops. To stop checks: **Actions → Blind Bag Radar stock check → Disable workflow** (cancelling a run also ends the chain).
- The page's **Refresh** button reloads `status.json` and checks every shop with a known product page live from the browser. The page also refreshes itself every 5 minutes while open.

Run it locally: `python blind-bag-radar/check_stock.py`
