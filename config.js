// EuroScout configuration.
// Leave SUPABASE_URL / SUPABASE_ANON_KEY empty to run in local-only mode
// (scouting reports, ratings, watchlist and big board are saved in this
// browser via localStorage). Fill both in to enable the cloud backend so your
// data syncs across devices and is tied to your sign-in. See README for the
// one-time Supabase setup (project creation + the `scouting` table SQL).
window.EUROSCOUT_CONFIG = {
  SUPABASE_URL: "",       // e.g. "https://xxxxxxxx.supabase.co"
  SUPABASE_ANON_KEY: "",  // the project's public anon key
};
