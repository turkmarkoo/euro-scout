#!/usr/bin/env python3
"""
EuroScout shot-chart scraper (hardened: checkpoint + auto-resume).

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

Robustness:
  * After every game it saves progress to raw/<id>_shots.progress.json AND
    rewrites raw/<id>_shots.txt, so an interruption (Ctrl-C, network drop,
    Cloudflare block) never loses work.
  * On restart it auto-resumes: already-fetched games are skipped. Just run the
    same command again to finish. Use --fresh to ignore any saved progress.
  * On a clean finish the .progress.json file is removed.
"""
import argparse, os, sys, time, math, json, signal

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


def write_txt(out_path, shots):
    with open(out_path, "w", encoding="utf-8") as f:
        for pc, zs in shots.items():
            parts = [f"{z}:{m}-{at}" for z, (m, at) in zs.items()]
            f.write(pc + "|" + "|".join(parts) + "\n")


def save_progress(prog_path, done, shots):
    tmp = prog_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(done), "shots": shots}, f)
    os.replace(tmp, prog_path)   # atomic — never leaves a half-written file


def load_progress(prog_path):
    if not os.path.exists(prog_path):
        return set(), {}
    try:
        d = json.load(open(prog_path, encoding="utf-8"))
        # JSON keys are strings; shot counts come back as lists already
        shots = {pc: {z: [int(v[0]), int(v[1])] for z, v in zs.items()}
                 for pc, zs in d.get("shots", {}).items()}
        return set(d.get("done", [])), shots
    except Exception:
        return set(), {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comp", required=True, help="competition code: E (EuroLeague), U (EuroCup)")
    ap.add_argument("--season", type=int, default=2025, help="season start year (2025 = 2025-26)")
    ap.add_argument("--id", required=True, help="league id used in build_all.py, e.g. euroleague")
    ap.add_argument("--delay", type=float, default=1.2, help="seconds between games (be polite)")
    ap.add_argument("--fresh", action="store_true", help="ignore saved progress and start over")
    ap.add_argument("--checkpoint", type=int, default=10, help="save progress every N games")
    a = ap.parse_args()
    seasoncode = f"{a.comp}{a.season}"
    os.makedirs(RAW, exist_ok=True)
    out = os.path.join(RAW, f"{a.id}_shots.txt")
    prog_path = os.path.join(RAW, f"{a.id}_shots.progress.json")

    codes = game_codes(a.comp, a.season)
    done, shots = (set(), {}) if a.fresh else load_progress(prog_path)
    remaining = [c for c in codes if c not in done]
    print(f"{a.id}: {len(codes)} games total"
          + (f" · resuming ({len(done)} already done, {len(remaining)} to go)" if done else ""))

    # flush cleanly on Ctrl-C
    def _flush(*_):
        save_progress(prog_path, done, shots)
        write_txt(out, shots)
        print(f"\ninterrupted — saved {len(done)} games / {len(shots)} players. "
              f"Re-run the same command to resume.")
        sys.exit(1)
    signal.signal(signal.SIGINT, _flush)

    t0 = time.time()
    for i, code in enumerate(remaining):
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
            print("  !! skipped game", code, "(will retry on next run)"); continue
        for row in j["Rows"]:
            act = row["ID_ACTION"].strip()
            if act not in ("2FGM", "2FGA", "3FGM", "3FGA"): continue
            three = act[0] == "3"; made = act.endswith("M")
            z = zone_of(row["COORD_X"], row["COORD_Y"], three)
            pc = row["ID_PLAYER"].strip().lstrip("P")
            e = shots.setdefault(pc, {}).setdefault(z, [0, 0])
            e[1] += 1
            if made: e[0] += 1
        done.add(code)

        if (i + 1) % a.checkpoint == 0:
            save_progress(prog_path, done, shots)
            write_txt(out, shots)
            rate = (i + 1) / max(1e-6, time.time() - t0)
            eta = (len(remaining) - i - 1) / max(1e-6, rate)
            print(f"  {len(done)}/{len(codes)} games · {len(shots)} players · ~{eta/60:.1f} min left")
        time.sleep(a.delay)

    # final write + clean up the progress file
    write_txt(out, shots)
    if os.path.exists(prog_path):
        os.remove(prog_path)
    print(f"done: {len(done)}/{len(codes)} games, {len(shots)} players -> {out}\n"
          f"Next: python build_all.py")


if __name__ == "__main__":
    main()
