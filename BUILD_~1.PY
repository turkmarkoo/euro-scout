#!/usr/bin/env python3
"""
EuroScout data builder.
Reads raw per-league player totals (pipe-delimited) + hard-coded team standings,
normalizes team names, aggregates players traded mid-season, computes per-game /
per-40 / shooting rates, and league percentiles + z-scores for the comparison
engine. Emits site/data/data.json consumed by the frontend.

Add a new league by dropping a raw file in scrapers/raw/ and registering it in
LEAGUES below (see README).
"""
import json, os, statistics, math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "..", "site", "data")

# ---- Canonical team registry: match_substrings -> (code, display, city, country) ----
EL_TEAMS = {
    "OLY": ("Olympiacos", "Piraeus", "Greece", ["olympiacos"]),
    "PAM": ("Valencia Basket", "Valencia", "Spain", ["valencia"]),
    "MAD": ("Real Madrid", "Madrid", "Spain", ["real madrid"]),
    "ULK": ("Fenerbahce Beko", "Istanbul", "Turkey", ["fenerbah"]),
    "ZAL": ("Zalgiris Kaunas", "Kaunas", "Lithuania", ["zalgiris", "algiris"]),
    "HTA": ("Hapoel Tel Aviv", "Tel Aviv", "Israel", ["hapoel"]),
    "PAN": ("Panathinaikos", "Athens", "Greece", ["panathinaikos"]),
    "MCO": ("AS Monaco", "Monaco", "France", ["monaco"]),
    "BAR": ("FC Barcelona", "Barcelona", "Spain", ["barcelona", "bar�", "barcelona b"]),
    "RED": ("Crvena Zvezda", "Belgrade", "Serbia", ["crvena", "zvezda", "red star"]),
    "DUB": ("Dubai Basketball", "Dubai", "UAE", ["dubai"]),
    "TEL": ("Maccabi Tel Aviv", "Tel Aviv", "Israel", ["maccabi"]),
    "MUN": ("Bayern Munich", "Munich", "Germany", ["bayern", "m�nchen", "munich"]),
    "MIL": ("EA7 Milan", "Milan", "Italy", ["armani", "milano", "ea7"]),
    "PAR": ("Partizan Belgrade", "Belgrade", "Serbia", ["partizan"]),
    "PRS": ("Paris Basketball", "Paris", "France", ["paris"]),
    "VIR": ("Virtus Bologna", "Bologna", "Italy", ["virtus", "bologna"]),
    "BAS": ("Baskonia", "Vitoria-Gasteiz", "Spain", ["baskonia"]),
    "IST": ("Anadolu Efes", "Istanbul", "Turkey", ["efes", "anadolu"]),
    "ASV": ("LDLC ASVEL", "Villeurbanne", "France", ["asvel"]),
}
# standings: code -> (rank, W, L, ptsFor, ptsAgainst) over 38 RS games
EL_STANDINGS = {
    "OLY": (1, 26, 12, 3406, 3144), "PAM": (2, 25, 13, 3418, 3243),
    "MAD": (3, 24, 14, 3342, 3156), "ULK": (4, 24, 14, 3114, 3061),
    "ZAL": (5, 23, 15, 3304, 3125), "HTA": (6, 23, 15, 3329, 3211),
    "PAN": (7, 22, 16, 3314, 3228), "MCO": (8, 22, 16, 3417, 3282),
    "BAR": (9, 21, 17, 3167, 3147), "RED": (10, 21, 17, 3287, 3245),
    "DUB": (11, 19, 19, 3324, 3325), "TEL": (12, 18, 20, 3386, 3486),
    "MUN": (13, 17, 21, 3063, 3168), "MIL": (14, 17, 21, 3246, 3294),
    "PAR": (15, 16, 22, 3052, 3242), "PRS": (16, 15, 23, 3422, 3456),
    "VIR": (17, 14, 24, 3110, 3285), "BAS": (18, 13, 25, 3321, 3483),
    "IST": (19, 12, 26, 2991, 3151), "ASV": (20, 8, 30, 2989, 3270),
}

