# Blind Bag Radar

Live page: https://grailzking.github.io/grailz-drops/blind-bag-radar/

Tracks the Santa Cruz x Pokémon TCG blind bag deck (item 11117698) across 100 US skate shops.

- `shops.json` is the shop list (name, state, site, deck page, manual status, known product URL). Edit it to add or remove shops.
- `check_stock.py` checks each Shopify shop's product listing and writes `status.json`. It only rewrites the file when a result changes or once an hour.
- `.github/workflows/blind-bag-radar.yml` runs the checker every 15 minutes. For an instant check, open **Actions → Blind Bag Radar stock check → Run workflow**.
- The page's **Refresh** button reloads `status.json`; the page also refreshes itself every 5 minutes while open.

Run it locally: `python blind-bag-radar/check_stock.py`
