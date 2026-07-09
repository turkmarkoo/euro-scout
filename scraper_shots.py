#!/usr/bin/env python3
"""
EuroScout shot-chart scraper.

Pulls EuroLeague/EuroCup shot data (the "Points" feed on live.euroleague.net),
classifies every field-goal attempt into court zones, aggregates per player, and
writes raw/<id>_shots.txt which build_all.py merges into each player's `shots`.

Works for any competition on the platform:
    E = EuroLeague, U = EuroCup  (future comps use their own code + season).

Usage:
    pip install -r requirements.txt
    python scraper_shots.py --comp E --season 2025 --id euroleague
    python scraper_shots.py --comp U --season 2025 --id eurocup
    python build_all.py           # rebuild data.json with shot charts

IMPORTANT: live.euroleague.net sits behind Cloudflare and rate-limits bursts.
This script goes ONE game at a time with a delay (default 1.2s) and retries, so
it stays under the limit. A full EuroLeague season (~400 games) takes ~10 min.
Run it from your own machine (not a shared/cloud IP) for best results.
"""
import argparse, os, sys, time, math

try:
    import requests
except ImportError:
    sys.exit("Run: pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
FEEDS = "https://feeds.incrowdsports.com/provider/euroleague-feeds"
LIVE = "https://live.euroleague.net/api/Points"
HDRS = {"User-Agent": "Mozilla/5.0 EuroScout/1.0",
        "Referer": "https://www.euroleaguebasketball.net/",
        "Accept": "application/json"}

def zone_of(x, y, three):
    d = math.hypot(x, y)
    if not three:
        if d <= 150: return "RIM"
        if abs(x) <= 245 and y <= 460: return "PAINT"
        return "MID_L" if x < -90 else ("MID_R" if x > 90 else "MID_C")
    if y <= 290: return "C3_L" if x < 0 else "C3_R"
    return "W3_L" if x < -210 else ("W3_R" if x > 210 else "TOP3")

def game_codes(comp, season):
    url = f"{FEEDS}/v2/competitions/{comp}/seasons/{comp}{season}/games?limit=600"
    data = requests.get(url, headers=HDRS, timeout=30).json()
    arr = data.get("data", data)
    return sorted(g["code"] for g in arr
                  if g.get("status") == "result" and g.get("home") and g["home"].get("score") is not None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comp", required=True, help="competition code: E (EuroLeague), U (EuroCup)")
    ap.add_argument("--season", type=int, default=2025, help="season start year (2025 = 2025-26)")
    ap.add_argument("--id", required=True, help="league id used in build_all.py, e.g. euroleague")
    ap.add_argument("--delay", type=float, default=1.2, help="seconds between games (be polite)")
    a = ap.parse_args()
    seasoncode = f"{a.comp}{a.season}"
    codes = game_codes(a.comp, a.season)
    print(f"{a.id}: {len(codes)} games")

    shots = {}   # pcode -> {zone: [made, att]}
    for i, code in enumerate(codes):
        # fetch_points expects full seasoncode
        j = None
        for t in range(4):
            try:
                r = requests.get(LIVE, params={"gamecode": code, "seasoncode": seasoncode},
                                 headers=HDRS, timeout=30)
                if r.status_code == 200 and r.text.startswith("{"):
                    j = r.json(); break
            except Exception:
                pass
            time.sleep(3 + 3 * t)
        if not j or "Rows" not in j:
            print("  !! skipped game", code); continue
        for row in j["Rows"]:
            act = row["ID_ACTION"].strip()
            if act not in ("2FGM", "2FGA", "3FGM", "3FGA"): continue
            three = act[0] == "3"; made = act.endswith("M")
            z = zone_of(row["COORD_X"], row["COORD_Y"], three)
            pc = row["ID_PLAYER"].strip().lstrip("P")
            e = shots.setdefault(pc, {}).setdefault(z, [0, 0])
            e[1] += 1
            if made: e[0] += 1
        if (i + 1) % 25 == 0: print(f"  {i+1}/{len(codes)} games, {len(shots)} players")
        time.sleep(a.delay)

    os.makedirs(RAW, exist_ok=True)
    out = os.path.join(RAW, f"{a.id}_shots.txt")
    with open(out, "w", encoding="utf-8") as f:
        for pc, zs in shots.items():
            parts = [f"{z}:{m}-{at}" for z, (m, at) in zs.items()]
            f.write(pc + "|" + "|".join(parts) + "\n")
    print(f"wrote {len(shots)} players -> {out}\nNext: python build_all.py")

if __name__ == "__main__":
    main()
