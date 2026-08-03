const sessions = new Map();
const GAMES = [
  ["cases", "命运之箱", "从 26 个密封箱中保留一个，在不断缩小的风险中与银行家谈判。", "单人 · 决策与风险", true],
  ["worm", "移动虫穴", "虫子每次失手后必向相邻洞移动；找出能保证抓住它的检查节奏。", "单人 · 隐藏状态追踪", true],
  ["pirates", "海盗议会", "亲自分配 100 枚金币，面对会做逆向归纳的理性海盗投票。", "单人 · 人机投票", true],
  ["kuhn-poker", "库恩扑克", "只用三张牌与策略型 AI 对决：读取下注信号，决定诈唬、跟注或弃牌。", "单人 · 隐藏手牌与诈唬", true],
  ["e-card", "E-Card 皇帝牌", "皇帝、市民与奴隶构成不对称循环；用隐藏出牌和高额弱者收益击败策略型 AI。", "单人 · 非对称混合策略", true],
  ["restricted-rps", "限定猜拳实验室", "固定库存让每次出拳都消耗未来选择；对抗均衡随机化与会学习的策略型 AI。", "单人 · 资源约束与机制设计", true],
  ["blackjack", "21 点策略实验室", "在透明规则下对抗庄家，比较自己的决策与规则限定的最优基础策略。", "单人 · 概率决策与策略审计", true],
  ["liars-dice", "骗子骰子", "隐藏手牌、公开叫价与诈唬识别。", "本地多人 · 即将开放", false],
  ["auction", "百元全支付拍卖", "用公开价格争夺主导权，并观察联盟与背叛。", "本地多人 · 即将开放", false],
].map(([id, title, summary, playerMode, available]) => ({ id, title, summary, playerMode, available }));

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});
const randomChoice = (items) => items[Math.floor(Math.random() * items.length)];
const shuffle = (items) => {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
};
const sample = (distribution) => {
  let target = Math.random();
  for (const [key, probability] of Object.entries(distribution)) {
    target -= probability;
    if (target <= 0) return key;
  }
  return Object.keys(distribution).at(-1);
};

class CaseSession {
  constructor(options) {
    this.prizes = [0.01,1,5,10,25,50,75,100,200,300,400,500,750,1000,5000,10000,25000,50000,75000,100000,200000,300000,400000,500000,750000,1000000];
    this.schedule = [6,5,4,3,2,1,1,1,1];
    this.values = Object.fromEntries(shuffle(this.prizes).map((v, i) => [i + 1, v]));
    this.riskTolerance = Number(options.riskTolerance || 100000);
    this.chosen = null; this.opened = {}; this.round = 0; this.openedRound = 0;
    this.phase = "choose"; this.offer = null; this.payout = null; this.history = [];
  }
  remaining() { return Object.entries(this.values).filter(([id]) => !(id in this.opened)).map(([,v]) => v); }
  act(action, payload) {
    const id = Number(payload.caseId);
    if (action === "choose_case" && this.phase === "choose" && this.values[id] != null) {
      this.chosen = id; this.phase = "opening"; this.history.push({kind:"choose", caseId:id});
    } else if (action === "open_case" && this.phase === "opening" && this.values[id] != null && id !== this.chosen && !(id in this.opened)) {
      const value = this.values[id]; this.opened[id] = value; this.openedRound += 1;
      this.history.push({kind:"reveal", caseId:id, value});
      if (this.openedRound === this.schedule[this.round]) {
        const values = this.remaining(); const mean = values.reduce((a,b)=>a+b,0) / values.length;
        this.offer = Math.round(mean * Math.min(0.96, 0.72 + this.round * 0.03));
        this.phase = "offer"; this.history.push({kind:"offer", round:this.round+1, value:this.offer});
      }
    } else if (action === "deal" && this.phase === "offer") {
      this.payout = this.offer; this.phase = "finished"; this.history.push({kind:"deal", value:this.payout});
    } else if (action === "no_deal" && this.phase === "offer") {
      this.history.push({kind:"no_deal", round:this.round+1});
      if (this.remaining().length === 1) { this.payout = this.values[this.chosen]; this.phase = "finished"; }
      else { this.round += 1; this.openedRound = 0; this.offer = null; this.phase = "opening"; }
    } else throw new Error("illegal case-game action");
  }
  snapshot() {
    const remaining = this.remaining(); let metrics = null;
    if (this.phase === "offer") {
      const mean = remaining.reduce((a,b)=>a+b,0)/remaining.length;
      const sd = Math.sqrt(remaining.reduce((a,b)=>a+(b-mean)**2,0)/remaining.length);
      metrics = {expectedValue:mean, standardDeviation:sd, certaintyEquivalent:mean-sd*sd/(2*this.riskTolerance), offerRatio:this.offer/mean, chanceToBeatOffer:remaining.filter(v=>v>this.offer).length/remaining.length, reservationRecommendation:this.offer >= mean-sd*sd/(2*this.riskTolerance) ? "deal" : "no_deal"};
    }
    const target = ["opening","offer"].includes(this.phase) ? this.schedule[this.round] : 0;
    return {gameId:"cases", phase:this.phase, round:this.round+1, chosenCase:this.chosen,
      cases:Object.keys(this.values).map(Number).map(id=>({id,status:id===this.chosen?"chosen":id in this.opened?"opened":"closed", ...((id in this.opened || (this.phase==="finished"&&id===this.chosen))?{value:this.values[id]}:{})})),
      prizeBoard:this.prizes.map(value=>({value,remaining:remaining.includes(value)})), openTarget:target, openedThisRound:this.openedRound, opensRemaining:Math.max(0,target-this.openedRound), offer:this.offer, metrics, payout:this.payout, history:this.history, riskTolerance:this.riskTolerance};
  }
}

