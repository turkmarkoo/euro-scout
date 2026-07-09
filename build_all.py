#!/usr/bin/env python3
"""
EuroScout builder — ALL competitions (EuroLeague + EuroCup).

Reads the official-feed raw files for each competition and emits one
site/data/data.json (+ data.js) containing every league. Players who appear in
BOTH competitions share the same person `code`, so the site can offer a
competition toggle on their profile.

Raw files per competition (produced by scraper_euroleague.py, competition E/U):
  raw/<id>_bio.txt      code|NAME|team|multi|position|jersey|height|weight|birth|country|imgflag+uuid
  raw/<id>_games.txt    gameCode|round|date|home|homeScore|away|awayScore
  raw/<id>_gamelog.txt  pcode,gameCode,team,opp,H/A,win,timeSec,pts,fg2m,fg2a,fg3m,fg3a,ftm,fta,trb,ast,stl,blk,tov,pir,pm
EuroCup also uses raw/eurocup_clubs.txt (code~name~country~city).
"""
import json, os, statistics
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "..", "site", "data")
TODAY = date(2026, 7, 9)
MIN_GAMES, MIN_MPG = 15, 10.0

EL_TEAMS = {
    "OLY": ("Olympiacos","Piraeus","Greece"), "PAM": ("Valencia Basket","Valencia","Spain"),
    "MAD": ("Real Madrid","Madrid","Spain"), "ULK": ("Fenerbahce Beko","Istanbul","Turkey"),
    "ZAL": ("Zalgiris Kaunas","Kaunas","Lithuania"), "HTA": ("Hapoel Tel Aviv","Tel Aviv","Israel"),
    "PAN": ("Panathinaikos","Athens","Greece"), "MCO": ("AS Monaco","Monaco","France"),
    "BAR": ("FC Barcelona","Barcelona","Spain"), "RED": ("Crvena Zvezda","Belgrade","Serbia"),
    "DUB": ("Dubai Basketball","Dubai","UAE"), "TEL": ("Maccabi Tel Aviv","Tel Aviv","Israel"),
    "MUN": ("Bayern Munich","Munich","Germany"), "MIL": ("EA7 Milan","Milan","Italy"),
    "PAR": ("Partizan Belgrade","Belgrade","Serbia"), "PRS": ("Paris Basketball","Paris","France"),
    "VIR": ("Virtus Bologna","Bologna","Italy"), "BAS": ("Baskonia","Vitoria-Gasteiz","Spain"),
    "IST": ("Anadolu Efes","Istanbul","Turkey"), "ASV": ("LDLC ASVEL","Villeurbanne","France"),
}
EL_STANDINGS = {
    "OLY":(1,26,12,3406,3144),"PAM":(2,25,13,3418,3243),"MAD":(3,24,14,3342,3156),
    "ULK":(4,24,14,3114,3061),"ZAL":(5,23,15,3304,3125),"HTA":(6,23,15,3329,3211),
    "PAN":(7,22,16,3314,3228),"MCO":(8,22,16,3417,3282),"BAR":(9,21,17,3167,3147),
    "RED":(10,21,17,3287,3245),"DUB":(11,19,19,3324,3325),"TEL":(12,18,20,3386,3486),
    "MUN":(13,17,21,3063,3168),"MIL":(14,17,21,3246,3294),"PAR":(15,16,22,3052,3242),
    "PRS":(16,15,23,3422,3456),"VIR":(17,14,24,3110,3285),"BAS":(18,13,25,3321,3483),
    "IST":(19,12,26,2991,3151),"ASV":(20,8,30,2989,3270),
}

LEAGUES = [
    dict(id="euroleague", name="EuroLeague", season="2025-26", tier="Continental (Tier 1)",
         rs_games=38, teams=EL_TEAMS, standings=EL_STANDINGS),
    dict(id="eurocup", name="EuroCup", season="2025-26", tier="Continental (Tier 2)",
         rs_games=18, teams=None, standings=None, standings_file="eurocup_standings.txt"),
]