LEAGUES = [
    {
        "id": "euroleague", "name": "EuroLeague", "season": "2025-26",
        "tier": "Continental (Tier 1)", "raw": "euroleague_2025_players.txt",
        "teams": EL_TEAMS, "standings": EL_STANDINGS, "rs_games": 38,
        "source": "Basketball-Reference / EuroLeague official feeds",
    },
    # To add a league, append a dict here and drop its raw file in raw/.
]

COLS = ["p","tm","g","mp","fg","fga","f3","f3a","ft","fta",
        "orb","drb","trb","ast","stl","blk","tov","pf","pts"]
NUMS = COLS[2:]

# Minimum thresholds to be "qualified" for percentiles / leaderboards
MIN_GAMES = 15
MIN_MPG = 10.0

def team_code(name, teams):
    n = name.lower()
    for code, (_disp, _city, _ctry, subs) in teams.items():
        for s in subs:
            if s and s in n:
                return code
    return None

def pct_rank(sorted_vals, v):
    # percentile 0-100 of v within sorted_vals (ascending)
    n = len(sorted_vals)
    if n <= 1:
        return 50.0
    below = sum(1 for x in sorted_vals if x < v)
    equal = sum(1 for x in sorted_vals if x == v)
    return round((below + 0.5 * equal) / n * 100, 1)