const afterMiss = (positions, checked, count) => [...new Set(positions.filter(p=>p!==checked).flatMap(p=>[p>1?p-1:null,p<count?p+1:null]).filter(Boolean))].sort((a,b)=>a-b);
function wormStrategy(count) {
  const start = Array.from({length:count},(_,i)=>i+1); const queue = [[start,[]]]; const seen = new Set([start.join(",")]);
  while (queue.length) { const [belief,prefix] = queue.shift(); for (let h=1;h<=count;h+=1) {
    const path=[...prefix,h]; if (belief.every(p=>p===h)) return path;
    const next=afterMiss(belief,h,count), key=next.join(","); if(!seen.has(key)){seen.add(key);queue.push([next,path]);}
  }} throw new Error("no capture strategy");
}
class WormSession {
  constructor(options){this.count=Number(options.holes||5);this.positions=Array.from({length:this.count},(_,i)=>i+1);this.strategy=wormStrategy(this.count);this.turn=0;this.phase="playing";this.history=[];this.followed=true;this.caught=null;}
  act(action,payload){if(action!=="check_hole"||this.phase!=="playing")throw new Error("illegal worm action");const hole=Number(payload.holeId);this.followed=this.followed&&hole===this.strategy[this.turn];this.turn+=1;if(this.positions.every(p=>p===hole)){this.phase="finished";this.caught=hole;this.positions=[hole];this.history.push({turn:this.turn,holeId:hole,result:"caught",guaranteed:true});}else{this.history.push({turn:this.turn,holeId:hole,result:"miss"});this.positions=afterMiss(this.positions,hole,this.count);}}
  snapshot(){return{gameId:"worm",mode:"adversarial",phase:this.phase,turn:this.turn,holes:Array.from({length:this.count},(_,i)=>({id:i+1,possible:this.positions.includes(i+1),worm:this.caught===i+1})),possiblePositions:this.positions,strategy:this.strategy,followedStrategy:this.followed,suggestedHole:this.phase==="playing"&&this.followed?this.strategy[this.turn]??null:null,history:this.history};}
}