def capword(w): return "-".join(p.capitalize() for p in w.split("-"))
def titlecase(raw):
    raw = raw.strip()
    surname, first = (raw.split(",",1)+[""])[:2] if "," in raw else (raw,"")
    return " ".join((" ".join(capword(w) for w in first.split()).strip()+" "+
                     " ".join(capword(w) for w in surname.split()).strip()).split())
def img_url(fu):
    if not fu or len(fu)<2: return ""
    host="cortextech.io" if fu[0]=="c" else "incrowdsports.com"
    return f"https://media-cdn.{host}/{fu[1:]}.png"
def age_from(b):
    try:
        y,m,d=map(int,b.split("-")); return TODAY.year-y-((TODAY.month,TODAY.day)<(m,d))
    except Exception: return None
def pct_rank(sv,v):
    n=len(sv)
    if n<=1: return 50.0
    below=sum(1 for x in sv if x<v); eq=sum(1 for x in sv if x==v)
    return round((below+0.5*eq)/n*100,1)

def load_clubs(fn):
    teams={}
    p=os.path.join(RAW,fn)
    if not os.path.exists(p): return teams
    for line in open(p,encoding="utf-8"):
        f=line.strip().split("~")
        if len(f)>=3: teams[f[0]]=(f[1],(f[3] if len(f)>3 else ""),f[2])
    return teams

def standings_from_games(games):
    rec={}
    for g in games.values():
        for code,ps,pa,win in [(g["h"],g["hs"],g["as"],g["hs"]>g["as"]),
                                (g["a"],g["as"],g["hs"],g["as"]>g["hs"])]:
            r=rec.setdefault(code,[0,0,0,0])
            r[0]+= 1 if win else 0; r[1]+= 0 if win else 1; r[2]+=ps; r[3]+=pa
    out={}
    ranked=sorted(rec.items(), key=lambda kv:(-(kv[1][0]/max(1,kv[1][0]+kv[1][1])), -(kv[1][2]-kv[1][3])))
    for i,(code,(w,l,pf,pa)) in enumerate(ranked):
        out[code]=(i+1,w,l,pf,pa)
    return out

