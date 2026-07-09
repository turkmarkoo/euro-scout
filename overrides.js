// EuroScout — manual overrides (edit players in the app, then Export to regenerate this file and commit it).
// links: manually tie the SAME person together across competitions/leagues when auto-linking (code or name+birth-year) misses them.
// bio:   correct or fill in a player's height (cm), weight (kg), country, position (G/F/C) or year of birth.
// ext:   an external profile URL (EuroBasket / FIBA / league site) shown on the player's header.
window.EUROSCOUT_OVERRIDES = {
  links: [
    // ["euroleague-uros-trifunovic", "liga-acb-uros-trifunovic"]
  ],
  bio: {
    // "euroleague-some-player": { "height": 206, "weight": 102, "country": "Greece", "pos": "F", "born": 1995 }
  },
  ext: {
    // "euroleague-some-player": "https://www.fiba.basketball/en/players/..."
  }
};
