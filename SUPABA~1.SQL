-- EuroScout · Supabase backend setup
-- Run this once in your Supabase project: SQL Editor -> New query -> paste -> Run.
-- It creates the table that stores each user's scouting reports, ratings, tags,
-- watchlist flags and big-board ranks, locked down so users only see their own rows.

create table if not exists public.scouting (
  user_id    uuid        not null references auth.users (id) on delete cascade,
  player_id  text        not null,           -- e.g. "euroleague-mike-james"
  report     text        default '',
  rating     smallint    default 0,          -- 0-5 star grade
  tags       text[]      default '{}',
  watch      boolean     default false,      -- on the watchlist?
  board      integer,                        -- big-board rank (null = not on board)
  updated_at timestamptz default now(),
  primary key (user_id, player_id)
);

alter table public.scouting enable row level security;

-- Each signed-in user can read/write ONLY their own rows.
create policy "own rows - select" on public.scouting
  for select using (auth.uid() = user_id);
create policy "own rows - insert" on public.scouting
  for insert with check (auth.uid() = user_id);
create policy "own rows - update" on public.scouting
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own rows - delete" on public.scouting
  for delete using (auth.uid() = user_id);

-- Sign-in uses email magic links (Supabase Auth -> Providers -> Email is on by
-- default). No extra config needed for the app to work.
