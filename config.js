// EuroScout configuration.
// Leave SUPABASE_URL / SUPABASE_ANON_KEY empty to run in single-user LOCAL mode
// (scouting data saved in this browser; optional cross-device sync via the gist
// button in the header).
// Fill both in to enable the SHARED cloud backend: email magic-link sign-in, an
// allowlist of approved emails with roles (editor = full edit, viewer = read-only),
// and one shared scouting dataset so your director sees your work. The whole app is
// gated behind sign-in. See README_SUPABASE.md for the one-time project + SQL setup.
window.EUROSCOUT_CONFIG = {
  SUPABASE_URL: "",       // e.g. "https://xxxxxxxx.supabase.co"
  SUPABASE_ANON_KEY: "",  // the project's public anon (publishable) key — safe to commit
};
