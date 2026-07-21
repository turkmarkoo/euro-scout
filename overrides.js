// EuroScout — manual overrides (edit players in the app, then Export to regenerate this file and commit it).
// links: manually tie the SAME person together across competitions/leagues when auto-linking (code or name+birth-year) misses them.
// bio:   correct or fill in height (cm), weight (kg), country, position (G/F/C), year of birth,
//        hand (L/R), agent, agency, agentUrl (RealGM agent-client page), rgm (RealGM player page).
// ext:   an external profile URL (EuroBasket / FIBA / league site) shown on the player's header.
window.EUROSCOUT_OVERRIDES = {
  links: [
    // ["euroleague-uros-trifunovic", "liga-acb-uros-trifunovic"]
  ],
  bio: {
    // "euroleague-some-player": { "height": 206, "weight": 102, "country": "Greece", "pos": "F", "born": 1995,
    //   "hand": "R", "agent": "Jeffrey Abankwa", "agency": "Wasserman",
    //   "agentUrl": "https://basketball.realgm.com/info/agent-client-list/Jeffrey-Abankwa/1592",
    //   "rgm": "https://basketball.realgm.com/player/..." }
  },
  ext: {
    // "euroleague-some-player": "https://www.fiba.basketball/en/players/..."
  }
};
// Agencies shown in the Agent/Agency dropdown. Add/edit freely here, or add new ones live in the app
// (they're saved to your browser and merged with this list).
window.EUROSCOUT_AGENCIES = [
  "Wasserman","Octagon","Excel Sports","CAA Sports","Roc Nation Sports","Priority Sports",
  "BeoBasket","Interperformances","YouFirst Sports","BDA Sports","Klutch Sports",
  "Mardešić Sports","Slash Sports","ProSports","U1st Sports","LIFT Sports Management"
];