def build_league(cfg):
    lid=cfg["id"]
    games={}
    for line in open(os.path.join(RAW,f"{lid}_games.txt"),encoding="utf-8"):
        p=line.strip().split("|")
        if len(p)!=7: continue
        games[p[0]]={"rnd":p[1],"date":p[2],"h":p[3],"hs":int(p[4]),"a":p[5],"as":int(p[6])}
    bios={}
    for line in open(os.path.join(RAW,f"{lid}_bio.txt"),encoding="utf-8"):
        p=line.rstrip("\n").split("|")
        if len(p)!=11: continue
        bios[p[0]]=dict(name=titlecase(p[1]),team=p[2],multi=p[3]=="1",pos=p[4],jersey=p[5],
                        ht=p[6],wt=p[7],bd=p[8],ctry=p[9],img=img_url(p[10]))
    logs={}
    for line in open(os.path.join(RAW,f"{lid}_gamelog.txt"),encoding="utf-8"):
        f=line.strip().split(",")
        if len(f)!=21: continue
        logs.setdefault(f[0],[]).append(f)

    teams_reg = cfg["teams"] or load_clubs("eurocup_clubs.txt")
    groups = {}
    if cfg.get("standings_file"):
        standings = {}
        for line in open(os.path.join(RAW, cfg["standings_file"]), encoding="utf-8"):
            f = line.strip().split("|")
            if len(f) != 7: continue
            grp, rank, code, w, l, pf, pa = f
            standings[code] = (int(rank), int(w), int(l), int(pf), int(pa))
            groups[code] = grp
    elif cfg["standings"]:
        standings = cfg["standings"]
    else:
        standings = standings_from_games(games)
    rs_g = cfg["rs_games"]
    ROLE={"Guard":"Guard","Forward":"Wing","Center":"Big"}
    keys=["team","opp","ha","win","sec","pts","fg2m","fg2a","fg3m","fg3a","ftm","fta",
          "trb","ast","stl","blk","tov","pir","pm"]
    players=[]
    for pc,rows in logs.items():
        b=bios.get(pc,{"name":pc,"team":rows[0][2],"multi":False,"pos":"","jersey":"",
                       "ht":"","wt":"","bd":"","ctry":"","img":""})
        T={k:0 for k in ["sec","pts","fg2m","fg2a","fg3m","fg3a","ftm","fta","trb","ast","stl","blk","tov","pir"]}
        glog=[]
        for f in rows:
            d=dict(zip(keys,f[2:]))
            for k in T: T[k]+=int(d[k])
            g=games.get(f[1],{})
            ts=g.get("hs" if d["ha"]=="H" else "as",0); os_=g.get("as" if d["ha"]=="H" else "hs",0)
            fgm=int(d["fg2m"])+int(d["fg3m"]); fga=int(d["fg2a"])+int(d["fg3a"])
            glog.append([g.get("date",""),d["opp"],d["ha"],int(d["win"]),ts,os_,round(int(d["sec"])/60,1),
                int(d["pts"]),fgm,fga,int(d["fg3m"]),int(d["fg3a"]),int(d["ftm"]),int(d["fta"]),
                int(d["trb"]),int(d["ast"]),int(d["stl"]),int(d["blk"]),int(d["tov"]),int(d["pir"]),int(d["pm"])])
        glog.sort(key=lambda r:r[0])
        G=len(rows); mp=T["sec"]/60.0; team=b["team"]
        fgm=T["fg2m"]+T["fg3m"]; fga=T["fg2a"]+T["fg3a"]
        pg=lambda x:round(x/G,1); p40=lambda x:round(x/mp*40,1) if mp else 0.0
        tsa=fga+0.44*T["fta"]
        players.append({
            "id":f"{lid}-{pc}","code":pc,"name":b["name"],"team":team,
            "teamName":teams_reg.get(team,(team,"",""))[0],"league":lid,"multiTeam":b["multi"],
            "role":ROLE.get(b["pos"],"Wing"),"pos":b["pos"] or "-","jersey":b["jersey"],
            "height":int(b["ht"]) if b["ht"].isdigit() else None,
            "weight":int(b["wt"]) if b["wt"].isdigit() else None,
            "age":age_from(b["bd"]),"country":b["ctry"],"img":b["img"],
            "g":G,"mpg":round(mp/G,1),"min":round(mp),
            "ppg":pg(T["pts"]),"rpg":pg(T["trb"]),"apg":pg(T["ast"]),"spg":pg(T["stl"]),
            "bpg":pg(T["blk"]),"topg":pg(T["tov"]),
            "fgp":round(fgm/fga*100,1) if fga else 0.0,
            "f3p":round(T["fg3m"]/T["fg3a"]*100,1) if T["fg3a"] else 0.0,
            "ftp":round(T["ftm"]/T["fta"]*100,1) if T["fta"] else 0.0,
            "efg":round((fgm+0.5*T["fg3m"])/fga*100,1) if fga else 0.0,
            "ts":round(T["pts"]/(2*tsa)*100,1) if tsa else 0.0,
            "pir":pg(T["pir"]),"eff":pg(T["pir"]),
            "fgma":f"{fgm}-{fga}","f3ma":f"{T['fg3m']}-{T['fg3a']}","ftma":f"{T['ftm']}-{T['fta']}",
            "pts40":p40(T["pts"]),"reb40":p40(T["trb"]),"ast40":p40(T["ast"]),
            "stl40":p40(T["stl"]),"blk40":p40(T["blk"]),"tov40":p40(T["tov"]),
            "usg":round((fga+0.44*T["fta"]+T["tov"])/mp*40,1) if mp else 0.0,
            "qualified":G>=MIN_GAMES and (mp/G)>=MIN_MPG,"gameLog":glog,
        })

    sp=os.path.join(RAW,f"{lid}_shots.txt")
    if os.path.exists(sp):
        smap={}
        for line in open(sp,encoding="utf-8"):
            parts=line.strip().split("|")
            if len(parts)<2: continue
            z={}
            for seg in parts[1:]:
                if ":" not in seg or "-" not in seg: continue
                zone,ma=seg.split(":",1); m,at=ma.split("-",1)
                try: z[zone]=[int(m),int(at)]
                except: pass
            if z: smap[parts[0]]=z
        n=0
        for p in players:
            if p["code"] in smap: p["shots"]=smap[p["code"]]; n+=1
        print(f"  {lid}: merged shots for {n} players")
    metrics=["ppg","rpg","apg","spg","bpg","topg","fgp","f3p","ftp","efg","ts","pir","eff",
             "pts40","reb40","ast40","stl40","blk40","usg","mpg"]
    qual=[p for p in players if p["qualified"]]
    stat_meta={}
    for m in metrics:
        vals=sorted(p[m] for p in qual)
        mean=statistics.mean(vals) if vals else 0
        sd=statistics.pstdev(vals) if len(vals)>1 else 1
        stat_meta[m]={"mean":round(mean,2),"sd":round(sd,2),"min":min(vals) if vals else 0,
                      "max":max(vals) if vals else 0,"n":len(vals)}
        for p in players:
            p.setdefault("pct",{}); p.setdefault("z",{})
            p["pct"][m]=pct_rank(vals,p[m]); p["z"][m]=round((p[m]-mean)/sd,2) if sd else 0.0

    teams=[]
    for code,(disp,city,ctry) in teams_reg.items():
        if code not in standings: continue
        rank,w,l,pf,pa=standings[code]; g=w+l
        teams.append({"code":code,"name":disp,"city":city,"country":ctry,"league":lid,"rank":rank,
                      "group":groups.get(code,""),
                      "w":w,"l":l,"winPct":round(w/g*100,1) if g else 0,
                      "ppg":round(pf/g,1) if g else 0,"oppg":round(pa/g,1) if g else 0,
                      "net":round((pf-pa)/g,1) if g else 0,
                      "rosterCount":sum(1 for p in players if p["team"]==code)})
    teams.sort(key=lambda t:(t.get("group",""),t["rank"]))
    return {"meta":{"id":lid,"name":cfg["name"],"season":cfg["season"],"tier":cfg["tier"],
                    "source":"EuroLeague official feeds (euroleaguebasketball.net)",
                    "minGames":MIN_GAMES,"minMpg":MIN_MPG,"playerCount":len(players),
                    "qualifiedCount":len(qual),
                    "gameLogCols":["date","opp","ha","win","teamPts","oppPts","min","pts","fgm","fga",
                                   "fg3m","fg3a","ftm","fta","reb","ast","stl","blk","tov","pir","pm"]},
            "statMeta":stat_meta,"teams":teams,"players":players}