function pirateSolution(count,gold){const names=Array.from({length:count},(_,i)=>String.fromCharCode(65+i));const rounds=[];for(let active=1;active<=count;active+=1){const activeNames=names.slice(count-active),previous=rounds.at(-1),required=Math.ceil(active/2),candidates=[];for(let i=1;i<active;i+=1){const alive=previous.alive[i-1],outside=previous.allocation[i-1];candidates.push({cost:alive?outside+1:0,index:i});}candidates.sort((a,b)=>a.cost-b.cost||a.index-b.index);const chosen=candidates.slice(0,Math.max(0,required-1)),affordable=chosen.length===Math.max(0,required-1)&&chosen.reduce((a,b)=>a+b.cost,0)<=gold;let allocation,alive;if(affordable){allocation=Array(active).fill(0);chosen.forEach(x=>allocation[x.index]=x.cost);allocation[0]=gold-allocation.reduce((a,b)=>a+b,0);alive=Array(active).fill(true);}else{allocation=[0,...(previous?.allocation||[])];alive=[false,...(previous?.alive||[])];}rounds.push({names:activeNames,allocation,alive});}return{names,rounds,final:rounds.at(-1)};}
class PirateSession {
  constructor(options){this.count=Number(options.pirates||5);this.gold=Number(options.gold??100);this.solution=pirateSolution(this.count,this.gold);this.phase="proposing";this.proposal=null;this.votes=[];this.passed=null;this.realized=null;this.alive=null;}
  act(action,payload){if(action!=="submit_proposal"||this.phase!=="proposing")throw new Error("illegal pirate action");const a=payload.allocation.map(Number);if(a.length!==this.count||a.some(x=>x<0)||a.reduce((x,y)=>x+y,0)!==this.gold)throw new Error("proposal must allocate every coin");const previous=this.solution.rounds.at(-2);this.votes=a.map((offered,i)=>{if(i===0)return{pirate:this.solution.names[i],offered,supports:true,rejectionAlive:false,rejectionGold:0,reasonCode:"proposer"};const rejectionAlive=previous.alive[i-1],rejectionGold=previous.allocation[i-1];const supports=!rejectionAlive||offered>rejectionGold;return{pirate:this.solution.names[i],offered,supports,rejectionAlive,rejectionGold,reasonCode:!rejectionAlive?"survival":offered>rejectionGold?"more_gold":offered===rejectionGold?"equal_rejected":"less_gold"};});this.proposal=a;this.passed=this.votes.filter(v=>v.supports).length>=Math.ceil(this.count/2);this.realized=this.passed?a:[0,...(previous?.allocation||[])];this.alive=this.passed?Array(this.count).fill(true):[false,...(previous?.alive||[])];this.phase="finished";}
  snapshot(){return{gameId:"pirates",phase:this.phase,pirateCount:this.count,totalGold:this.gold,votesRequired:Math.ceil(this.count/2),pirates:this.solution.names.map((name,id)=>({id,name,isProposer:id===0})),proposal:this.proposal,votes:this.votes,yesVotes:this.votes.filter(v=>v.supports).length,passed:this.passed,realizedAllocation:this.realized,realizedAlive:this.alive,optimalAllocation:this.phase==="finished"?this.solution.final.allocation:null,matchesOptimal:this.proposal?this.proposal.every((v,i)=>v===this.solution.final.allocation[i]):null};}
}

class PokerSession {
  constructor(){this.hand=0;this.playerScore=0;this.aiScore=0;this.start();}
  start(){this.hand+=1;[this.playerCard,this.aiCard]=shuffle(["J","Q","K"]).slice(0,2);this.first=this.hand%2===1;this.phase="playing";this.history=[];this.result=null;this.pot=2;this.legal=this.first?["check","bet"]:[];if(!this.first)this.aiOpen();}
  aiBet(){return this.aiCard==="K"||(this.aiCard==="J"&&Math.random()<1/3);}
  aiOpen(){const action=this.aiBet()?"bet":"check";this.history.push({actor:"ai",action});if(action==="bet"){this.pot=3;this.legal=["fold","call"];}else this.legal=["check","bet"];}
  finish(winner,stakes,reason){const delta=winner==="player"?stakes:-stakes;this.playerScore+=delta;this.aiScore-=delta;this.result={winner,playerDelta:delta,reason,aiBluffed:this.history.some(x=>x.actor==="ai"&&x.action==="bet")&&this.aiCard==="J"};this.phase="finished";this.legal=["next_hand"];}
  showdown(stakes,reason){this.finish(["J","Q","K"].indexOf(this.playerCard)>["J","Q","K"].indexOf(this.aiCard)?"player":"ai",stakes,reason);}
  act(action){if(action==="next_hand"&&this.phase==="finished"){this.start();return;}if(!this.legal.includes(action))throw new Error("illegal poker action");this.history.push({actor:"player",action});if(action==="fold")return this.finish("ai",1,"player_folded");if(action==="call"){this.pot=4;return this.showdown(2,"bet_called");}if(action==="bet"){this.pot=3;const call=this.aiCard==="K"||(this.aiCard==="Q"&&Math.random()<1/3);this.history.push({actor:"ai",action:call?"call":"fold"});return call?this.showdown(2,"bet_called"):this.finish("player",1,"ai_folded");}if(this.history[0].actor==="ai")return this.showdown(1,"both_checked");const bet=this.aiBet();this.history.push({actor:"ai",action:bet?"bet":"check"});if(bet){this.pot=3;this.legal=["fold","call"];}else this.showdown(1,"both_checked");}
  snapshot(){return{gameId:"kuhn-poker",phase:this.phase,handNumber:this.hand,playerCard:this.playerCard,aiCard:this.phase==="finished"?this.aiCard:null,playerIsFirst:this.first,pot:this.pot,playerScore:this.playerScore,aiScore:this.aiScore,legalActions:this.legal,history:this.history,result:this.result,informationSet:{privateCard:this.playerCard,publicHistory:this.history,possibleOpponentCards:["J","Q","K"].filter(c=>c!==this.playerCard)}};}
}

