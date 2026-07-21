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
  "The Team","Octagon","Excel Sports Management","CAA Sports","Roc Nation Sports","Priority Sports",
  "Klutch Sports","BDA Sports","WME Sports",
  "Interperformances","BeoBasket","YouFirst Sports","Higher Vision Basketball","Base Sports",
  "Sport1 Basketball","ProBasket","Court Side","Slash Sports","Pallas Sports","Mizrahi Sports",
  "Rebasa","Mészáros Sport","BeoBasket Adriatic","Life Sports Agency","U1st Sports",
  "LIFT Sports Management","Wolf Sports","Two Points","AENA Sports","Octagon Europe",
  "Comsport","Meridian Sports","SFX Basketball","Glez Basket","Estival Sports"
];
