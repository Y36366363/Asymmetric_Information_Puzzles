const sessions = new Map();
const GAMES = [
  ["cases", "命运之箱", "从 26 个密封箱中保留一个，在不断缩小的风险中与银行家谈判。", "单人 · 决策与风险", true],
  ["blackjack", "21 点策略实验室", "在透明规则下对抗庄家，比较自己的决策与规则限定的最优基础策略。", "单人 · 概率决策与策略审计", true],
  ["restricted-rps", "限定猜拳实验室", "固定库存让每次出拳都消耗未来选择；对抗均衡随机化与会学习的策略型 AI。", "单人 · 资源约束与机制设计", true],
  ["mastermind", "猜数字 · 密码破解", "从 5,040 个隐藏密码中推理答案，并比较自己的步数与 minimax 信息策略。", "单人 · 信息集搜索", true],
  ["battleship", "海战棋", "部署自己的舰队，在未知海域中搜索敌舰，并对抗概率热力图 AI。", "单人 · 隐藏部署与概率搜索", true],
  ["e-card", "E-Card 皇帝牌", "皇帝、市民与奴隶构成不对称循环；用隐藏出牌和高额弱者收益击败策略型 AI。", "单人 · 非对称混合策略", true],
  ["pirates", "海盗议会", "亲自分配 100 枚金币，面对会做逆向归纳的理性海盗投票。", "单人 · 人机投票", true],
  ["kuhn-poker", "库恩扑克", "只用三张牌与策略型 AI 对决：读取下注信号，决定诈唬、跟注或弃牌。", "单人 · 隐藏手牌与诈唬", true],
  ["liars-dice", "骗子骰子", "隐藏手牌、公开叫价与质疑概率；判断何时加注，何时抓住 AI 的虚张声势。", "单人 · 隐藏骰子与公开信号", true],
  ["worm", "移动虫穴", "虫子每次失手后必向相邻洞移动；找出能保证抓住它的检查节奏。", "单人 · 隐藏状态追踪", true],
  ["auction", "百元全支付拍卖", "用公开价格争夺主导权，并观察联盟与背叛。", "本地多人 · 即将开放", false],
].map(([id, title, summary, playerMode, available]) => ({ id, title, summary, playerMode, available }));

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});
const randomChoice = (items) => items[Math.floor(Math.random() * items.length)];
const boundedInteger = (value, fallback, minimum, maximum, label) => { const number=Number(value??fallback); if(!Number.isInteger(number)||number<minimum||number>maximum)throw new Error(`${label} must be a whole number from ${minimum} to ${maximum}`); return number; };
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
    this.schedule = [6,5,4,3,2,1,1,1,1,1];
    this.values = Object.fromEntries(shuffle(this.prizes).map((v, i) => [i + 1, v]));
    this.riskTolerance = Number(options.riskTolerance ?? 100000); if(!Number.isFinite(this.riskTolerance)||this.riskTolerance<=0)throw new Error("risk tolerance must be positive");
    this.chosen = null; this.opened = {}; this.round = 0; this.openedRound = 0;
    this.phase = "choose"; this.offer = null; this.payout = null; this.history = []; this.result = null;
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
      this.payout = this.offer; this.phase = "finished"; this.result={kind:"deal",payout:this.payout,offer:this.offer}; this.history.push({kind:"deal", value:this.payout});
    } else if (action === "no_deal" && this.phase === "offer") {
      this.history.push({kind:"no_deal", round:this.round+1});
      if (this.remaining().length === 1) { this.payout = this.values[this.chosen]; this.phase = "finished"; this.result={kind:"kept_case",payout:this.payout,chosenCase:this.chosen}; this.history.push({kind:"case_payout",caseId:this.chosen,value:this.payout}); }
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
      prizeBoard:this.prizes.map(value=>({value,remaining:remaining.includes(value)})), openTarget:target, openedThisRound:this.openedRound, opensRemaining:Math.max(0,target-this.openedRound), offer:this.offer, isFinalOffer:this.phase==="offer"&&remaining.length===1, metrics, payout:this.payout, result:this.result, history:this.history, riskTolerance:this.riskTolerance};
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
  constructor(options){this.count=boundedInteger(options.holes,5,3,12,"holes");this.positions=Array.from({length:this.count},(_,i)=>i+1);this.strategy=wormStrategy(this.count);this.turn=0;this.phase="playing";this.history=[];this.followed=true;this.caught=null;}
  act(action,payload){if(action!=="check_hole"||this.phase!=="playing")throw new Error("illegal worm action");const hole=boundedInteger(payload.holeId,0,1,this.count,"hole");this.followed=this.followed&&hole===this.strategy[this.turn];this.turn+=1;if(this.positions.every(p=>p===hole)){this.phase="finished";this.caught=hole;this.positions=[hole];this.history.push({turn:this.turn,holeId:hole,result:"caught",guaranteed:true});}else{this.history.push({turn:this.turn,holeId:hole,result:"miss"});this.positions=afterMiss(this.positions,hole,this.count);}}
  snapshot(){return{gameId:"worm",mode:"adversarial",phase:this.phase,turn:this.turn,holes:Array.from({length:this.count},(_,i)=>({id:i+1,possible:this.positions.includes(i+1),worm:this.caught===i+1})),possiblePositions:this.positions,strategy:this.strategy,followedStrategy:this.followed,suggestedHole:this.phase==="playing"&&this.followed?this.strategy[this.turn]??null:null,history:this.history};}
}

