#!/usr/bin/env python3
"""
EuroScout scraper — OFFICIAL EuroLeague feeds (euroleaguebasketball.net).

Produces the three raw files that build_euroleague.py turns into the site data:
  raw/euroleague_bio.txt      player bios + headshots
  raw/euroleague_games.txt    schedule/results
  raw/euroleague_gamelog.txt  every player's per-game box score line

Data comes from the same public feeds the official site uses:
  people   : {FEEDS}/v2/competitions/E/seasons/E{YEAR}/people?personType=J
  games    : {FEEDS}/v2/competitions/E/seasons/E{YEAR}/games
  boxscore : {FEEDS}/v2/competitions/E/seasons/E{YEAR}/games/{code}/stats
where FEEDS = https://feeds.incrowdsports.com/provider/euroleague-feeds

Usage:
  pip install -r requirements.txt
  python scraper_euroleague.py --season 2025     # 2025-26 season
Then: python build_euroleague.py   (rebuilds site/data/data.json)

Notes:
  * Run on your own machine. It makes ~400 requests (one per game) with a small
    delay — be polite. Re-run to refresh as the season progresses.
  * timePlayed comes in seconds; build converts to minutes.
  * These are unofficial/undocumented endpoints used by the public website. They
    can change without notice; treat this as a best-effort community scraper and
    respect EuroLeague's terms of use.
"""
import argparse, os, sys, time, re

try:
    import requests
