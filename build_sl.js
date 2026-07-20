const sl=require('/mnt/user-data/uploads/sl_vegas_2026_full.json').players;
const d=require('/home/claude/build/site/data/data.json');
function normName(x){return (x||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[\u0111\u0142]/g,'d').replace(/[\u015f\u0219]/g,'s').replace(/[\u0131]/g,'i').replace(/[\u0127]/g,'h').replace(/[\u00f0]/g,'d').replace(/[\u00f8]/g,'o').replace(/[\u00e6]/g,'ae').replace(/[^a-z ]/g,'').trim();}

// NBA team abbr -> full name
const TEAMS={ATL:'Atlanta Hawks',BOS:'Boston Celtics',BKN:'Brooklyn Nets',CHA:'Charlotte Hornets',CHI:'Chicago Bulls',CLE:'Cleveland Cavaliers',DAL:'Dallas Mavericks',DEN:'Denver Nuggets',DET:'Detroit Pistons',GSW:'Golden State Warriors',HOU:'Houston Rockets',IND:'Indiana Pacers',LAC:'LA Clippers',LAL:'Los Angeles Lakers',MEM:'Memphis Grizzlies',MIA:'Miami Heat',MIL:'Milwaukee Bucks',MIN:'Minnesota Timberwolves',NOP:'New Orleans Pelicans',NYK:'New York Knicks',OKC:'Oklahoma City Thunder',ORL:'Orlando Magic',PHI:'Philadelphia 76ers',PHX:'Phoenix Suns',POR:'Portland Trail Blazers',SAC:'Sacramento Kings',SAS:'San Antonio Spurs',TOR:'Toronto Raptors',UTA:'Utah Jazz',WAS:'Washington Wizards'};

// compute per-40 and derived, then percentiles across the SL pool (qualified: >=2 GP)
function per40(v,min){return min>0?v/min*40:0;}
sl.forEach(p=>{
  p.efg=p.fga>0?((p.fgm-p.f3m)+1.5*p.f3m)/p.fga*100:0; // wrong: fgm includes 3? NBA FGM is total. eFG=(FGM+0.5*3PM)/FGA
  p.efg=p.fga>0?(p.fgm+0.5*p.f3m)/p.fga*100:0;
  p.pts40=per40(p.pts,p.min);p.reb40=per40(p.reb,p.min);p.ast40=per40(p.ast,p.min);
  p.stl40=per40(p.stl,p.min);p.blk40=per40(p.blk,p.min);p.tov40=per40(p.tov,p.min);
  // TS%: pts/(2*(fga+0.44*fta))
  p.ts=(p.fga+0.44*p.fta)>0?p.pts/(2*(p.fga+0.44*p.fta))*100:0;
  // usg from bio (fraction) -> pct number; ast_pct etc likewise
  p.usgN=p.usg!=null?p.usg*100:null;
  // simple PIR (efficiency): pts+reb+ast+stl+blk - (missed fg + missed ft + tov)
  p.pir=p.pts+p.reb+p.ast+p.stl+p.blk-((p.fga-p.fgm)+(p.fta-p.ftm)+p.tov);
});
const qual=sl.filter(p=>p.gp>=2&&p.min>=8);
function pctRank(pool,key,val,lower){if(val==null)return null;const vals=pool.map(x=>x[key]).filter(v=>v!=null&&!isNaN(v));if(vals.length<2)return 50;let below=0,eq=0;vals.forEach(v=>{if(v<val)below++;else if(v===val)eq++;});let pct=Math.round((below+eq/2)/vals.length*100);if(lower)pct=100-pct;return Math.max(0,Math.min(100,pct));}
// build pct per player over qualified pool
const PCTKEYS={ppg:'pts',rpg:'reb',apg:'ast',spg:'stl',bpg:'blk',topg:'tov',fgp:'fgp',f3p:'f3p',ftp:'ftp',efg:'efg',ts:'ts',pir:'pir',pts40:'pts40',reb40:'reb40',ast40:'ast40',stl40:'stl40',blk40:'blk40',usg:'usgN'};
sl.forEach(p=>{
  p.pct={};
  for(const[pk,sk]of Object.entries(PCTKEYS)){p.pct[pk]=pctRank(qual,sk,p[sk],pk==='topg');}
});
// cross-match map: normalized name -> present in EU
const euNN=new Set();d.leagues.forEach(L=>L.players.forEach(pl=>euNN.add(normName(pl.name))));
// exclude the known false positive
sl.forEach(p=>{p.euMatch=euNN.has(normName(p.name))&&normName(p.name)!=='aaron scott';});
const matched=sl.filter(p=>p.euMatch);
console.log('SL players:',sl.length,'| qualified pool:',qual.length,'| EU-matched:',matched.length);
// output structured file
const out={event:'NBA Summer League 2026 — Las Vegas',short:'NBA SL 2026',season:2026,leagueId:15,
  qualifiedCount:qual.length,playerCount:sl.length,
  teams:[...new Set(sl.map(p=>p.team))].filter(Boolean).map(t=>({code:t,name:TEAMS[t]||t})),
  players:sl.map(p=>({
    name:p.name,team:p.team,teamName:(TEAMS[p.team]||p.team),
    g:p.gp,mpg:p.min,ppg:p.pts,rpg:p.reb,apg:p.ast,spg:p.stl,bpg:p.blk,topg:p.tov,
    fgp:p.fgp,f3p:p.f3p,ftp:p.ftp,efg:Math.round(p.efg*10)/10,ts:Math.round(p.ts*10)/10,
    fgma:p.fgm+'-'+p.fga,f3ma:p.f3m+'-'+p.f3a,ftma:p.ftm+'-'+p.fta,
    pts40:Math.round(p.pts40*10)/10,reb40:Math.round(p.reb40*10)/10,ast40:Math.round(p.ast40*10)/10,
    stl40:Math.round(p.stl40*10)/10,blk40:Math.round(p.blk40*10)/10,
    pir:Math.round(p.pir*10)/10,usg:p.usgN!=null?Math.round(p.usgN*10)/10:null,
    ht:p.htIn,wt:p.wt,country:p.country,college:p.college,draftYr:p.draftYr,
    nbaId:p.id||null,pct:p.pct,euMatch:p.euMatch,nn:normName(p.name)
  }))};
require('fs').writeFileSync('/tmp/sl_data.json',JSON.stringify(out));
console.log('wrote /tmp/sl_data.json',(JSON.stringify(out).length/1024).toFixed(0),'KB');
// show top 10 by pir
console.log('--- top 10 SL by PIR ---');
sl.filter(p=>p.gp>=2).sort((a,b)=>b.pir-a.pir).slice(0,10).forEach(p=>console.log(p.pir.toFixed(1),p.name,p.team,'| '+p.pts+'p '+p.reb+'r '+p.ast+'a',p.euMatch?'[EU]':''));
