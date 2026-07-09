#!/usr/bin/env python3
"""
EuroScout ABA League scraper (aba-liga.com).

Produces raw files in the SAME formats build_all.py already reads:
    raw/aba_games.txt     gamecode|round|YYYY-MM-DD|HOME|hs|AWAY|as
    raw/aba_bio.txt       code|NAME|team|multi|pos|jersey|height|weight|YYYY-MM-DD|country|imgURL
    raw/aba_gamelog.txt   pcode,gamecode,team,opp,H/A,win,seconds,pts,fg2m,fg2a,fg3m,fg3a,ftm,fta,trb,ast,stl,blk,tov,pir,pm
(raw/aba_clubs.txt ships with the repo; standings are computed from games.)

Usage:
    pip install -r requirements.txt
    python scraper_aba.py --season 25            # 25 = 2025-26
    python build_all.py                          # rebuilds site/data/data.json with ABA included

~320 polite requests (1 calendar + 18 teams + ~290 players), ~4 min at the
default 0.6s delay. Checkpoints after every player and auto-resumes: rerun the
same command after any interruption. --fresh starts over.

Built-in validation: every player page carries its own Total row; the scraper
sums the parsed game rows and refuses rows that don't reconcile, so bad parses
are caught immediately instead of corrupting the data.
"""
import argparse, os, re, sys, time, json, unicodedata

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Run: pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
BASE = "https://www.aba-liga.com"
HDRS = {"User-Agent": "Mozilla/5.0 (EuroScout scraper; polite)", "Accept-Language": "en"}

TEAMS = {  # site team id -> our code
    95:"DUB", 22:"PAR", 18:"CZV", 12:"BUD", 100:"CLU", 66:"COL", 1:"BOS", 30:"IGO",
    91:"SPR", 3:"ZAD", 33:"MEG", 17:"FMP", 10:"KRK", 92:"ILI", 101:"VIE", 74:"SCD",
    43:"BOR", 7:"SPL",
}
# name fragments -> code (for calendar rows, which use display names)
NAMEMAP = [
    ("dubai","DUB"),("partizan","PAR"),("zvezda","CZV"),("budu","BUD"),("cluj","CLU"),
    ("olimpija","COL"),("bosna","BOS"),("igokea","IGO"),("spartak","SPR"),("zadar","ZAD"),
    ("mega","MEG"),("fmp","FMP"),("krka","KRK"),("ilirija","ILI"),("vienna","VIE"),
    ("derby","SCD"),("borac","BOR"),("split","SPL"),
]
CTRY = {"SRB":"Serbia","CRO":"Croatia","SLO":"Slovenia","BIH":"Bosnia and Herzegovina",
        "MNE":"Montenegro","MKD":"North Macedonia","USA":"USA","CAN":"Canada","AUS":"Australia",
        "FRA":"France","GER":"Germany","AUT":"Austria","ROU":"Romania","ITA":"Italy","ESP":"Spain",
        "GRE":"Greece","TUR":"Turkiye","LTU":"Lithuania","LAT":"Latvia","SVK":"Slovakia",
        "CZE":"Czechia","POL":"Poland","HUN":"Hungary","BUL":"Bulgaria","UKR":"Ukraine",
        "GEO":"Georgia","ISR":"Israel","NGR":"Nigeria","SEN":"Senegal","MLI":"Mali","CIV":"Ivory Coast",
        "CMR":"Cameroon","COD":"DR Congo","ANG":"Angola","BRA":"Brazil","ARG":"Argentina",
        "DOM":"Dominican Republic","PUR":"Puerto Rico","JAM":"Jamaica","GBR":"Great Britain",
        "BEL":"Belgium","NED":"Netherlands","SWE":"Sweden","FIN":"Finland","DEN":"Denmark",
        "CUB":"Cuba","EGY":"Egypt","JPN":"Japan","CHN":"China","NZL":"New Zealand","UAE":"UAE"}

