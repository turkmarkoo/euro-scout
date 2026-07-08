#!/usr/bin/env python3
"""
EuroScout scraper — Basketball-Reference international leagues.

Basketball-Reference hosts season pages for all four leagues you asked about:
    EuroLeague   -> slug "euroleague"
    Liga ACB     -> slug "liga-acb"        (Spain)
    Lega A       -> slug "lega-basket-serie-a"  (Italy)
    ABA League   -> slug "aba-league"       (Adriatic)
(Verify a slug by opening https://www.basketball-reference.com/international/<slug>/ .)

For a given league + season year it downloads the per-player TOTALS table and
writes it in the pipe-delimited format build_data.py expects
(raw/<id>_players.txt). It also prints the standings so you can paste team
records into build_data.py's LEAGUES config.

Usage:
    pip install -r requirements.txt
    python scraper_bbref.py --slug euroleague --year 2026 --id euroleague
    python scraper_bbref.py --slug liga-acb   --year 2026 --id liga-acb

Notes:
  * "year" is the season END year (2025-26 season = 2026).
  * Run this on your own machine. Be polite: one request at a time, and cache
    the HTML rather than re-fetching. Respect Basketball-Reference's terms.
  * The EuroLeague raw file shipped with this project was produced exactly this
    way, so the numbers match what you already see in the app.
"""
import argparse, os, sys, time, json

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing deps. Run: pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
BASE = "https://www.basketball-reference.com/international"
UA = {"User-Agent": "EuroScout/1.0 (personal scouting project)"}

COLS = ["g","mp","fg","fga","fg3","fg3a","ft","fta","orb","drb","trb",
        "ast","stl","blk","tov","pf","pts"]   # data-stat names on BBRef

def fetch(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    time.sleep(3)  # be gentle
    return r.text

def cell(row, stat):
    c = row.find(attrs={"data-stat": stat})
    return c.get_text(strip=True) if c else ""

def scrape_players(slug, year, out_id):
    url = f"{BASE}/{slug}/{year}_totals.html"
    print("GET", url)
    soup = BeautifulSoup(fetch(url), "lxml")
    table = soup.find("table", id="stats") or soup.find("table", class_="stats_table")
    if not table:
        sys.exit("No player table found — check the slug/year.")
    lines = []
    for tr in table.select("tbody tr"):
        if "thead" in (tr.get("class") or []):
            continue
        name = cell(tr, "player")
        if not name or name == "Player":
            continue
        team = cell(tr, "team_name") or cell(tr, "team_id") or cell(tr, "team")
        vals = [cell(tr, c) or "0" for c in COLS]
        lines.append("|".join([name, team] + vals))
    os.makedirs(RAW, exist_ok=True)
    out = os.path.join(RAW, f"{out_id}_players.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} players -> {out}")

def scrape_standings(slug, year):
    url = f"{BASE}/{slug}/{year}.html"
    print("GET", url)
    soup = BeautifulSoup(fetch(url), "lxml")
    table = soup.find("table")  # first standings table
    print("\n--- Standings (paste records into build_data.py) ---")
    for tr in table.select("tbody tr"):
        name = cell(tr, "team") or (tr.find("th").get_text(strip=True) if tr.find("th") else "")
        w, l = cell(tr, "wins") or cell(tr, "W"), cell(tr, "losses") or cell(tr, "L")
        if name:
            print(f"  {name}: {w}-{l}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="BBRef league slug, e.g. euroleague")
    ap.add_argument("--year", required=True, type=int, help="season end year, e.g. 2026")
    ap.add_argument("--id", required=True, help="league id used in build_data.py, e.g. euroleague")
    ap.add_argument("--standings", action="store_true", help="also print standings")
    a = ap.parse_args()
    scrape_players(a.slug, a.year, a.id)
    if a.standings:
        try: scrape_standings(a.slug, a.year)
        except Exception as e: print("standings scrape failed:", e)
    print("\nNext: register the league in build_data.py LEAGUES, then run "
          "`python build_data.py` to rebuild site/data/data.json.")

if __name__ == "__main__":
    main()
