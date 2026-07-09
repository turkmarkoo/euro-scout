#!/usr/bin/env python3
"""
EuroScout builder — official EuroLeague feed edition.

Reads three raw files produced from the official EuroLeague data feeds:
  raw/euroleague_bio.txt      code|NAME|team|multi|position|jersey|height|weight|birth|country|imgflag+uuid
  raw/euroleague_games.txt    gameCode|round|date|home|homeScore|away|awayScore
  raw/euroleague_gamelog.txt  pcode,gameCode,team,opp,H/A,win,timeSec,pts,fg2m,fg2a,fg3m,fg3a,ftm,fta,trb,ast,stl,blk,tov,pir,pm

Emits site/data/data.json (+ data.js) with, for every player: official season
stats (incl. real PIR/valuation), bio + headshot, and a full per-game game log.
"""
import json, os, statistics
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "..", "site", "data")
TODAY = date(2026, 7, 9)

TEAMS = {  # code: (display, city, country)
    "OLY": ("Olympiacos", "Piraeus", "Greece"), "PAM": ("Valencia Basket", "Valencia", "Spain"),
    "MAD": ("Real Madrid", "Madrid", "Spain"), "ULK": ("Fenerbahce Beko", "Istanbul", "Turkey"),
    "ZAL": ("Zalgiris Kaunas", "Kaunas", "Lithuania"), "HTA": ("Hapoel Tel Aviv", "Tel Aviv", "Israel"),
    "PAN": ("Panathinaikos", "Athens", "Greece"), "MCO": ("AS Monaco", "Monaco", "France"),
    "BAR": ("FC Barcelona", "Barcelona", "Spain"), "RED": ("Crvena Zvezda", "Belgrade", "Serbia"),
    "DUB": ("Dubai Basketball", "Dubai", "UAE"), "TEL": ("Maccabi Tel Aviv", "Tel Aviv", "Israel"),
    "MUN": ("Bayern Munich", "Munich", "Germany"), "MIL": ("EA7 Milan", "Milan", "Italy"),
    "PAR": ("Partizan Belgrade", "Belgrade", "Serbia"), "PRS": ("Paris Basketball", "Paris", "France"),
    "VIR": ("Virtus Bologna", "Bologna", "Italy"), "BAS": ("Baskonia", "Vitoria-Gasteiz", "Spain"),
    "IST": ("Anadolu Efes", "Istanbul", "Turkey"), "ASV": ("LDLC ASVEL", "Villeurbanne", "France"),
}
STANDINGS = {  # code: (rank,W,L,ptsFor,ptsAgainst) — 38-game regular season (api-live)
    "OLY": (1,26,12,3406,3144), "PAM": (2,25,13,3418,3243), "MAD": (3,24,14,3342,3156),
    "ULK": (4,24,14,3114,3061), "ZAL": (5,23,15,3304,3125), "HTA": (6,23,15,3329,3211),
    "PAN": (7,22,16,3314,3228), "MCO": (8,22,16,3417,3282), "BAR": (9,21,17,3167,3147),
    "RED": (10,21,17,3287,3245), "DUB": (11,19,19,3324,3325), "TEL": (12,18,20,3386,3486),
    "MUN": (13,17,21,3063,3168), "MIL": (14,17,21,3246,3294), "PAR": (15,16,22,3052,3242),
    "PRS": (16,15,23,3422,3456), "VIR": (17,14,24,3110,3285), "BAS": (18,13,25,3321,3483),
    "IST": (19,12,26,2991,3151), "ASV": (20,8,30,2989,3270),
}
MIN_GAMES, MIN_MPG = 15, 10.0

def titlecase_name(raw):
    raw = raw.strip()
    if "," in raw:
        surname, first = raw.split(",", 1)
    else:
        surname, first = raw, ""
    def capword(w):
        return "-".join(part.capitalize() for part in w.split("-"))
    def tc(s):
        return " ".join(capword(w) for w in s.split())
    full = (tc(first).strip() + " " + tc(surname).strip()).strip()
    return " ".join(full.split())

def img_url(flag_uuid):
    if not flag_uuid or len(flag_uuid) < 2:
        return ""
    host = "cortextech.io" if flag_uuid[0] == "c" else "incrowdsports.com"
    return f"https://media-cdn.{host}/{flag_uuid[1:]}.png"

def age_from(birth):
    try:
        y, m, d = map(int, birth.split("-"))
        a = TODAY.year - y - ((TODAY.month, TODAY.day) < (m, d))
        return a
    except Exception:
        return None