def main():
    leagues=[build_league(c) for c in LEAGUES]
    # cross-competition index: person code -> competitions
    idx={}
    for L in leagues:
        for p in L["players"]:
            idx.setdefault(p["code"],[]).append({"league":L["meta"]["id"],"id":p["id"],
                                                 "name":L["meta"]["name"]})
    dual=sum(1 for c,v in idx.items() if len(v)>1)
    out={"generated":TODAY.isoformat(),"leagues":leagues,
         "crossPlayers":{c:v for c,v in idx.items() if len(v)>1}}
    os.makedirs(OUT,exist_ok=True)
    payload=json.dumps(out,ensure_ascii=False,separators=(",",":"))
    open(os.path.join(OUT,"data.json"),"w",encoding="utf-8").write(payload)
    open(os.path.join(OUT,"data.js"),"w",encoding="utf-8").write("window.EUROSCOUT_INLINE="+payload+";")
    for L in leagues:
        print(f"{L['meta']['name']}: {L['meta']['playerCount']} players, {L['meta']['qualifiedCount']} qual, "
              f"{len(L['teams'])} teams, {sum(len(p['gameLog']) for p in L['players'])} gamelog rows")
    print(f"dual-competition players: {dual}")
    print("wrote data.json + data.js")

if __name__ == "__main__":
    main()
