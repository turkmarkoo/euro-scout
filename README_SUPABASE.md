# EuroScout — Supabase setup (email login + roles + shared data)

This turns EuroScout into a private, multi-user app: **email magic-link sign-in**, an
**allowlist** of approved emails, **roles** (editor = full edit, viewer = read-only),
and **one shared scouting dataset** so your director sees your work. The whole app is
gated — nothing loads until an approved user signs in.

You do this once. I can't create the project for you (it's tied to your account), but
every step below is dashboard clicks + one SQL paste.

## 1. Create the project
1. Go to https://supabase.com → **New project** (free tier is fine). Pick a name + region.
2. When it's ready: **Project Settings → API**. Copy the **Project URL** and the
   **anon / publishable key**. (The anon key is safe to commit — security comes from RLS.)

## 2. Paste the keys into `config.js`
```js
window.EUROSCOUT_CONFIG = {
  SUPABASE_URL: "https://xxxxxxxx.supabase.co",
  SUPABASE_ANON_KEY: "eyJhbGci...your anon key...",
};
```
Re-upload `config.js` with a fresh `?v=` like usual. As soon as these are set, EuroScout
switches from local mode to the gated shared backend.

## 3. Auth settings
1. **Authentication → Providers → Email**: make sure it's enabled (magic link is on by default).
2. **Authentication → URL Configuration**:
   - **Site URL**: `https://turkmarkoo.github.io/euro-scout/`
   - **Redirect URLs**: add `https://turkmarkoo.github.io/euro-scout/`
   (The sign-in link sends people back here already logged in.)
3. (Optional but nice) **Authentication → Emails**: the default sender is rate-limited and
   can land in spam. For real use, set up custom SMTP later.

## 4. Create the tables + security (one SQL paste)
Open **SQL Editor → New query**, paste all of this, and **Run**:

```sql
-- allowlist: email -> role
create table public.members (
  email text primary key,
  role  text not null default 'viewer' check (role in ('editor','viewer')),
  created_at timestamptz default now()
);

-- ONE shared scouting row per player (edited by editors, read by all members)
create table public.scouting (
  player_id text primary key,
  report text, rating int, tags jsonb, watch boolean, board jsonb, eye jsonb,
  updated_at timestamptz default now(), updated_by text
);

-- shared app blobs: bio overrides, custom agents/agencies, saved views, matchup
create table public.appdata (
  k text primary key, v jsonb, updated_at timestamptz default now()
);

alter table public.members  enable row level security;
alter table public.scouting enable row level security;
alter table public.appdata  enable row level security;

-- role lookup that safely bypasses RLS on the members table
create or replace function public.my_role() returns text
  language sql security definer stable set search_path = public as $$
  select role from public.members
  where lower(email) = lower(auth.jwt() ->> 'email') limit 1;
$$;
grant execute on function public.my_role() to authenticated;

-- each user may read their own membership row (so the app learns its role)
create policy "members read own" on public.members
  for select using (lower(email) = lower(auth.jwt() ->> 'email'));

-- editors may read the whole allowlist and manage it (needed for the in-app admin panel)
create policy "members read all for editors" on public.members
  for select using (public.my_role() = 'editor');
create policy "members manage for editors" on public.members
  for all using (public.my_role() = 'editor') with check (public.my_role() = 'editor');

-- scouting: members read, editors write
create policy "scouting read"  on public.scouting for select
  using (public.my_role() is not null);
create policy "scouting write" on public.scouting for all
  using (public.my_role() = 'editor') with check (public.my_role() = 'editor');

-- appdata: members read, editors write
create policy "appdata read"  on public.appdata for select
  using (public.my_role() is not null);
create policy "appdata write" on public.appdata for all
  using (public.my_role() = 'editor') with check (public.my_role() = 'editor');
```

## 5. Add yourself and your director
Still in the SQL Editor (edit the emails):
```sql
insert into public.members (email, role) values
  ('you@yourclub.com', 'editor'),
  ('director@yourclub.com', 'viewer');
```
- **editor** = you (and any future scouts you add the same way) — full edit.
- **viewer** = your director / guests — sees everything, can't change anything.

To add someone later, just insert another row. To revoke, delete their row. To promote a
viewer to editor: `update public.members set role='editor' where email='...';`

## How it behaves
- Opening the site with no session → a sign-in screen; nothing else loads.
- Enter an approved email → one-time link by email → click it → you're in.
- A logged-in email that **isn't** in `members` → a "not approved yet" screen (RLS also
  returns them zero rows, so there's nothing to leak).
- **Your first editor sign-in migrates your existing local scouting notes up to the shared
  DB automatically** (only if the DB is still empty, so it won't clobber anything).
- Viewers get a read-only app: ratings, eye grades and notes are visible but frozen, edit
  controls are hidden, and the database itself rejects any write from them.

## Notes
- The stats database (`data/data.json`) is still a static file; the app won't render it
  until you're signed in, but the raw file is technically reachable by URL. Your private
  work — the scouting layer — lives in Supabase behind the policies above and is not
  reachable without an approved login. If you ever want the stats file hard-gated too, put
  the whole site behind Cloudflare Access (separate ~20-min setup).
- In local mode (keys empty) nothing changes from before, including the gist sync button.

---

## Already ran the earlier SQL? Two quick updates

If you set up before the in-app admin panel + password login existed, run this once in
the **SQL Editor** so editors can manage the allowlist from inside EuroScout:

```sql
create policy "members read all for editors" on public.members
  for select using (public.my_role() = 'editor');
create policy "members manage for editors" on public.members
  for all using (public.my_role() = 'editor') with check (public.my_role() = 'editor');
```

**Password sign-in** (bypasses the magic-link email limit entirely) needs no SQL — it's in
the app now. To use it, create a password for yourself: **Authentication → Users → Add
user**, enter your email + a password, tick **Auto Confirm User**, save. Then on the
EuroScout sign-in screen click **"Have a password? Sign in without email"** and log in.
(You still need your `members` row as `editor` — that's the allowlist, separate from auth.)