class ECardSession {
  constructor(){this.round=0;this.playerScore=0;this.aiScore=0;this.timings=[];this.start();}
  start(){this.round+=1;this.playerRole=this.round%2?"emperor":"slave";this.aiRole=this.playerRole==="emperor"?"slave":"emperor";this.player=[this.playerRole,"citizen","citizen","citizen","citizen"];this.ai=[this.aiRole,"citizen","citizen","citizen","citizen"];this.phase="playing";this.history=[];this.last=null;this.result=null;}
  act(action,payload){if(action==="next_round"&&this.phase==="finished"){this.start();return;}const card=payload.card;if(action!=="play_card"||this.phase!=="playing"||!this.player.includes(card))throw new Error("illegal E-Card action");const duel=this.history.length+1;const specialIndex=this.ai.indexOf(this.aiRole),citizens=this.ai.filter(c=>c==="citizen").length;const probability=specialIndex<0?0:citizens===0?1:Math.min(.78,1/this.ai.length);const aiCard=Math.random()<probability?this.aiRole:"citizen";this.player.splice(this.player.indexOf(card),1);this.ai.splice(this.ai.indexOf(aiCard),1);const wins={emperor:"citizen",citizen:"slave",slave:"emperor"};const outcome=card===aiCard?"draw":wins[card]===aiCard?"player":"ai";this.last={duel,playerCard:card,aiCard,outcome,aiSpecialProbability:probability};this.history.push(this.last);if(card===this.playerRole)this.timings.push(duel);if(outcome!=="draw"){const role=outcome==="player"?this.playerRole:this.aiRole,points=role==="slave"?5:1;if(outcome==="player")this.playerScore+=points;else this.aiScore+=points;this.result={winner:outcome,winnerRole:role,points,decisiveDuel:duel};this.phase="finished";}}
  snapshot(){const hand=[...new Set(this.player)].map(card=>({card,count:this.player.filter(c=>c===card).length}));return{gameId:"e-card",phase:this.phase,roundNumber:this.round,duelNumber:this.history.length+(this.phase==="finished"?0:1),playerRole:this.playerRole,aiRole:this.aiRole,playerHand:hand,opponentCardsLeft:this.ai.length,playerScore:this.playerScore,aiScore:this.aiScore,history:this.history,lastReveal:this.last,result:this.result,legalActions:[this.phase==="playing"?"play_card":"next_round"],informationSet:{privateHand:this.player,publicHistory:this.history,possibleOpponentCards:[...new Set(this.ai)].sort(),opponentCardsLeft:this.ai.length}};}
}