except ImportError:
    sys.exit("Run: pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
FEEDS = "https://feeds.incrowdsports.com/provider/euroleague-feeds"
HDRS = {"User-Agent": "EuroScout/1.0", "Accept": "application/json",
        "Origin": "https://www.euroleaguebasketball.net",
        "Referer": "https://www.euroleaguebasketball.net/"}

def get(url, **params):
    r = requests.get(url, params=params, headers=HDRS, timeout=30)
    r.raise_for_status()
    return r.json()

def short_img(u):
    if not u: return ""
    m = re.search(r"([0-9a-f-]{36})", u, re.I)
    if not m: return ""
    return ("c" if "cortextech" in u else "i") + m.group(1)

def secs(v):
    if isinstance(v, (int, float)): return int(v)
    if isinstance(v, str) and ":" in v:
        p = v.split(":"); return int(p[0]) * 60 + int(p[1])
    try: return int(v)
    except Exception: return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025, help="season start year (2025 = 2025-26)")
    ap.add_argument("--delay", type=float, default=0.3, help="seconds between game requests")
    a = ap.parse_args()
    base = f"{FEEDS}/v2/competitions/E/seasons/E{a.season}"
    os.makedirs(RAW, exist_ok=True)

    # 1) people -> bios/images/positions
    print("Fetching people…")
    people = get(f"{base}/people", personType="J", limit=600)
    pmap = {}
    for pp in (people.get("data") or people):
        per = pp.get("person") or {}
        img = (pp.get("images") or {}).get("headshot") or (pp.get("images") or {}).get("action") or ""
        pmap[per.get("code")] = dict(
            pos=pp.get("positionName") or "", jersey=pp.get("dorsal") or "",
            img=short_img(img), ht=per.get("height") or "", wt=per.get("weight") or "",
            bd=(per.get("birthDate") or "")[:10], ctry=(per.get("country") or {}).get("name") or "",
            name=per.get("name") or "")

    # 2) games -> schedule map
    print("Fetching games…")
    gl = get(f"{base}/games", limit=500)
    games = {}
    for g in (gl.get("data") or gl):
        if not (g.get("home") and g.get("away") and g["home"].get("score") is not None): continue
        if g.get("status") != "result": continue
        games[g["code"]] = dict(rnd=(g.get("round") or {}).get("round", ""),
                                date=(g.get("date") or "")[:10],
                                h=g["home"]["code"], hs=g["home"]["score"],
                                a=g["away"]["code"], as_=g["away"]["score"])

    with open(os.path.join(RAW, "euroleague_games.txt"), "w", encoding="utf-8") as f:
        for code, g in sorted(games.items()):
            f.write(f"{code}|{g['rnd']}|{g['date']}|{g['h']}|{g['hs']}|{g['a']}|{g['as_']}\n")

    # 3) per-game box scores -> game logs + bios (fallback from box score persons)
    print(f"Fetching {len(games)} box scores…")
    players = {}   # code -> dict(name, ht, wt, bd, ctry, teamcounts, rows[])
    def add(side_players, team, opp, ha, win, code):
        for L in side_players:
            per = (L.get("player") or {}).get("person"); s = L.get("stats")
            if not per or not s: continue
            if secs(s.get("timePlayed", 0)) <= 0 and not s.get("points") and not s.get("totalRebounds") and not s.get("assistances"):
                continue
            c = per["code"]
            P = players.setdefault(c, dict(name=per.get("name", c), ht=per.get("height", ""),
                    wt=per.get("weight", ""), bd=(per.get("birthDate") or "")[:10],
                    ctry=(per.get("country") or {}).get("name", ""), tc={}, rows=[]))
            P["tc"][team] = P["tc"].get(team, 0) + 1
            P["rows"].append([code, team, opp, ha, win, secs(s.get("timePlayed", 0)),
                s.get("points", 0), s.get("fieldGoalsMade2", 0), s.get("fieldGoalsAttempted2", 0),
                s.get("fieldGoalsMade3", 0), s.get("fieldGoalsAttempted3", 0),
                s.get("freeThrowsMade", 0), s.get("freeThrowsAttempted", 0),
                s.get("totalRebounds", 0), s.get("assistances", 0), s.get("steals", 0),
                s.get("blocksFavour", 0), s.get("turnovers", 0), s.get("valuation", 0),
                s.get("plusMinus", 0)])

    for i, code in enumerate(sorted(games)):
        g = games[code]
        try:
            js = get(f"{base}/games/{code}/stats")
        except Exception as e:
            print("  skip game", code, e); continue
        if not js.get("local") or not js.get("road"): continue
        hw = 1 if g["hs"] > g["as_"] else 0
        add(js["local"]["players"], g["h"], g["a"], "H", hw, code)
        add(js["road"]["players"], g["a"], g["h"], "A", 1 - hw, code)
        if (i + 1) % 50 == 0: print(f"  {i+1}/{len(games)}")
        time.sleep(a.delay)

    # write bios (people feed first, fall back to box-score person)
    with open(os.path.join(RAW, "euroleague_bio.txt"), "w", encoding="utf-8") as f:
        for c, P in players.items():
            m = pmap.get(c, {})
            team = max(P["tc"], key=P["tc"].get)
            multi = 1 if len([t for t in P["tc"] if P["tc"][t] > 0]) > 1 else 0
            f.write("|".join(str(x) for x in [c, m.get("name") or P["name"], team, multi,
                m.get("pos", ""), m.get("jersey", ""), m.get("ht") or P["ht"],
                m.get("wt") or P["wt"], m.get("bd") or P["bd"], m.get("ctry") or P["ctry"],
                m.get("img", "")]) + "\n")

    # write game logs
    n = 0
    with open(os.path.join(RAW, "euroleague_gamelog.txt"), "w", encoding="utf-8") as f:
        for c, P in players.items():
            for r in P["rows"]:
                f.write(c + "," + ",".join(str(x) for x in r) + "\n"); n += 1
    # note: gamelog row = pcode,gameCode,team,opp,ha,win,sec,pts,fg2m,fg2a,fg3m,fg3a,ftm,fta,trb,ast,stl,blk,tov,pir,pm
    print(f"Done. players={len(players)} bios written, gamelog rows={n}, games={len(games)}")
    print("Next: python build_euroleague.py")

if __name__ == "__main__":
    main()