def pct_rank(sorted_vals, v):
    n = len(sorted_vals)
    if n <= 1: return 50.0
    below = sum(1 for x in sorted_vals if x < v)
    equal = sum(1 for x in sorted_vals if x == v)
    return round((below + 0.5*equal)/n*100, 1)

def main():
    # games map
    games = {}
    for line in open(os.path.join(RAW, "euroleague_games.txt"), encoding="utf-8"):
        p = line.strip().split("|")
        if len(p) != 7: continue
        code, rnd, dt, h, hs, a, as_ = p
        games[code] = {"rnd": rnd, "date": dt, "h": h, "hs": int(hs), "a": a, "as": int(as_)}

    # bios
    bios = {}
    for line in open(os.path.join(RAW, "euroleague_bio.txt"), encoding="utf-8"):
        p = line.rstrip("\n").split("|")
        if len(p) != 11: continue
        code, name, team, multi, pos, jersey, ht, wt, bd, ctry, img = p
        bios[code] = {"name": titlecase_name(name), "team": team, "multi": multi == "1",
                      "pos": pos, "jersey": jersey, "ht": ht, "wt": wt, "bd": bd,
                      "ctry": ctry, "img": img_url(img)}

    # game logs grouped by player
    logs = {}
    for line in open(os.path.join(RAW, "euroleague_gamelog.txt"), encoding="utf-8"):
        f = line.strip().split(",")
        if len(f) != 21: continue
        pc = f[0]
        logs.setdefault(pc, []).append(f)

    ROLE = {"Guard": "Guard", "Forward": "Wing", "Center": "Big"}
    players = []
    for pc, rows in logs.items():
        b = bios.get(pc, {"name": pc, "team": rows[0][2], "multi": False, "pos": "",
                          "jersey": "", "ht": "", "wt": "", "bd": "", "ctry": "", "img": ""})
        # season totals from game rows
        T = dict(sec=0, pts=0, fg2m=0, fg2a=0, fg3m=0, fg3a=0, ftm=0, fta=0,
                 trb=0, ast=0, stl=0, blk=0, tov=0, pir=0)
        keys = ["team","opp","ha","win","sec","pts","fg2m","fg2a","fg3m","fg3a","ftm","fta",
                "trb","ast","stl","blk","tov","pir","pm"]  # f[2..20]
        glog = []
        for f in rows:
            d = dict(zip(keys, f[2:]))
            for k in ["sec","pts","fg2m","fg2a","fg3m","fg3a","ftm","fta","trb","ast","stl","blk","tov","pir"]:
                T[k] += int(d[k])
            g = games.get(f[1], {})
            teamscore = g.get("hs" if d["ha"] == "H" else "as", 0)
            oppscore = g.get("as" if d["ha"] == "H" else "hs", 0)
            fgm = int(d["fg2m"]) + int(d["fg3m"]); fga = int(d["fg2a"]) + int(d["fg3a"])
            glog.append([g.get("date",""), d["opp"], d["ha"], int(d["win"]),
                         teamscore, oppscore, round(int(d["sec"])/60,1), int(d["pts"]),
                         fgm, fga, int(d["fg3m"]), int(d["fg3a"]), int(d["ftm"]), int(d["fta"]),
                         int(d["trb"]), int(d["ast"]), int(d["stl"]), int(d["blk"]),
                         int(d["tov"]), int(d["pir"]), int(d["pm"])])
        glog.sort(key=lambda r: r[0])
        G = len(rows); mp = T["sec"]/60.0
        team = b["team"]
        fgm = T["fg2m"]+T["fg3m"]; fga = T["fg2a"]+T["fg3a"]
        def pg(x): return round(x/G, 1)
        def p40(x): return round(x/mp*40, 1) if mp else 0.0
        fgp = round(fgm/fga*100,1) if fga else 0.0
        f3p = round(T["fg3m"]/T["fg3a"]*100,1) if T["fg3a"] else 0.0
        ftp = round(T["ftm"]/T["fta"]*100,1) if T["fta"] else 0.0
        efg = round((fgm+0.5*T["fg3m"])/fga*100,1) if fga else 0.0
        tsa = fga + 0.44*T["fta"]
        ts = round(T["pts"]/(2*tsa)*100,1) if tsa else 0.0
        age = age_from(b["bd"])
        players.append({
            "id": f"euroleague-{pc}", "code": pc, "name": b["name"],
            "team": team, "teamName": TEAMS.get(team,(team,"",""))[0],
            "league": "euroleague", "multiTeam": b["multi"],
            "role": ROLE.get(b["pos"], "Wing"), "pos": b["pos"] or "-",
            "jersey": b["jersey"], "height": int(b["ht"]) if b["ht"].isdigit() else None,
            "weight": int(b["wt"]) if b["wt"].isdigit() else None,
            "age": age, "country": b["ctry"], "img": b["img"],
            "g": G, "mpg": round(mp/G,1), "min": round(mp),
            "ppg": pg(T["pts"]), "rpg": pg(T["trb"]), "apg": pg(T["ast"]),
            "spg": pg(T["stl"]), "bpg": pg(T["blk"]), "topg": pg(T["tov"]),
            "fgp": fgp, "f3p": f3p, "ftp": ftp, "efg": efg, "ts": ts,
            "pir": pg(T["pir"]), "eff": pg(T["pir"]),
            "fgma": f"{fgm}-{fga}", "f3ma": f"{T['fg3m']}-{T['fg3a']}", "ftma": f"{T['ftm']}-{T['fta']}",
            "pts40": p40(T["pts"]), "reb40": p40(T["trb"]), "ast40": p40(T["ast"]),
            "stl40": p40(T["stl"]), "blk40": p40(T["blk"]), "tov40": p40(T["tov"]),
            "usg": round((fga+0.44*T["fta"]+T["tov"])/mp*40,1) if mp else 0.0,
            "qualified": G >= MIN_GAMES and (mp/G) >= MIN_MPG,
            "gameLog": glog,
        })

    # percentiles + z
    metrics = ["ppg","rpg","apg","spg","bpg","topg","fgp","f3p","ftp","efg","ts","pir","eff",
               "pts40","reb40","ast40","stl40","blk40","usg","mpg"]
    qual = [p for p in players if p["qualified"]]
    stat_meta = {}
    for m in metrics:
        vals = sorted(p[m] for p in qual)
        mean = statistics.mean(vals) if vals else 0
        sd = statistics.pstdev(vals) if len(vals) > 1 else 1
        stat_meta[m] = {"mean": round(mean,2), "sd": round(sd,2),
                        "min": min(vals) if vals else 0, "max": max(vals) if vals else 0, "n": len(vals)}
        for p in players:
            p.setdefault("pct", {}); p.setdefault("z", {})
            p["pct"][m] = pct_rank(vals, p[m])
            p["z"][m] = round((p[m]-mean)/sd, 2) if sd else 0.0

    teams = []
    for code, (disp, city, ctry) in TEAMS.items():
        rank,w,l,pf,pa = STANDINGS[code]; g=38
        teams.append({"code":code,"name":disp,"city":city,"country":ctry,"league":"euroleague",
                      "rank":rank,"w":w,"l":l,"winPct":round(w/(w+l)*100,1),
                      "ppg":round(pf/g,1),"oppg":round(pa/g,1),"net":round((pf-pa)/g,1),
                      "rosterCount":sum(1 for p in players if p["team"]==code)})

    out = {"generated": TODAY.isoformat(), "leagues": [{
        "meta": {"id":"euroleague","name":"EuroLeague","season":"2025-26",
                 "tier":"Continental (Tier 1)","source":"EuroLeague official feeds (euroleaguebasketball.net)",
                 "minGames":MIN_GAMES,"minMpg":MIN_MPG,
                 "playerCount":len(players),"qualifiedCount":len(qual),
                 "gameLogCols":["date","opp","ha","win","teamPts","oppPts","min","pts","fgm","fga",
                                "fg3m","fg3a","ftm","fta","reb","ast","stl","blk","tov","pir","pm"]},
        "statMeta": stat_meta, "teams": teams, "players": players,
    }]}
    os.makedirs(OUT, exist_ok=True)
    payload = json.dumps(out, ensure_ascii=False, separators=(",",":"))
    open(os.path.join(OUT,"data.json"),"w",encoding="utf-8").write(payload)
    open(os.path.join(OUT,"data.js"),"w",encoding="utf-8").write("window.EUROSCOUT_INLINE="+payload+";")
    print(f"players {len(players)} qualified {len(qual)} gameLogRows {sum(len(p['gameLog']) for p in players)}")
    print("wrote data.json + data.js")

if __name__ == "__main__":
    main()