class RPSSession {
  constructor(options){this.copies=Math.max(1,Math.min(8,Number(options.copies||3)));this.start();}
  start(){this.player={rock:this.copies,paper:this.copies,scissors:this.copies};this.ai={rock:this.copies,paper:this.copies,scissors:this.copies};this.seen={rock:0,paper:0,scissors:0};this.round=0;this.playerScore=0;this.aiScore=0;this.draws=0;this.phase="playing";this.history=[];this.last=null;}
  distribution(inventory){const total=Object.values(inventory).reduce((a,b)=>a+b,0);return Object.fromEntries(Object.entries(inventory).map(([k,v])=>[k,total?v/total:0]));}
  act(action,payload){if(action==="new_match"&&this.phase==="finished"){this.start();return;}const move=payload.move;if(action!=="play_move"||this.phase!=="playing"||!this.player[move])throw new Error("illegal RPS action");const equilibrium=this.distribution(this.ai),observed=this.round,prior=this.distribution(this.player);const prediction=Object.fromEntries(Object.keys(this.player).map(k=>[k,.55*prior[k]+.45*(this.seen[k]+1)/(observed+3)]));const counters={rock:"paper",paper:"scissors",scissors:"rock"};const likely=Object.keys(prediction).sort((a,b)=>prediction[b]-prediction[a])[0],best=counters[likely],weight=Math.min(.32,observed*.045);let final=Object.fromEntries(Object.keys(equilibrium).map(k=>[k,(1-weight)*equilibrium[k]+(k===best?weight:0)]));const sum=Object.values(final).reduce((a,b)=>a+b,0);final=Object.fromEntries(Object.entries(final).map(([k,v])=>[k,v/sum]));const aiMove=sample(final);this.player[move]-=1;this.ai[aiMove]-=1;this.seen[move]+=1;this.round+=1;const beats={rock:"scissors",paper:"rock",scissors:"paper"};const outcome=move===aiMove?"draw":beats[move]===aiMove?"player":"ai";if(outcome==="draw")this.draws+=1;else if(outcome==="player")this.playerScore+=1;else this.aiScore+=1;const analysis={equilibriumDistribution:equilibrium,predictedPlayerDistribution:prediction,bestResponse:best,exploitWeight:weight,finalDistribution:final,minimaxValue:0};this.history.push({round:this.round,playerMove:move,aiMove,outcome,analysis});this.last=analysis;if(Object.values(this.player).every(v=>v===0))this.phase="finished";}
  snapshot(){return{gameId:"restricted-rps",phase:this.phase,roundNumber:this.round,roundsTotal:this.copies*3,playerInventory:this.player,aiInventory:this.ai,playerScore:this.playerScore,aiScore:this.aiScore,draws:this.draws,history:this.history,lastAnalysis:this.last,equilibriumRecommendation:this.distribution(this.player),legalActions:[this.phase==="playing"?"play_move":"new_match"],informationSet:{privateChoice:null,publicHistory:this.history,knownInventories:{player:this.player,ai:this.ai}}};}
}

class BlackjackSession {
  constructor(){this.bankroll=0;this.wins=0;this.losses=0;this.pushes=0;this.decisions=0;this.matches=0;this.round=0;this.buildShoe();this.start();}
  buildShoe(){this.shoe=shuffle(["A","2","3","4","5","6","7","8","9","10","J","Q","K"].flatMap(r=>Array(24).fill(r)));}
  draw(){return this.shoe.pop();}
  value(cards){let total=0,aces=0;for(const c of cards){if(c==="A"){total+=11;aces+=1;}else total+=["10","J","Q","K"].includes(c)?10:Number(c);}while(total>21&&aces){total-=10;aces-=1;}return[total,aces>0];}
  start(){if(this.shoe.length<52)this.buildShoe();this.round+=1;this.multiplier=1;this.player=[this.draw(),this.draw()];this.dealer=[this.draw(),this.draw()];this.phase="player_turn";this.history=[];this.result=null;const pb=this.player.length===2&&this.value(this.player)[0]===21,db=this.value(this.dealer)[0]===21;if(pb||db)this.finish(pb&&db?"push":pb?"player":"dealer",pb&&!db?1.5:db&&!pb?-1:0,pb&&db?"both_blackjack":pb?"player_blackjack":"dealer_blackjack");}
  dealerValue(c){return c==="A"?11:["10","J","Q","K"].includes(c)?10:Number(c);}
  recommendation(){const [total,soft]=this.value(this.player),d=this.dealerValue(this.dealer[0]),canDouble=this.player.length===2;let r;if(soft){if(total>=19)r="stand";else if(total===18)r=d>=3&&d<=6?"double":[2,7,8].includes(d)?"stand":"hit";else if(total===17)r=d>=3&&d<=6?"double":"hit";else if([15,16].includes(total))r=d>=4&&d<=6?"double":"hit";else if([13,14].includes(total))r=d>=5&&d<=6?"double":"hit";else r="hit";}else{if(total>=17)r="stand";else if(total>=13)r=d>=2&&d<=6?"stand":"hit";else if(total===12)r=d>=4&&d<=6?"stand":"hit";else if(total===11)r=d<=10?"double":"hit";else if(total===10)r=d>=2&&d<=9?"double":"hit";else if(total===9)r=d>=3&&d<=6?"double":"hit";else r="hit";}return r==="double"&&!canDouble?"hit":r;}
  finish(winner,delta,reason){this.phase="finished";this.bankroll+=delta;if(winner==="player")this.wins+=1;else if(winner==="dealer")this.losses+=1;else this.pushes+=1;this.result={winner,delta,reason};}
  resolve(){while(this.value(this.dealer)[0]<17){const card=this.draw();this.dealer.push(card);this.history.push({actor:"dealer",action:"hit",card,total:this.value(this.dealer)[0]});}const p=this.value(this.player)[0],d=this.value(this.dealer)[0],stake=this.multiplier;if(d>21||p>d)this.finish("player",stake,d>21?"dealer_bust":"higher_total");else if(p<d)this.finish("dealer",-stake,"lower_total");else this.finish("push",0,"equal_total");}
  act(action){if(action==="new_round"&&this.phase==="finished"){this.start();return;}if(this.phase!=="player_turn")throw new Error("illegal blackjack action");const actual=action==="ai_play"?this.recommendation():action,legal=["hit","stand",...(this.player.length===2?["double"]:[])];if(!legal.includes(actual))throw new Error("illegal blackjack action");const recommended=this.recommendation(),matched=actual===recommended;this.decisions+=1;if(matched)this.matches+=1;this.history.push({actor:action==="ai_play"?"ai":"player",action:actual,recommended,matched,totalBefore:this.value(this.player)[0]});if(actual==="hit"){this.player.push(this.draw());const total=this.value(this.player)[0];if(total>21)this.finish("dealer",-this.multiplier,"player_bust");else if(total===21)this.resolve();}else if(actual==="double"){this.multiplier=2;this.player.push(this.draw());if(this.value(this.player)[0]>21)this.finish("dealer",-2,"player_bust");else this.resolve();}else this.resolve();}
  snapshot(){const[pTotal,pSoft]=this.value(this.player),finished=this.phase==="finished";return{gameId:"blackjack",phase:this.phase,roundNumber:this.round,playerHand:this.player,playerTotal:pTotal,playerSoft:pSoft,dealerHand:finished?this.dealer:[this.dealer[0]],dealerTotal:finished?this.value(this.dealer)[0]:null,dealerHoleHidden:!finished,shoeRemaining:this.shoe.length,betMultiplier:this.multiplier,bankroll:this.bankroll,wins:this.wins,losses:this.losses,pushes:this.pushes,legalActions:this.phase==="player_turn"?["hit","stand",...(this.player.length===2?["double"]:[])]:["new_round"],recommendation:this.phase==="player_turn"?this.recommendation():null,strategyAccuracy:this.decisions?this.matches/this.decisions:null,decisions:this.decisions,history:this.history,result:this.result,rules:{decks:6,dealerStandsSoft17:true,blackjackPayout:1.5,split:false,surrender:false,insurance:false},strategyScope:"six_deck_s17_no_split_no_surrender_no_counting",informationSet:{privateHand:this.player,publicDealerUpcard:this.dealer[0],hiddenDealerHole:finished?this.dealer[1]:true,shoeRemaining:this.shoe.length}};}
}