def build_league(cfg):
    path = os.path.join(RAW, cfg["raw"])
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) != len(COLS):
                continue
            rec = {"p": parts[0], "tm": parts[1]}
            for i, c in enumerate(NUMS):
                rec[c] = int(parts[i+2])
            rows.append(rec)

    # aggregate traded players (same exact name -> sum totals; keep team w/ most mp)
    agg = {}
    for r in rows:
        key = r["p"]
        if key not in agg:
            agg[key] = {"p": r["p"], "teams": {}, **{c: 0 for c in NUMS}}
        a = agg[key]
        for c in NUMS:
            a[c] += r[c]
        a["teams"][r["tm"]] = a["teams"].get(r["tm"], 0) + r["mp"]

    players = []
    for a in agg.values():
        primary_tm = max(a["teams"], key=a["teams"].get)
        code = team_code(primary_tm, cfg["teams"])
        multi = len([t for t in a["teams"] if a["teams"][t] > 0]) > 1
        g, mp = a["g"], a["mp"]
        if g == 0:
            continue
        def pg(x): return round(a[x] / g, 1)
        def per40(x): return round(a[x] / mp * 40, 1) if mp > 0 else 0.0
        fg, fga, f3, f3a, ft, fta = a["fg"], a["fga"], a["f3"], a["f3a"], a["ft"], a["fta"]
        fgp = round(fg / fga * 100, 1) if fga else 0.0
        f3p = round(f3 / f3a * 100, 1) if f3a else 0.0
        ftp = round(ft / fta * 100, 1) if fta else 0.0
        efg = round((fg + 0.5 * f3) / fga * 100, 1) if fga else 0.0
        tsa = fga + 0.44 * fta
        ts = round(a["pts"] / (2 * tsa) * 100, 1) if tsa else 0.0
        # NBA-style efficiency (approx of EuroLeague PIR; labeled EFF in UI)
        eff_total = (a["pts"] + a["trb"] + a["ast"] + a["stl"] + a["blk"]
                     - (fga - fg) - (fta - ft) - a["tov"])
        eff = round(eff_total / g, 1)
        usg_proxy = round((fga + 0.44 * fta + a["tov"]) / mp * 40, 1) if mp else 0.0
        # crude projected role from rate profile
        trb40, ast40, blk40 = per40("trb"), per40("ast"), per40("blk")
        if trb40 >= 8.5 or blk40 >= 1.2:
            role = "Big"
        elif ast40 >= 5.0:
            role = "Guard"
        else:
            role = "Wing"
        players.append({
            "id": f"{cfg['id']}-" + a["p"].lower().replace(" ", "-").replace(".", "").replace("'", ""),
            "name": a["p"], "team": code, "teamName": cfg["teams"][code][0] if code else primary_tm,
            "league": cfg["id"], "multiTeam": multi, "role": role,
            "g": g, "mpg": round(mp / g, 1), "min": mp,
            "ppg": pg("pts"), "rpg": pg("trb"), "apg": pg("ast"),
            "spg": pg("stl"), "bpg": pg("blk"), "topg": pg("tov"),
            "orpg": pg("orb"), "drpg": pg("drb"), "pfpg": pg("pf"),
            "fgp": fgp, "f3p": f3p, "ftp": ftp, "efg": efg, "ts": ts,
            "eff": eff,
            "f3ma": f"{f3}-{f3a}", "fgma": f"{fg}-{fga}", "ftma": f"{ft}-{fta}",
            "pts40": per40("pts"), "reb40": per40("trb"), "ast40": per40("ast"),
            "stl40": per40("stl"), "blk40": per40("blk"), "tov40": per40("tov"),
            "usg": usg_proxy,
            "qualified": g >= MIN_GAMES and (mp / g) >= MIN_MPG,
            "raw": {c: a[c] for c in NUMS},
        })

    # percentiles + z-scores across qualified players
    metrics = ["ppg","rpg","apg","spg","bpg","topg","fgp","f3p","ftp","efg","ts","eff",
               "pts40","reb40","ast40","stl40","blk40","usg","mpg"]
    qual = [p for p in players if p["qualified"]]
    stat_meta = {}
    for m in metrics:
        vals = sorted(p[m] for p in qual)
        mean = statistics.mean(vals) if vals else 0
        sd = statistics.pstdev(vals) if len(vals) > 1 else 1
        stat_meta[m] = {"mean": round(mean, 2), "sd": round(sd, 2),
                        "min": min(vals) if vals else 0, "max": max(vals) if vals else 0,
                        "n": len(vals)}
        for p in players:
            p.setdefault("pct", {})
            p.setdefault("z", {})
            p["pct"][m] = pct_rank(vals, p[m])
            p["z"][m] = round((p[m] - mean) / sd, 2) if sd else 0.0

    # teams
    teams = []
    for code, (disp, city, ctry, _subs) in cfg["teams"].items():
        rank, w, l, pf, pa = cfg["standings"][code]
        g = cfg["rs_games"]
        roster = sorted([p["name"] for p in players if p["team"] == code])
        teams.append({
            "code": code, "name": disp, "city": city, "country": ctry,
            "league": cfg["id"], "rank": rank, "w": w, "l": l,
            "winPct": round(w / (w + l) * 100, 1),
            "ppg": round(pf / g, 1), "oppg": round(pa / g, 1),
            "net": round((pf - pa) / g, 1),
            "rosterCount": len(roster),
        })

    return {
        "meta": {"id": cfg["id"], "name": cfg["name"], "season": cfg["season"],
                 "tier": cfg["tier"], "source": cfg["source"],
                 "minGames": MIN_GAMES, "minMpg": MIN_MPG,
                 "playerCount": len(players), "qualifiedCount": len(qual)},
        "statMeta": stat_meta,
        "teams": teams,
        "players": players,
    }

def main():
    os.makedirs(OUT, exist_ok=True)
    out = {"generated": "2026-07-08", "leagues": []}
    for cfg in LEAGUES:
        if not os.path.exists(os.path.join(RAW, cfg["raw"])):
            print("skip (no raw):", cfg["id"]); continue
        L = build_league(cfg)
        out["leagues"].append(L)
        print(f"{cfg['name']}: {L['meta']['playerCount']} players, "
              f"{L['meta']['qualifiedCount']} qualified, {len(L['teams'])} teams")
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
        f.write(payload)
    # inline fallback so index.html works when opened directly (file://) with no server
    with open(os.path.join(OUT, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.EUROSCOUT_INLINE=" + payload + ";")
    print("wrote data.json and data.js")

if __name__ == "__main__":
    main()