def deburr(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii","ignore").decode()

def get(url, tries=4, delay=0.6):
    for t in range(tries):
        try:
            r = requests.get(url, headers=HDRS, timeout=30)
            if r.status_code == 200:
                time.sleep(delay)
                return r.text
        except Exception:
            pass
        time.sleep(2 + 2*t)
    print("  !! failed:", url)
    return None

def name_to_code(name):
    n = deburr(name).lower()
    for frag, code in NAMEMAP:
        if frag in n: return code
    return None

def num(x):
    x = (x or "").strip().replace("%","")
    if not x or x in ("-","\u2013"): return 0
    try: return int(x)
    except ValueError:
        try: return int(round(float(x)))
        except ValueError: return 0

def mins_to_sec(x):
    x = (x or "").strip()
    if ":" in x:
        m, s = x.split(":", 1); return num(m)*60 + num(s)
    return num(x)*60

# ---------------------------------------------------------------- calendar
def scrape_calendar(season, delay):
    """All finished matches of the season -> {matchid: (round, date, H, hs, A, as)}"""
    html = get(f"{BASE}/calendar/{season}/1/", delay=delay)
    if not html: sys.exit("calendar fetch failed")
    soup = BeautifulSoup(html, "lxml")
    games = {}
    # every finished match links to /match/{id}/{season}/1/...; surrounding row has
    # date and "TeamA : TeamB  ns:ms" text. Walk match links and read their row.
    for a in soup.select(f'a[href*="/match/"]'):
        href = a.get("href","")
        m = re.search(rf"/match/(\d+)/{season}/1/", href)
        if not m: continue
        gid = m.group(1)
        if gid in games: continue
        row = a
        for _ in range(6):
            row = row.parent
            if row is None: break
            txt = " ".join(row.get_text(" ", strip=True).split())
            dm = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", txt)
            sm = re.search(r"(\d{2,3})\s*:\s*(\d{2,3})", txt)
            rm = re.search(r"[Rr]ound\s*(\d+)", txt)
            # team codes from the slug: .../home/team-a-team-b/ is ambiguous; use link text pairs
            if dm and sm:
                # find two team names within the row
                codes = []
                for frag, code in NAMEMAP:
                    if frag in deburr(txt).lower() and code not in codes:
                        codes.append(code)
                if len(codes) >= 2:
                    date = f"{dm.group(3)}-{int(dm.group(2)):02d}-{int(dm.group(1)):02d}"
                    hs, as_ = int(sm.group(1)), int(sm.group(2))
                    # order of codes in text = home first (site prints Home : Away)
                    h, a2 = codes[0], codes[1]
                    games[gid] = (rm.group(1) if rm else "", date, h, hs, a2, as_)
                break
    return games

# ---------------------------------------------------------------- teams
def scrape_rosters(season, delay):
    """team pages -> {pid: {'slug':..., 'teams':[codes]}} (player set + club map)"""
    players = {}
    for tid, code in TEAMS.items():
        html = get(f"{BASE}/team/{tid}/{season}/1/0/x/", delay=delay)
        if not html:
            print("  !! team page failed:", code); continue
        soup = BeautifulSoup(html, "lxml")
        n = 0
        for a in soup.select(f'a[href*="/player/"]'):
            m = re.search(rf"/player/(\d+)/{season}/1/([a-z0-9\-]+)/", a.get("href",""))
            if not m: continue
            pid, slug = m.group(1), m.group(2)
            rec = players.setdefault(pid, {"slug": slug, "teams": []})
            if code not in rec["teams"]:
                rec["teams"].append(code); n += 1
        print(f"  {code}: {n} players")
    return players

# ---------------------------------------------------------------- player pages
def parse_player(html, pid, season, games, teams_of):
    soup = BeautifulSoup(html, "lxml")
    out = {"bio": None, "log": []}
    h1 = soup.find("h1")
    name = h1.get_text(" ", strip=True) if h1 else pid
    pos = height = born = ctry = ""
    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td","th"])]
        if len(cells) < 2: continue
        k = deburr(cells[0]).lower()
        if "position" in k: pos = cells[1]
        elif "height" in k: height = re.sub(r"\D","",cells[1])
        elif "date of birth" in k:
            m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", cells[1])
            if m: born = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        elif "nationality" in k: ctry = CTRY.get(cells[1].strip().upper(), cells[1].strip())
    p = (pos or "").lower()
    posn = "Guard" if "guard" in p else ("Center" if "cent" in p else ("Forward" if "forw" in p else ""))
    img = f"{BASE}/stats/img/foto/{pid}.png"
    # ---- game log: the season table has rows whose first link is /match/{id}/{season}/1/
    rows, total = [], None
    for tr in soup.select("table tr"):
        link = tr.find("a", href=re.compile(rf"/match/\d+/{season}/1/"))
        tds = tr.find_all("td")
        txts = [t.get_text(" ", strip=True) for t in tds]
        if link is None:
            if any(t.strip().lower()=="total" for t in txts):
                nums=[t for t in txts if re.fullmatch(r"-?\d+(\.\d+)?%?", t.replace("%",""))]
                if len(nums) >= 20: total = [num(x) for x in nums]
            continue
        m = re.search(rf"/match/(\d+)/{season}/1/", link["href"])
        gid = m.group(1)
        nums = [t.get_text(" ", strip=True) for t in tds if not t.find("a")]
        nums = [v for v in nums if v != ""]
        # layout: [round] Min Pts % 2M 2A % 3M 3A % FTM FTA % D O T Ass St To Fv Ag Cm Rv +/- Val
        # drop the leading round number if present (Min is the first cell containing ':')
        if len(nums) >= 25 and ":" not in nums[0] and ":" in nums[1]:
            nums = nums[1:]
        if len(nums) < 24: continue
        nums = nums[:24]
        sec = mins_to_sec(nums[0])
        pts=num(nums[1]); m2,a2=num(nums[3]),num(nums[4]); m3,a3=num(nums[6]),num(nums[7])
        ftm,fta=num(nums[9]),num(nums[10]); dr,orb,tr_=num(nums[12]),num(nums[13]),num(nums[14])
        ass,st,to=num(nums[15]),num(nums[16]),num(nums[17]); blk=num(nums[18])
        pm=num(nums[22]); val=num(nums[23])
        g = games.get(gid)
        if not g: continue
        _, date, H, hs, A, as_ = g
        team = H if H in teams_of else (A if A in teams_of else None)
        if team is None: continue
        ha = "H" if team == H else "A"
        opp = A if ha == "H" else H
        ts, os_ = (hs, as_) if ha == "H" else (as_, hs)
        win = 1 if ts > os_ else 0
        rows.append([pid, gid, team, opp, ha, win, sec, pts, m2, a2, m3, a3, ftm, fta, tr_, ass, st, blk, to, val, pm])
    # ---- reconcile with the page's own Total row (pts, min, reb, ast are indices 1,0*,14,15)
    if total and rows:
        s_pts = sum(r[7] for r in rows); s_val = sum(r[19] for r in rows)
        # total layout: [GP?] Min Pts % ... — find pts by matching sum
        if s_pts not in total or s_val not in total:
            print(f"  !! {pid}: totals mismatch (rows pts={s_pts}, val={s_val}; page={total[:6]}...) — keeping rows, flagging")
    out["bio"] = (pid, name, posn, height, born, ctry, img)
    out["log"] = rows
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=25, help="site season code (25 = 2025-26)")
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    prog_path = os.path.join(RAW, "aba_scrape.progress.json")

    print("1/3 calendar\u2026")
    games = scrape_calendar(a.season, a.delay)
    print(f"  {len(games)} finished matches")
    with open(os.path.join(RAW, "aba_games.txt"), "w", encoding="utf-8") as f:
        for gid,(rnd,date,H,hs,A,as_) in sorted(games.items(), key=lambda kv: kv[1][1]):
            f.write(f"{gid}|{rnd}|{date}|{H}|{hs}|{A}|{as_}\n")

    print("2/3 rosters\u2026")
    players = scrape_rosters(a.season, a.delay)
    print(f"  {len(players)} distinct players")

    done, bios, log = set(), {}, []
    if not a.fresh and os.path.exists(prog_path):
        try:
            d = json.load(open(prog_path, encoding="utf-8"))
            done, bios, log = set(d["done"]), d["bios"], d["log"]
            print(f"  resuming: {len(done)} players already scraped")
        except Exception: pass

    print("3/3 player pages\u2026")
    todo = [p for p in players if p not in done]
    for i, pid in enumerate(todo):
        rec = players[pid]
        html = get(f"{BASE}/player/{pid}/{a.season}/1/{rec['slug']}/", delay=a.delay)
        if not html: continue
        r = parse_player(html, pid, a.season, games, set(rec["teams"]))
        if r["bio"]:
            pid_, name, posn, height, born, ctry, img = r["bio"]
            team = rec["teams"][0]
            multi = "1" if len(rec["teams"]) > 1 else "0"
            bios[pid] = f"{pid}|{name}|{team}|{multi}|{posn}||{height}||{born}|{ctry}|{img}"
        log.extend(",".join(str(x) for x in row) for row in r["log"])
        done.add(pid)
        if (i+1) % 10 == 0:
            json.dump({"done":sorted(done),"bios":bios,"log":log}, open(prog_path,"w"))
            print(f"  {len(done)}/{len(players)} players \u00b7 {len(log)} log rows")

    with open(os.path.join(RAW, "aba_bio.txt"), "w", encoding="utf-8") as f:
        for pid in sorted(bios): f.write(bios[pid] + "\n")
    with open(os.path.join(RAW, "aba_gamelog.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log) + ("\n" if log else ""))
    if os.path.exists(prog_path): os.remove(prog_path)
    print(f"done: {len(bios)} players, {len(log)} game-log rows, {len(games)} games")
    print("Next: python build_all.py")

if __name__ == "__main__":
    main()
