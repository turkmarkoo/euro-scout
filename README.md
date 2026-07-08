# EuroScout — European basketball scouting

A scouting site for professional European leagues, in the spirit of your Hoop Scout
site but built for multi-league player comparison and written scouting reports.

**What it does**

- Sortable, filterable stat tables for every player in a league (per-game and per-40).
- A **player profile** for each player with percentile bars vs the league, a
  statistical-profile radar, and full shooting splits.
- A **scouting report** editor on every profile: free-text notes, a 1–5 star grade,
  and tags — saved to the cloud (or this browser) and tied to your sign-in.
- **Compare** any two players side by side (head-to-head table + overlaid radar).
- A personal **Big Board** (your ranking, reorderable) and a **Watchlist**.
- **Teams** standings and a **Glossary** of every metric.

**What's loaded right now:** the complete, real **EuroLeague 2025-26** season —
all 20 teams and 334 players. Numbers come from official EuroLeague feeds /
Basketball-Reference and were validated against the season's stat leaders
(Vezenkov scoring, Miller-McIntyre assists, Milutinov rebounds, etc.).

Liga ACB (Spain), Lega A (Italy) and ABA/Adriatic are wired into the data model
and can be added with the included scraper (see *Add a league* below).

---

## Folder layout

```
euroscout/
├─ site/                     the website (this is what you host)
│  ├─ index.html             the whole app (single file)
│  ├─ config.js              your Supabase keys go here (optional)
│  └─ data/
│     ├─ data.json           generated data the site reads
│     └─ data.js             same data inlined (lets index.html open with no server)
├─ scrapers/
│  ├─ scraper_bbref.py       pull a league's stats -> raw/<id>_players.txt
│  ├─ build_data.py          turn raw files into site/data/data.json
│  ├─ requirements.txt
│  └─ raw/                   raw per-league stat files (source of truth)
├─ supabase_setup.sql        one-time cloud backend setup
└─ README.md
```

---

## Run it locally

The quickest way — just open it:

- Double-click `site/index.html`. It loads `data/data.js` and works with no server.

The proper way (recommended, needed for sign-in/magic links to redirect cleanly):

```bash
cd euroscout/site
python3 -m http.server 8000
# then open http://localhost:8000
```

Until you add Supabase keys, the app runs in **Local mode**: reports, ratings,
watchlist and big board are saved in that browser via `localStorage`.

---

## Cloud backend (so reports sync across devices) — recommended setup

Your reports become device-independent and tied to your login.

1. Create a free project at <https://supabase.com>.
2. In the project: **SQL Editor → New query**, paste the contents of
   `supabase_setup.sql`, and **Run**. (Creates the `scouting` table with
   row-level security so each user sees only their own data.)
3. In **Project Settings → API**, copy the **Project URL** and the **anon public**
   key.
4. Paste both into `site/config.js`:
   ```js
   window.EUROSCOUT_CONFIG = {
     SUPABASE_URL: "https://YOURPROJECT.supabase.co",
     SUPABASE_ANON_KEY: "eyJhbGc...your anon key...",
   };
   ```
5. Reload the site → click **Sign in** → enter your email → open the magic link.

That's it. The app upserts to Supabase and keeps a local cache, so it stays fast
and still works offline.

---

## Where to host it (my recommendation)

Because the site is static files + a hosted database, the cheapest and simplest
setup is:

- **Frontend:** GitHub Pages (same as your current Hoop Scout site) or Netlify —
  both free. Just publish the `site/` folder. On GitHub Pages, push `site/` to a
  repo and enable Pages; on Netlify, drag-and-drop the `site/` folder.
- **Backend:** Supabase free tier (the step above).

Netlify is slightly friendlier for the magic-link redirect, but GitHub Pages is
perfectly fine and matches what you already use. Either way, **put your real
Supabase keys only in the deployed `config.js`** — the anon key is safe to expose
(row-level security protects the data), but keep the *service* key private (never
needed by this app).

---

## Add a league

The workflow mirrors exactly how the EuroLeague data here was produced:

1. **Get the data.** Basketball-Reference hosts all four leagues you wanted:
   ```bash
   cd euroscout/scrapers
   pip install -r requirements.txt
   python scraper_bbref.py --slug liga-acb --year 2026 --id liga-acb --standings
   ```
   This writes `raw/liga-acb_players.txt` and prints the standings.
   (Slugs: `euroleague`, `liga-acb`, `lega-basket-serie-a`, `aba-league` — confirm
   each at basketball-reference.com/international/.)

   If you'd rather scrape a league's **own** website, just produce a file in the
   same pipe format — one line per player:
   `Name|Team|G|MP|FG|FGA|3P|3PA|FT|FTA|ORB|DRB|TRB|AST|STL|BLK|TOV|PF|PTS`

2. **Register it** in `build_data.py` → the `LEAGUES` list: add a dict with the
   league `id`, `name`, `season`, a `teams` registry (team-name → code/city/country)
   and its `standings`. Copy the EuroLeague block as a template.

3. **Rebuild:**
   ```bash
   python build_data.py
   ```
   This regenerates `site/data/data.json` (+ `data.js`) with per-game, per-40,
   percentiles and z-scores for every league.

4. **Redeploy** the `site/` folder. The league picker (top-right) shows it
   automatically.

---

## How comparison works

- **Percentiles** rank a player against *qualified* players in their league
  (default: ≥15 games and ≥10 mpg — tunable in `build_data.py`).
- **Per-40** stats normalize for playing time so bench and starter roles compare
  fairly.
- **Z-scores** (standard deviations from league average) are computed per league.
  They're the basis for **cross-league** comparison: a +2.0 scorer in one league
  vs another is comparable even when raw scoring levels differ. The Compare view
  overlays per-40 percentile radars today; once you load a second league, the
  z-scores make like-for-like cross-league reads meaningful. League strength still
  differs, so treat cross-league numbers as a guide, not gospel.

## Notes & caveats

- `EFF` is a quick all-round value metric (points + rebounds + assists + steals +
  blocks − missed shots − turnovers). It *approximates* the official EuroLeague
  PIR but isn't identical — PIR also adds fouls drawn and subtracts fouls and
  blocks-against, which aren't in this dataset. See the in-app Glossary.
- Players who changed teams mid-season are shown once with combined totals and a
  **2TM** badge.
- "Projected role" (Guard/Wing/Big) is inferred from each player's rate profile,
  not from an official position list — handy for filtering, not definitive.