function pirateSolution(count,gold){const names=Array.from({length:count},(_,i)=>String.fromCharCode(65+i));const rounds=[];for(let active=1;active<=count;active+=1){const activeNames=names.slice(count-active),previous=rounds.at(-1),required=Math.ceil(active/2),candidates=[];for(let i=1;i<active;i+=1){const alive=previous.alive[i-1],outside=previous.allocation[i-1];candidates.push({cost:alive?outside+1:0,index:i});}candidates.sort((a,b)=>a.cost-b.cost||a.index-b.index);const chosen=candidates.slice(0,Math.max(0,required-1)),affordable=chosen.length===Math.max(0,required-1)&&chosen.reduce((a,b)=>a+b.cost,0)<=gold;let allocation,alive;if(affordable){allocation=Array(active).fill(0);chosen.forEach(x=>allocation[x.index]=x.cost);allocation[0]=gold-allocation.reduce((a,b)=>a+b,0);alive=Array(active).fill(true);}else{allocation=[0,...(previous?.allocation||[])];alive=[false,...(previous?.alive||[])];}rounds.push({names:activeNames,allocation,alive});}return{names,rounds,final:rounds.at(-1)};}
class PirateSession {
  constructor(options){this.count=boundedInteger(options.pirates,5,1,12,"pirates");this.gold=boundedInteger(options.gold,100,0,10000,"gold");this.solution=pirateSolution(this.count,this.gold);this.phase="proposing";this.proposal=null;this.votes=[];this.passed=null;this.realized=null;this.alive=null;}
  act(action,payload){if(action!=="submit_proposal"||this.phase!=="proposing")throw new Error("illegal pirate action");if(!Array.isArray(payload.allocation))throw new Error("allocation must be a list");const a=payload.allocation.map(Number);if(a.length!==this.count||a.some(x=>!Number.isInteger(x)||x<0)||a.reduce((x,y)=>x+y,0)!==this.gold)throw new Error("proposal must allocate every coin as whole numbers");const previous=this.solution.rounds.at(-2);this.votes=a.map((offered,i)=>{if(i===0)return{pirate:this.solution.names[i],offered,supports:true,rejectionAlive:false,rejectionGold:0,reasonCode:"proposer"};const rejectionAlive=previous.alive[i-1],rejectionGold=previous.allocation[i-1];const supports=!rejectionAlive||offered>rejectionGold;return{pirate:this.solution.names[i],offered,supports,rejectionAlive,rejectionGold,reasonCode:!rejectionAlive?"survival":offered>rejectionGold?"more_gold":offered===rejectionGold?"equal_rejected":"less_gold"};});this.proposal=a;this.passed=this.votes.filter(v=>v.supports).length>=Math.ceil(this.count/2);this.realized=this.passed?a:[0,...(previous?.allocation||[])];this.alive=this.passed?Array(this.count).fill(true):[false,...(previous?.alive||[])];this.phase="finished";}
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
  constructor(options){this.copies=boundedInteger(options.copies,3,1,8,"copies");this.start();}
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

class LiarDiceSession {
  constructor(options = {}) { this.dicePerPlayer = boundedInteger(options.dice,5,2,8,"dice"); this.playerScore = 0; this.aiScore = 0; this.round = 0; this.start(); }
  roll(count) { return Array.from({length: count}, () => 1 + Math.floor(Math.random() * 6)).sort((a,b) => a-b); }
  start() { this.round += 1; this.player = this.roll(this.dicePerPlayer); this.ai = this.roll(this.dicePerPlayer); this.bid = null; this.phase = "bidding"; this.turn = "player"; this.history = []; this.result = null; }
  higher(candidate) { return !this.bid || candidate[0] > this.bid[0] || (candidate[0] === this.bid[0] && candidate[1] > this.bid[1]); }
  validate(quantity, face) { if (!Number.isInteger(quantity) || !Number.isInteger(face) || quantity < 1 || quantity > this.dicePerPlayer * 2 || face < 1 || face > 6 || !this.higher([quantity, face])) throw new Error("bid must use whole numbers and be higher than the public bid"); return [quantity, face]; }
  probability(bid, knownDice=this.player) { if (!bid) return null; const [quantity, face] = bid; const own = knownDice.filter(value => value === face || (face !== 1 && value === 1)).length; const needed = quantity - own; if (needed <= 0) return 1; const p = face === 1 ? 1/6 : 1/3; let total = 0; for (let k = Math.max(needed, 0); k <= this.dicePerPlayer; k += 1) { let c = 1; for (let i = 1; i <= k; i += 1) c = c * (this.dicePerPlayer - i + 1) / i; total += c * p ** k * (1-p) ** (this.dicePerPlayer-k); } return total; }
  act(action, payload = {}) { if (action === "new_round" && this.phase === "finished") { this.start(); return; } if (action === "raise_bid") { if (this.phase !== "bidding" || this.turn !== "player") throw new Error("it is not your bidding turn"); const bid = this.validate(Number(payload.quantity), Number(payload.face)); this.bid = bid; this.history.push({actor:"player", action:"raise", quantity:bid[0], face:bid[1]}); this.turn = "ai"; this.aiRespond(); return; } if (action === "challenge") { if (this.phase !== "bidding" || this.turn !== "player" || !this.bid) throw new Error("there is no bid to challenge"); this.history.push({actor:"player", action:"challenge", bid:this.bid}); this.resolve("player"); return; } throw new Error("unknown liar's-dice action"); }
  aiRespond() { const confidence = this.probability(this.bid,this.ai); if (confidence < .45 || this.bid[0] >= this.dicePerPlayer * 2) { this.history.push({actor:"ai", action:"challenge", bid:this.bid, confidence}); this.resolve("ai"); return; } const preferred = [1,2,3,4,5,6].sort((a,b) => (this.ai.filter(v=>v===b).length + (b===1?0:this.ai.filter(v=>v===1).length)) - (this.ai.filter(v=>v===a).length + (a===1?0:this.ai.filter(v=>v===1).length)))[0]; const next = this.bid[0] < this.dicePerPlayer*2 ? [this.bid[0]+1, preferred] : [this.bid[0], this.bid[1]+1]; if (!this.higher(next) || next[1] > 6) { this.history.push({actor:"ai", action:"challenge", bid:this.bid, confidence}); this.resolve("ai"); return; } this.bid = next; this.history.push({actor:"ai", action:"raise", quantity:next[0], face:next[1], confidence}); this.turn = "player"; }
  resolve(challenger) { const [quantity, face] = this.bid; const count = [...this.player, ...this.ai].filter(value => value === face || (face !== 1 && value === 1)).length; const claimTrue = count >= quantity; const loser = claimTrue ? challenger : challenger === "player" ? "ai" : "player"; const winner = loser === "player" ? "ai" : "player"; if (winner === "player") this.playerScore += 1; else this.aiScore += 1; this.result = {challenger, bid:this.bid, actualCount:count, claimTrue, winner, loser}; this.phase = "finished"; this.turn = "none"; }
  snapshot() { const confidence = this.probability(this.bid); return {gameId:"liars-dice", phase:this.phase, roundNumber:this.round, dicePerPlayer:this.dicePerPlayer, playerDice:this.player, opponentDiceCount:this.ai.length, currentBid:this.bid, minimumBid:this.bid ? {quantity:this.bid[1] < 6 ? this.bid[0] : this.bid[0]+1, face:this.bid[1] < 6 ? this.bid[1]+1 : 1} : null, turn:this.turn, playerScore:this.playerScore, aiScore:this.aiScore, claimProbability:confidence, history:this.history, result:this.result, legalActions:this.phase === "bidding" && this.turn === "player" ? ["raise_bid","challenge"] : this.phase === "finished" ? ["new_round"] : [], informationSet:{privateHand:this.player, publicHistory:this.history, opponentDiceCount:this.ai.length, claimProbability:confidence}}; }
}

const battleKey = (cell) => `${cell[0]},${cell[1]}`;
const battleCell = (key) => key.split(",").map(Number);
function battlePlacements(size, length) {
  const result=[];
  for(let row=0;row<size;row+=1)for(let column=0;column<=size-length;column+=1)result.push(Array.from({length},(_,offset)=>[row,column+offset]));
  for(let row=0;row<=size-length;row+=1)for(let column=0;column<size;column+=1)result.push(Array.from({length},(_,offset)=>[row+offset,column]));
  return result;
}
function battleFleet(size, lengths) {
  for(let attempt=0;attempt<1000;attempt+=1){const occupied=new Set(),ships=[];for(const length of lengths){const candidates=battlePlacements(size,length).filter(cells=>cells.every(cell=>!occupied.has(battleKey(cell))));if(!candidates.length)break;const cells=randomChoice(candidates),keys=new Set(cells.map(battleKey));keys.forEach(key=>occupied.add(key));ships.push({length,cells:keys});}if(ships.length===lengths.length)return{ships,shots:new Set(),hits:new Set()};}
  throw new Error("could not place a legal fleet");
}
function battleFire(board, cell, size) {
  const key=battleKey(cell);if(cell.some(value=>!Number.isInteger(value)||value<0||value>=size))throw new Error("shot is outside the board");if(board.shots.has(key))throw new Error("the same cell cannot be fired at twice");board.shots.add(key);const ship=board.ships.find(item=>item.cells.has(key));if(!ship)return{cell,hit:false,sunk:false,sunkLength:null,sunkCells:[]};board.hits.add(key);const sunk=[...ship.cells].every(item=>board.hits.has(item));return{cell,hit:true,sunk,sunkLength:sunk?ship.length:null,sunkCells:sunk?[...ship.cells].map(battleCell):[]};
}
function battleTracker(lengths){return{shots:new Set(),misses:new Set(),hits:new Set(),sunk:new Set(),remaining:[...lengths]};}
function observeBattle(tracker,outcome){const key=battleKey(outcome.cell);tracker.shots.add(key);if(!outcome.hit){tracker.misses.add(key);return;}tracker.hits.add(key);if(outcome.sunk){tracker.remaining.splice(tracker.remaining.indexOf(outcome.sunkLength),1);for(const cell of outcome.sunkCells){const item=battleKey(cell);tracker.sunk.add(item);tracker.hits.delete(item);}}}
function battleDensity(tracker,size){const scores=new Map();for(let row=0;row<size;row+=1)for(let column=0;column<size;column+=1){const key=battleKey([row,column]);if(!tracker.shots.has(key))scores.set(key,0);}let candidatePlacements=0;for(const length of tracker.remaining){let candidates=battlePlacements(size,length).filter(cells=>cells.every(cell=>!tracker.misses.has(battleKey(cell))&&!tracker.sunk.has(battleKey(cell))));if(tracker.hits.size){const focused=candidates.filter(cells=>cells.some(cell=>tracker.hits.has(battleKey(cell))));if(focused.length)candidates=focused;}candidatePlacements+=candidates.length;for(const cells of candidates)for(const cell of cells){const key=battleKey(cell);if(scores.has(key))scores.set(key,scores.get(key)+1);}}return{scores,candidatePlacements};}
function chooseBattleShot(tracker,size,randomize=true){const{scores,candidatePlacements}=battleDensity(tracker,size),peak=Math.max(...scores.values()),best=[...scores].filter(([,score])=>score===peak).map(([key])=>key).sort(),key=randomize?randomChoice(best):best[0];return{cell:battleCell(key),analysis:{candidatePlacements,peakDensity:peak,tiedBestCells:best.length,chosenCell:battleCell(key)}};}
const BATTLE_FLEETS={10:[5,4,3,3,2],12:[6,5,4,3,3,2],15:[7,6,5,4,4,3,2]};
function battleOrientation(ship){return new Set([...ship.cells].map(key=>battleCell(key)[0])).size===1?"horizontal":"vertical";}
function rotateBattleShip(board,shipId,size){if(!Number.isInteger(shipId)||shipId<0||shipId>=board.ships.length)throw new Error("unknown ship");const ship=board.ships[shipId],horizontal=battleOrientation(ship)==="horizontal",coordinates=[...ship.cells].map(battleCell),anchorRow=Math.min(...coordinates.map(cell=>cell[0])),anchorColumn=Math.min(...coordinates.map(cell=>cell[1])),occupied=new Set(board.ships.filter((_,index)=>index!==shipId).flatMap(item=>[...item.cells])),candidates=[];if(horizontal){for(let row=0;row<=size-ship.length;row+=1)for(let column=0;column<size;column+=1){const cells=Array.from({length:ship.length},(_,offset)=>[row+offset,column]),keys=new Set(cells.map(battleKey));if([...keys].every(key=>!occupied.has(key)))candidates.push(keys);}}else{for(let row=0;row<size;row+=1)for(let column=0;column<=size-ship.length;column+=1){const cells=Array.from({length:ship.length},(_,offset)=>[row,column+offset]),keys=new Set(cells.map(battleKey));if([...keys].every(key=>!occupied.has(key)))candidates.push(keys);}}if(!candidates.length)throw new Error("no collision-free rotation is available");candidates.sort((a,b)=>{const ca=[...a].map(battleCell),cb=[...b].map(battleCell),da=Math.abs(Math.min(...ca.map(x=>x[0]))-anchorRow)+Math.abs(Math.min(...ca.map(x=>x[1]))-anchorColumn),db=Math.abs(Math.min(...cb.map(x=>x[0]))-anchorRow)+Math.abs(Math.min(...cb.map(x=>x[1]))-anchorColumn);return da-db;});board.ships[shipId]={length:ship.length,cells:candidates[0]};}

class BattleshipSession {
  constructor(options={}){this.configure(boundedInteger(options.boardSize,10,10,15,"boardSize"));}
  configure(size){if(!BATTLE_FLEETS[size])throw new Error("boardSize must be 10, 12, or 15");this.size=size;this.lengths=[...BATTLE_FLEETS[size]];this.player=battleFleet(this.size,this.lengths);this.enemy=battleFleet(this.size,this.lengths);this.ai=battleTracker(this.lengths);this.advisor=battleTracker(this.lengths);this.phase="placement";this.turn=0;this.winner=null;this.history=[];this.lastAiAnalysis=null;}
  remaining(board){return board.ships.filter(ship=>![...ship.cells].every(key=>board.hits.has(key))).map(ship=>ship.length);}
  boardPayload(board,reveal){const cells=[];for(let row=0;row<this.size;row+=1)for(let column=0;column<this.size;column+=1){const key=battleKey([row,column]),shipId=board.ships.findIndex(item=>item.cells.has(key)),ship=shipId>=0?board.ships[shipId]:null,sunk=Boolean(ship&&[...ship.cells].every(item=>board.hits.has(item)));cells.push({row,column,shot:board.shots.has(key),hit:board.hits.has(key),sunk,ship:reveal?Boolean(ship):sunk,shipId:reveal||sunk?shipId:null});}return cells;}
  outcome(outcome){return{cell:outcome.cell,hit:outcome.hit,sunk:outcome.sunk,sunkLength:outcome.sunkLength};}
  act(action,payload={}){if(action==="randomize_fleet"){if(this.phase!=="placement")throw new Error("fleet placement is already locked");this.player=battleFleet(this.size,this.lengths);return;}if(action==="set_board_size"){if(this.phase!=="placement")throw new Error("board size can only change during placement");const size=Number(payload.boardSize);if(!Number.isInteger(size)||!BATTLE_FLEETS[size])throw new Error("boardSize must be 10, 12, or 15");this.configure(size);return;}if(action==="rotate_ship"){if(this.phase!=="placement")throw new Error("ships can only rotate during placement");rotateBattleShip(this.player,Number(payload.shipId),this.size);return;}if(action==="start_battle"){if(this.phase!=="placement")throw new Error("battle has already started");this.phase="player_turn";return;}if(action!=="fire"||this.phase!=="player_turn")throw new Error("fire only when the battle is active");const cell=[Number(payload.row),Number(payload.column)],playerOutcome=battleFire(this.enemy,cell,this.size);observeBattle(this.advisor,playerOutcome);this.turn+=1;const event={turn:this.turn,playerShot:this.outcome(playerOutcome),aiShot:null};if(!this.remaining(this.enemy).length){this.phase="finished";this.winner="player";this.history.push(event);return;}const decision=chooseBattleShot(this.ai,this.size),aiOutcome=battleFire(this.player,decision.cell,this.size);observeBattle(this.ai,aiOutcome);event.aiShot=this.outcome(aiOutcome);this.lastAiAnalysis=decision.analysis;this.history.push(event);if(!this.remaining(this.player).length){this.phase="finished";this.winner="ai";}}
  snapshot(){const density=battleDensity(this.advisor,this.size),suggestion=this.phase==="player_turn"?chooseBattleShot(this.advisor,this.size,false).cell:null,finished=this.phase==="finished";return{gameId:"battleship",phase:this.phase,turn:this.turn,winner:this.winner,boardSize:this.size,boardSizes:Object.keys(BATTLE_FLEETS).map(Number),shipLengths:this.lengths,fleet:this.player.ships.map((ship,id)=>({id,length:ship.length,orientation:battleOrientation(ship)})),playerBoard:this.boardPayload(this.player,true),enemyBoard:this.boardPayload(this.enemy,finished),playerShipsRemaining:this.remaining(this.player),enemyShipsRemaining:this.remaining(this.enemy),suggestedShot:suggestion,candidatePlacementCount:density.candidatePlacements,lastAiAnalysis:this.lastAiAnalysis,history:this.history,legalActions:this.phase==="placement"?["randomize_fleet","set_board_size","rotate_ship","start_battle"]:this.phase==="player_turn"?["fire"]:[],informationSet:{misses:[...this.advisor.misses].map(battleCell),unresolvedHits:[...this.advisor.hits].map(battleCell),sunkCells:[...this.advisor.sunk].map(battleCell),remainingShipLengths:this.advisor.remaining,candidatePlacementCount:density.candidatePlacements}};}
}

class MastermindSession {
  constructor(options = {}) { this.length=4; this.symbols=[0,1,2,3,4,5,6,7,8,9]; this.maxAttempts=10; this.allCodes=[]; for(const a of this.symbols)for(const b of this.symbols)for(const c of this.symbols)for(const d of this.symbols)if(new Set([a,b,c,d]).size===4)this.allCodes.push([a,b,c,d]); this.gamesCompleted=0;this.gamesSolved=0;this.totalSolvedAttempts=0;this.bestAttempts=null;this.start(); }
  start() { this.secret=[...this.allCodes[Math.floor(Math.random()*this.allCodes.length)]]; this.candidates=[...this.allCodes]; this.attempts=[]; this.phase="playing"; this.result=null; }
  feedback(guess, secret) { const exact=guess.reduce((n,v,i)=>n+(v===secret[i]?1:0),0); const shared=guess.filter(v=>secret.includes(v)).length; return [exact,shared-exact]; }
  sample(values,limit){if(values.length<=limit)return values;return Array.from({length:limit},(_,index)=>values[Math.floor(index*values.length/limit)]);}
  suggestion() { if(!this.candidates.length)return null;if(this.candidates.length===1)return{guess:this.candidates[0],worstCaseRemaining:1,expectedRemaining:1,evaluatedGuesses:1,exactSearch:true};let pool;if(this.candidates.length===this.allCodes.length){pool=[[0,1,2,3]];}else if(this.candidates.length<=160){pool=this.allCodes;}else if(this.candidates.length<=800){pool=[...new Map([...this.candidates,...this.sample(this.allCodes,360)].map(code=>[code.join(""),code])).values()];}else{pool=[...new Map([...this.sample(this.candidates,280),...this.sample(this.allCodes,120)].map(code=>[code.join(""),code])).values()];}const candidateKeys=new Set(this.candidates.map(code=>code.join("")));let best=null;for(const guess of pool){const counts={};for(const candidate of this.candidates){const key=this.feedback(guess,candidate).join(",");counts[key]=(counts[key]||0)+1;}const sizes=Object.values(counts),worst=Math.max(...sizes),expected=sizes.reduce((sum,size)=>sum+size*size,0)/this.candidates.length,key=[worst,expected,candidateKeys.has(guess.join(""))?0:1,...guess];if(!best||key.some((value,index)=>value<best.key[index]&&key.slice(0,index).every((prior,i)=>prior===best.key[i]))){best={guess,worstCaseRemaining:worst,expectedRemaining:expected,evaluatedGuesses:pool.length,exactSearch:pool.length===this.allCodes.length,key};}}delete best.key;return best; }
  act(action,payload={}) { if(action==="new_game"){this.start();return;} if(action!=="submit_guess"||this.phase!=="playing")throw new Error("submit a guess while the game is active"); const guess=(payload.guess||[]).map(Number); if(guess.length!==4||guess.some(v=>!Number.isInteger(v))||new Set(guess).size!==4||guess.some(v=>!this.symbols.includes(v)))throw new Error("guess must contain four distinct digits from 0 to 9"); const beforeCandidates=this.candidates.length,[exact,partial]=this.feedback(guess,this.secret);this.candidates=this.candidates.filter(candidate=>{const f=this.feedback(guess,candidate);return f[0]===exact&&f[1]===partial;});const afterCandidates=this.candidates.length;this.attempts.push({guess,exact,partial,beforeCandidates,afterCandidates,eliminated:beforeCandidates-afterCandidates}); if(exact===4){this.phase="finished";this.result={won:true,secret:this.secret,attempts:this.attempts.length};this.gamesCompleted+=1;this.gamesSolved+=1;this.totalSolvedAttempts+=this.attempts.length;this.bestAttempts=this.bestAttempts===null?this.attempts.length:Math.min(this.bestAttempts,this.attempts.length);}else if(this.attempts.length>=this.maxAttempts){this.phase="finished";this.result={won:false,secret:this.secret,attempts:this.attempts.length};this.gamesCompleted+=1;} }
  snapshot() { const analysis=this.phase==="playing"?this.suggestion():null; return {gameId:"mastermind",phase:this.phase,length:4,symbols:this.symbols,maxAttempts:10,attemptsUsed:this.attempts.length,attempts:this.attempts,candidateCount:this.candidates.length,initialCandidateCount:this.allCodes.length,suggestedGuess:analysis?analysis.guess:null,suggestionAnalysis:analysis?{worstCaseRemaining:analysis.worstCaseRemaining,expectedRemaining:analysis.expectedRemaining,evaluatedGuesses:analysis.evaluatedGuesses,exactSearch:analysis.exactSearch}:null,result:this.result,legalActions:this.phase==="playing"?["submit_guess"]:["new_game"],sessionStats:{gamesCompleted:this.gamesCompleted,gamesSolved:this.gamesSolved,averageSolvedAttempts:this.gamesSolved?this.totalSolvedAttempts/this.gamesSolved:null,bestAttempts:this.bestAttempts},strategyScope:"bounded_one_step_minimax_then_expected_partition",informationSet:{candidateCount:this.candidates.length,candidatePreview:this.candidates.slice(0,8),feedbackHistory:this.attempts}}; }
}

function createSession(gameId, options={}) {
  const factories={cases:CaseSession,worm:WormSession,pirates:PirateSession,"kuhn-poker":PokerSession,"e-card":ECardSession,"restricted-rps":RPSSession,blackjack:BlackjackSession,"liars-dice":LiarDiceSession,mastermind:MastermindSession,battleship:BattleshipSession};
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