function createSession(gameId, options={}) {
  const factories={cases:CaseSession,worm:WormSession,pirates:PirateSession,"kuhn-poker":PokerSession,"e-card":ECardSession,"restricted-rps":RPSSession,blackjack:BlackjackSession};
  const Factory=factories[gameId]; if(!Factory)throw new Error("unknown or unavailable game"); return new Factory(options);
}

async function api(request, url) {
  if (request.method === "GET" && url.pathname === "/api/health") return json({status:"ok",service:"aip-public"});
  if (request.method === "GET" && url.pathname === "/api/games") return json({games:GAMES});
  if (request.method === "POST" && url.pathname === "/api/sessions") {
    const {gameId,options} = await request.json(); const session=createSession(gameId,options); const sessionId=crypto.randomUUID(); sessions.set(sessionId,session); return json({sessionId,state:session.snapshot()},201);
  }
  const match=url.pathname.match(/^\/api\/sessions\/([^/]+)\/actions$/);
  if(request.method==="POST"&&match){const session=sessions.get(match[1]);if(!session)throw new Error("unknown or expired session; restart the game");const{action,payload}=await request.json();session.act(action,payload||{});return json({state:session.snapshot()});}
  return json({error:"not found"},404);
}

export default {
  async fetch(request) {
    const url=new URL(request.url);
    try {
      if(url.pathname.startsWith("/api/"))return await api(request,url);
      if(url.pathname==="/"||url.pathname==="/index.html")return new Response(INDEX_HTML,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"public, max-age=300"}});
      if(url.pathname==="/styles.css")return new Response(STYLES_CSS,{headers:{"content-type":"text/css; charset=utf-8","cache-control":"public, max-age=3600"}});
      if(url.pathname==="/app.js")return new Response(APP_JS,{headers:{"content-type":"text/javascript; charset=utf-8","cache-control":"public, max-age=3600"}});
      return new Response("Not found",{status:404});
    } catch(error) { return json({error:error instanceof Error?error.message:"operation failed"},400); }
  }
};
