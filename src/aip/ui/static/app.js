const $ = (selector) => document.querySelector(selector);
let language = localStorage.getItem("aip-language") || "zh";
let money = new Intl.NumberFormat(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: 2 });
let sessionId = null;
let currentState = null;
let currentGameId = null;
let lobbyGames = [];
let pirateDraft = [];

const copy = {
  zh: {
    brandName: "非对称博弈实验室", localOnly: "仅在本机运行",
    heroLine1: "把推理变成一场", heroLine2: "真正可以玩的博弈",
    heroCopy: "选择一个实验。你做决定，系统隐藏信息、扮演对手，并在关键时刻揭示概率与代价。",
    backLobby: "← 返回大厅", restart: "重新开始", restartCouncil: "重新召开议会",
    caseEyebrow: "CASE 01 · 风险与谈判", caseTitle: "命运之箱",
    wormEyebrow: "CASE 02 · 隐藏状态追踪", wormTitle: "移动虫穴",
    pirateEyebrow: "CASE 03 · 逆向归纳与联盟", pirateTitle: "海盗议会",
    pokerEyebrow: "CASE 04 · 私有信息与诈唬", pokerTitle: "库恩扑克",
    restartMatch: "重新开始比赛", handNumber: "当前牌局", yourScore: "你的净筹码",
    potSize: "底池", aiScore: "AI 净筹码", strategyAi: "策略型 AI", you: "你",
    yourInformationSet: "你的信息集", quickRules: "快速规则",
    pokerRules: "双方先各投入 1。下注为 1；跟注后比牌，弃牌则直接输。K 最大、J 最小。AI 会按概率诈唬，所以同一种动作不总代表同一张牌。",
    eCardEyebrow: "CASE 05 · 非对称收益与混合策略", eCardTitle: "E-Card 皇帝牌",
    currentDuel: "本轮对决", emperor: "皇帝", citizen: "市民", slave: "奴隶",
    eCardYourScore: "你的得分", eCardAiScore: "AI 得分",
    duelHistory: "公开对局记录",
    eCardPayoff: "皇帝获胜得 1 分，奴隶获胜得 5 分。双方市民相撞时只弃掉两张牌并继续本轮。",
    prizePool: "奖金池", round: "回合", decisionPanel: "决策仪表",
    emptyInsight: "银行家报价后，这里会显示期望值、风险和模型建议。",
    gameHistory: "博弈记录", liveChecks: "实时检查次数", possiblePositions: "仍可能的位置",
    strategyHint: "保证策略提示", guaranteedSequence: "保证抓捕序列",
    wormStrategyCopy: "只要从第一步开始严格执行该序列，即使虫子选择最不利的移动，也能在序列结束前抓到。",
    searchHistory: "搜索记录", availableGold: "可分配金币", votesNeeded: "通过所需票数",
    unallocated: "尚未分配", yourProposal: "你的提案", submitProposal: "提交提案并投票",
    pirateInstruction: "你是最资深的 A。为每名海盗分配金币，然后让所有人同时投票。",
    backwardBenchmark: "逆向归纳基准", bankerOffer: "银行家报价", acceptOffer: "接受报价",
    rejectOffer: "拒绝，继续开箱", operationFailed: "操作失败",
  },
  en: {
    brandName: "Asymmetric Games Lab", localOnly: "Running locally",
    heroLine1: "Turn reasoning into", heroLine2: "games you can actually play",
    heroCopy: "Choose an experiment. You decide; the system hides information, plays the opposition, and reveals probability and cost at decisive moments.",
    backLobby: "← Back to lobby", restart: "New game", restartCouncil: "New council",
    caseEyebrow: "CASE 01 · RISK & NEGOTIATION", caseTitle: "Cases of Fate",
    wormEyebrow: "CASE 02 · HIDDEN-STATE TRACKING", wormTitle: "The Moving Worm",
    pirateEyebrow: "CASE 03 · BACKWARD INDUCTION & COALITIONS", pirateTitle: "Pirate Council",
    pokerEyebrow: "CASE 04 · PRIVATE INFORMATION & BLUFFING", pokerTitle: "Kuhn Poker",
    restartMatch: "Restart match", handNumber: "Current hand", yourScore: "Your net chips",
    potSize: "Pot", aiScore: "AI net chips", strategyAi: "Strategy AI", you: "You",
    yourInformationSet: "Your information set", quickRules: "Quick rules",
    pokerRules: "Both players ante 1. A bet costs 1; a call leads to showdown, while a fold loses immediately. K is high and J is low. The AI bluffs probabilistically, so one action never reveals one card with certainty.",
    eCardEyebrow: "CASE 05 · ASYMMETRIC PAYOFFS & MIXED STRATEGY", eCardTitle: "E-Card",
    currentDuel: "Duel", emperor: "Emperor", citizen: "Citizen", slave: "Slave",
    eCardYourScore: "Your score", eCardAiScore: "AI score",
    duelHistory: "Public duel history",
    eCardPayoff: "An Emperor win scores 1; a Slave win scores 5. Citizen versus Citizen discards both cards and continues the round.",
    prizePool: "Prize board", round: "Round", decisionPanel: "Decision dashboard",
    emptyInsight: "Expected value, risk, and model guidance appear after the banker's offer.",
    gameHistory: "Game history", liveChecks: "Live check count", possiblePositions: "Possible positions",
    strategyHint: "Guaranteed-strategy hint", guaranteedSequence: "Guaranteed capture sequence",
    wormStrategyCopy: "Follow this sequence from the first move and even a worst-case worm must be caught before it ends.",
    searchHistory: "Search history", availableGold: "Gold available", votesNeeded: "Votes required",
    unallocated: "Unallocated", yourProposal: "Your proposal", submitProposal: "Submit proposal and vote",
    pirateInstruction: "You are A, the most senior pirate. Allocate gold to every pirate, then call a simultaneous vote.",
    backwardBenchmark: "Backward-induction benchmark", bankerOffer: "Banker's offer", acceptOffer: "Deal",
    rejectOffer: "No deal — keep opening", operationFailed: "Action failed",
  },
};

const gamesCopy = {
  zh: {
    cases: ["命运之箱", "从 26 个密封箱中保留一个，在不断缩小的风险中与银行家谈判。", "单人 · 决策与风险"],
    worm: ["移动虫穴", "面对无随机性的智能虫子；错误方法永远无法靠运气抓到它。", "单人 · 对抗搜索"],
    pirates: ["海盗议会", "亲自分配 100 枚金币，面对会做逆向归纳的理性海盗投票。", "单人 · 人机投票"],
    "kuhn-poker": ["库恩扑克", "在三张牌的极简牌局中读取信号、抓诈唬，并与混合策略 AI 连续对战。", "单人 · 隐藏手牌与诈唬"],
    "e-card": ["E-Card 皇帝牌", "轮流扮演皇帝方与奴隶方，在非对称收益下猜测 AI 的隐藏出牌时机。", "单人 · 非对称混合策略"],
    "liars-dice": ["骗子骰子", "隐藏手牌、公开叫价与诈唬识别。", "本地多人 · 即将开放"],
    auction: ["百元全支付拍卖", "用公开价格争夺主导权，并观察联盟与背叛。", "本地多人 · 即将开放"],
  },
  en: {
    cases: ["Cases of Fate", "Keep one of 26 sealed cases and negotiate with the banker as uncertainty narrows.", "Solo · Risk & decision"],
    worm: ["The Moving Worm", "Face a deterministic adversary: a wrong method can never win by luck.", "Solo · Adversarial search"],
    pirates: ["Pirate Council", "Allocate 100 coins and face rational pirates who reason backward before voting.", "Solo · Human vs AI vote"],
    "kuhn-poker": ["Kuhn Poker", "Read signals, catch bluffs, and battle a mixed-strategy AI in the classic three-card game.", "Solo · Hidden cards & bluffing"],
    "e-card": ["E-Card", "Alternate between Emperor and Slave, reading the AI's hidden timing under asymmetric rewards.", "Solo · Asymmetric mixed strategy"],
    "liars-dice": ["Liar's Dice", "Private hands, public bids, and bluff inference.", "Local multiplayer · Coming soon"],
    auction: ["100-Unit All-Pay Auction", "Fight for leadership through public prices, alliances, and defection.", "Local multiplayer · Coming soon"],
  },
};

function tr(key) { return copy[language][key] ?? key; }

function applyLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.title = language === "zh" ? "AIP · 非对称博弈实验室" : "AIP · Asymmetric Games Lab";
  money = new Intl.NumberFormat(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: 2 });
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = tr(element.dataset.i18n);
  });
  $("#languageZh").classList.toggle("active", language === "zh");
  $("#languageEn").classList.toggle("active", language === "en");
  renderLobby();
  if (currentState) render();
}

function setLanguage(nextLanguage) {
  language = nextLanguage;
  localStorage.setItem("aip-language", language);
  applyLanguage();
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || tr("operationFailed"));
  return data;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  window.setTimeout(() => toast.classList.add("hidden"), 2400);
}

async function loadLobby() {
  const { games } = await request("/api/games");
  lobbyGames = games;
  renderLobby();
}

function renderLobby() {
  if (!lobbyGames.length) return;
  $("#gameGrid").innerHTML = lobbyGames.map((game, index) => {
    const localized = gamesCopy[language][game.id] || [game.title, game.summary, game.playerMode];
    return `
    <button class="game-card" data-game="${game.id}" ${game.available ? "" : "disabled"}>
      <span class="game-index">0${index + 1}</span>
      <h2>${localized[0]}</h2>
      <p>${localized[1]}</p>
      <span class="game-mode">${localized[2]}</span>
    </button>
  `; }).join("");
  document.querySelectorAll(".game-card:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => startGame(button.dataset.game));
  });
}

async function startGame(gameId = "cases", options = {}) {
  try {
    const gameOptions = gameId === "cases"
      ? { riskTolerance: 100000, ...options }
      : options;
    const result = await request("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ gameId, options: gameOptions }),
    });
    sessionId = result.sessionId;
    currentState = result.state;
    currentGameId = gameId;
    if (gameId === "pirates") pirateDraft = currentState.pirates.map(() => 0);
    $("#lobbyView").classList.add("hidden");
    $("#gameView").classList.toggle("hidden", gameId !== "cases");
    $("#wormView").classList.toggle("hidden", gameId !== "worm");
    $("#pirateView").classList.toggle("hidden", gameId !== "pirates");
    $("#pokerView").classList.toggle("hidden", gameId !== "kuhn-poker");
    $("#eCardView").classList.toggle("hidden", gameId !== "e-card");
    render();
  } catch (error) {
    showToast(error.message);
  }
}

async function act(action, payload = {}) {
  try {
    const result = await request(`/api/sessions/${sessionId}/actions`, {
      method: "POST",
      body: JSON.stringify({ action, payload }),
    });
    currentState = result.state;
    render();
  } catch (error) {
    showToast(error.message);
  }
}

function render() {
  if (currentState.gameId === "e-card") {
    renderECard();
    return;
  }
  if (currentState.gameId === "kuhn-poker") {
    renderPoker();
    return;
  }
  if (currentState.gameId === "pirates") {
    renderPirates();
    return;
  }
  if (currentState.gameId === "worm") {
    renderWorm();
    return;
  }
  const state = currentState;
  $("#roundNumber").textContent = state.phase === "choose" ? "—" : state.round;
  $("#remainingCount").textContent = state.prizeBoard.filter((prize) => prize.remaining).length;
  const instructions = language === "zh" ? {
    choose: "请选择一个属于你的密封箱",
    opening: `再打开 ${state.opensRemaining} 个箱子，银行家随后报价`,
    offer: "银行家正在等待你的决定",
    finished: `本局结束 · 你获得 ${formatMoney(state.payout)}`,
  } : {
    choose: "Choose one sealed case to keep",
    opening: `Open ${state.opensRemaining} more case(s) before the next offer`,
    offer: "The banker is waiting for your decision",
    finished: `Game over · You received ${formatMoney(state.payout)}`,
  };
  $("#instruction").textContent = instructions[state.phase];
  $("#chosenStrip").textContent = state.chosenCase
    ? (language === "zh"
      ? `你的密封箱：${state.chosenCase} 号${state.phase === "finished" ? ` · ${formatMoney(findCase(state.chosenCase).value)}` : ""}`
      : `Your sealed case: No. ${state.chosenCase}${state.phase === "finished" ? ` · ${formatMoney(findCase(state.chosenCase).value)}` : ""}`)
    : (language === "zh" ? "你的箱子尚未选择" : "You have not chosen a case yet");

  $("#caseGrid").innerHTML = state.cases.map((item) => {
    const label = item.status === "opened" ? formatMoney(item.value) : item.id;
    return `<button class="case ${item.status}" data-case="${item.id}" ${caseDisabled(item) ? "disabled" : ""}>${label}</button>`;
  }).join("");
  document.querySelectorAll(".case:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => {
      const action = state.phase === "choose" ? "choose_case" : "open_case";
      act(action, { caseId: Number(button.dataset.case) });
    });
  });

  $("#prizeBoard").innerHTML = state.prizeBoard.map((prize) =>
    `<div class="prize ${prize.remaining ? "" : "gone"}">${formatMoney(prize.value)}</div>`
  ).join("");
  renderMetrics(state.metrics);
  renderHistory(state.history);
  $("#offerModal").classList.toggle("hidden", state.phase !== "offer");
  if (state.phase === "offer") {
    $("#offerValue").textContent = formatMoney(state.offer);
    const remaining = state.prizeBoard.filter((prize) => prize.remaining).length;
    $("#offerContext").textContent = language === "zh"
      ? `剩余 ${remaining} 个可能金额。模型保留价为 ${formatMoney(state.metrics.certaintyEquivalent)}。`
      : `${remaining} prize values remain. The model's reservation value is ${formatMoney(state.metrics.certaintyEquivalent)}.`;
  }
}

function renderECard() {
  const state = currentState;
  const cardNames = language === "zh"
    ? { emperor: "皇帝", citizen: "市民", slave: "奴隶" }
    : { emperor: "Emperor", citizen: "Citizen", slave: "Slave" };
  const roleName = (role) => language === "zh" ? `${cardNames[role]}方` : `${cardNames[role]} side`;
  $("#ecardRound").textContent = state.roundNumber;
  $("#ecardDuel").textContent = `${state.duelNumber} / 5`;
  $("#ecardPlayerScore").textContent = state.playerScore;
  $("#ecardAiScore").textContent = state.aiScore;
  $("#ecardPlayerRole").textContent = roleName(state.playerRole);
  $("#ecardAiRole").textContent = roleName(state.aiRole);
  $("#ecardHiddenHand").innerHTML = Array.from({length: state.opponentCardsLeft}, () => '<div class="tiny-card card-back">?</div>').join("");
  $("#ecardHand").innerHTML = state.playerHand.map((item) => `
    <button class="ecard-card ${item.card}" data-ecard="${item.card}" ${state.phase !== "playing" ? "disabled" : ""}>
      <span>${cardNames[item.card]}</span><b>×${item.count}</b>
    </button>`).join("");
  document.querySelectorAll("[data-ecard]:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => act("play_card", {card: button.dataset.ecard}));
  });

  const reveal = state.lastReveal;
  $("#ecardReveal").innerHTML = reveal
    ? `<div class="mini-card ${reveal.playerCard}">${cardNames[reveal.playerCard]}</div><strong>VS</strong><div class="mini-card ${reveal.aiCard}">${cardNames[reveal.aiCard]}</div>`
    : '<div class="mini-card card-back">?</div><strong>VS</strong><div class="mini-card card-back">?</div>';
  $("#ecardInstruction").textContent = state.phase === "finished"
    ? (language === "zh" ? "本轮结束：双方下一轮交换阵营" : "Round over: sides swap next round")
    : reveal?.outcome === "draw"
      ? (language === "zh" ? "市民相撞，记住已消耗的牌并再次选择" : "Citizens tied. Track the discarded cards and choose again")
      : (language === "zh" ? "选择一张牌，双方将同时揭晓" : "Choose a card; both choices are revealed together");

  $("#ecardHistory").innerHTML = state.history.length
    ? state.history.map((item) => `<div><span>${item.duel}</span><b>${cardNames[item.playerCard]}</b><em>VS</em><b>${cardNames[item.aiCard]}</b><small>${item.outcome === "draw" ? (language === "zh" ? "平局" : "Draw") : item.outcome === "player" ? (language === "zh" ? "你胜" : "You win") : (language === "zh" ? "AI 胜" : "AI wins")}</small></div>`).join("")
    : `<p>${language === "zh" ? "尚无公开出牌。" : "No public plays yet."}</p>`;
  const possible = state.informationSet.possibleOpponentCards.map((card) => cardNames[card]).join(language === "zh" ? "或" : " or ");
  $("#ecardInformation").textContent = language === "zh"
    ? `AI 还剩 ${state.informationSet.opponentCardsLeft} 张牌，可能出的牌型为${possible}。它的实际选择在你出牌前保持隐藏。`
    : `The AI has ${state.informationSet.opponentCardsLeft} cards left and may play ${possible}. Its actual choice stays hidden until yours is committed.`;

  $("#ecardResult").classList.toggle("hidden", state.phase !== "finished");
  if (state.phase === "finished") {
    const won = state.result.winner === "player";
    $("#ecardResult").className = `ecard-result ${won ? "win" : "loss"}`;
    $("#ecardResult").innerHTML = `<strong>${won ? (language === "zh" ? "你赢得本轮" : "You win the round") : (language === "zh" ? "AI 赢得本轮" : "AI wins the round")} · +${state.result.points}</strong><p>${language === "zh" ? `${roleName(state.result.winnerRole)}在第 ${state.result.decisiveDuel} 次对决获胜。` : `${roleName(state.result.winnerRole)} prevailed on duel ${state.result.decisiveDuel}.`}</p><button data-ecard-next>${language === "zh" ? "交换阵营，进入下一轮" : "Swap sides and play next round"}</button>`;
    const nextButton = $("[data-ecard-next]");
    if (nextButton) nextButton.addEventListener("click", () => act("next_round"));
  }
}

function renderPoker() {
  const state = currentState;
  const names = language === "zh"
    ? { check: "过牌", bet: "下注", fold: "弃牌", call: "跟注", next_hand: "下一局", player: "你", ai: "AI" }
    : { check: "Check", bet: "Bet", fold: "Fold", call: "Call", next_hand: "Next hand", player: "You", ai: "AI" };
  $("#pokerHand").textContent = state.handNumber;
  $("#pokerPlayerScore").textContent = signed(state.playerScore);
  $("#pokerAiScore").textContent = signed(state.aiScore);
  $("#pokerPot").textContent = state.pot;
  $("#playerCard").textContent = state.playerCard;
  $("#aiCard").textContent = state.aiCard || "?";
  $("#aiCard").classList.toggle("card-back", !state.aiCard);
  $("#playerPosition").textContent = language === "zh"
    ? (state.playerIsFirst ? "先手" : "后手")
    : (state.playerIsFirst ? "First to act" : "Second to act");
  $("#aiPosition").textContent = language === "zh"
    ? (state.playerIsFirst ? "后手" : "先手")
    : (state.playerIsFirst ? "Second to act" : "First to act");
  $("#pokerActionLog").innerHTML = state.history.length
    ? state.history.map((item) => `<span>${names[item.actor]} · ${names[item.action]}</span>`).join('<b>→</b>')
    : `<span>${language === "zh" ? "等待你的决定" : "Waiting for your decision"}</span>`;
  $("#pokerActions").innerHTML = state.legalActions.map((action) =>
    `<button class="${action === "fold" ? "poker-fold" : ""}" data-poker-action="${action}">${names[action]}</button>`
  ).join("");
  document.querySelectorAll("[data-poker-action]").forEach((button) => {
    button.addEventListener("click", () => act(button.dataset.pokerAction));
  });
  const facingBet = state.legalActions.includes("call");
  $("#pokerInstruction").textContent = state.phase === "finished"
    ? (language === "zh" ? "本局信息已经揭晓" : "The hand is revealed")
    : facingBet
      ? (language === "zh" ? "AI 下注了：它拿着 K，还是在用 J 诈唬？" : "The AI bet: is it holding K, or bluffing with J?")
      : (language === "zh" ? "利用你的私牌与公开行动做决定" : "Decide from your private card and the public actions");
  $("#pokerInformation").textContent = language === "zh"
    ? `你确定自己拿到 ${state.informationSet.privateCard}；因此 AI 只可能持有 ${state.informationSet.possibleOpponentCards.join(" 或 ")}。公开行动不会直接揭示是哪一张。`
    : `You know you hold ${state.informationSet.privateCard}; therefore the AI can only hold ${state.informationSet.possibleOpponentCards.join(" or ")}. Public actions do not identify which one with certainty.`;
  $("#pokerResult").classList.toggle("hidden", state.phase !== "finished");
  if (state.phase === "finished") {
    const won = state.result.winner === "player";
    $("#pokerResult").className = `poker-result ${won ? "win" : "loss"}`;
    const reason = language === "zh" ? {
      player_folded: "你弃牌，AI 无需亮牌便拿下底池。",
      ai_folded: "AI 弃牌，你的下注成功拿下底池。",
      both_checked: "双方过牌后直接比牌。",
      bet_called: "下注被跟注，双方摊牌。",
    }[state.result.reason] : {
      player_folded: "You folded, so the AI took the pot without a showdown.",
      ai_folded: "The AI folded, so your bet took the pot.",
      both_checked: "Both players checked and went to showdown.",
      bet_called: "The bet was called and both cards were revealed.",
    }[state.result.reason];
    const bluff = state.result.aiBluffed
      ? (language === "zh" ? " AI 这次确实在用 J 诈唬。" : " The AI really was bluffing with J.") : "";
    $("#pokerResult").innerHTML = `<strong>${won ? (language === "zh" ? "你赢了" : "You win") : (language === "zh" ? "AI 赢了" : "AI wins")} · ${signed(state.result.playerDelta)}</strong><p>${reason}${bluff}</p>`;
  }
}

function signed(value) { return value > 0 ? `+${value}` : `${value}`; }

function renderPirates() {
  const state = currentState;
  const proposal = state.proposal || (pirateDraft.length ? pirateDraft : state.pirates.map(() => 0));
  $("#pirateTotalGold").textContent = state.totalGold;
  $("#pirateVotesNeeded").textContent = `${state.votesRequired} / ${state.pirateCount}`;
  $("#pirateGrid").innerHTML = state.pirates.map((pirate, index) => `
    <div class="pirate-card ${pirate.isProposer ? "proposer" : ""}">
      <div class="pirate-avatar">${pirate.name}</div>
      <strong>${language === "zh" ? "海盗" : "Pirate"} ${pirate.name}</strong>
      <div class="pirate-role">${pirate.isProposer
        ? (language === "zh" ? "提案者 · 你" : "Proposer · You")
        : (language === "zh" ? "理性投票者" : "Rational voter")}</div>
      <label for="pirate-gold-${index}">${language === "zh" ? "分配金币" : "Gold allocation"}</label>
      <input id="pirate-gold-${index}" class="pirate-gold-input" data-index="${index}"
        type="number" min="0" max="${state.totalGold}" step="1" value="${proposal[index]}"
        ${state.phase === "finished" ? "disabled" : ""} />
    </div>
  `).join("");
  document.querySelectorAll(".pirate-gold-input").forEach((input) => {
    input.addEventListener("input", updatePirateBudget);
  });
  updatePirateBudget();
  $("#pirateResult").classList.toggle("hidden", state.phase !== "finished");
  if (state.phase !== "finished") return;

  $("#pirateVerdict").className = `pirate-verdict ${state.passed ? "pass" : "fail"}`;
  $("#pirateVerdict").textContent = language === "zh"
    ? (state.passed
      ? `提案通过：${state.yesVotes} 票赞成，你活了下来。`
      : `提案被否决：只有 ${state.yesVotes} 票赞成，提案者 A 被处决。`)
    : (state.passed
      ? `Proposal passed with ${state.yesVotes} yes votes. You survive.`
      : `Proposal rejected with only ${state.yesVotes} yes votes. Pirate A is executed.`);
  $("#pirateVotes").innerHTML = state.votes.map((vote) => `
    <div class="vote-card ${vote.supports ? "yes" : "no"}">
      <strong>${vote.pirate} · ${vote.supports ? (language === "zh" ? "赞成" : "YES") : (language === "zh" ? "反对" : "NO")}</strong>
      <p>${language === "zh"
        ? `获得 ${vote.offered} 枚；拒绝后${vote.rejectionAlive ? `可活并获得 ${vote.rejectionGold} 枚` : "会死亡"}。`
        : `Offered ${vote.offered}; after rejection, ${vote.rejectionAlive ? `survives with ${vote.rejectionGold}` : "dies"}.`}</p>
      <p>${pirateVoteReason(vote)}</p>
    </div>
  `).join("");
  const optimal = state.pirates.map((pirate, index) => `${pirate.name}: ${state.optimalAllocation[index]}`).join(language === "zh" ? "，" : ", ");
  $("#pirateOptimal").textContent = language === "zh"
    ? (state.matchesOptimal
      ? `你找到了选定规则下的均衡提案：${optimal}。`
      : `理论最优提案为 ${optimal}。它用最低成本购买足够票数，并让 A 保留最多金币。`)
    : (state.matchesOptimal
      ? `You found the equilibrium proposal under these rules: ${optimal}.`
      : `The theoretical optimum is ${optimal}. It buys the required votes at minimum cost and maximizes A's gold.`);
}

function updatePirateBudget() {
  if (!currentState || currentState.gameId !== "pirates") return;
  const inputs = [...document.querySelectorAll(".pirate-gold-input")];
  const used = inputs.reduce((sum, input) => sum + Math.max(0, Number(input.value) || 0), 0);
  pirateDraft = inputs.map((input) => Math.max(0, Number(input.value) || 0));
  const left = currentState.totalGold - used;
  $("#pirateGoldLeft").textContent = left;
  $("#pirateGoldLeft").style.color = left === 0 ? "var(--gold-soft)" : "#efb0aa";
  $("#submitPirateProposal").disabled = currentState.phase !== "proposing" || left !== 0;
}

function pirateVoteReason(vote) {
  const reasons = language === "zh" ? {
    proposer: "提案者支持自己的可行提案。",
    survival: "接受可以活命，而否决后会死亡。",
    more_gold: "接受得到的金币比否决后的延续结果更多。",
    equal_accepted: "规则允许在金币相同时投赞成票。",
    equal_rejected: "金币相同不足以收买他，因此投反对票。",
    less_gold: "接受得到的金币少于否决后的延续结果。",
  } : {
    proposer: "The proposer supports their own feasible proposal.",
    survival: "Acceptance means survival; rejection means death.",
    more_gold: "The offer beats the continuation payoff after rejection.",
    equal_accepted: "The configured rule permits a yes vote when gold is equal.",
    equal_rejected: "Equal gold is not enough to buy this pirate's vote.",
    less_gold: "The offer is below the continuation payoff after rejection.",
  };
  return reasons[vote.reasonCode];
}

function renderWorm() {
  const state = currentState;
  $("#wormTurn").textContent = state.turn;
  $("#possibleHoles").textContent = state.possiblePositions.join(" · ") || (language === "zh" ? "已锁定" : "Locked");
  $("#wormHint").textContent = state.phase === "finished"
    ? (language === "zh" ? "已成功抓捕" : "Captured")
    : state.suggestedHole
      ? (language === "zh" ? `检查 ${state.suggestedHole} 号洞` : `Check hole ${state.suggestedHole}`)
      : state.followedStrategy
        ? (language === "zh" ? "序列已完成" : "Sequence complete")
        : (language === "zh" ? "已偏离保证序列" : "Guaranteed sequence lost");
  $("#wormHeadline").textContent = state.phase === "finished"
    ? (language === "zh" ? `抓到了！第 ${state.turn} 次检查成功` : `Captured on check ${state.turn}`)
    : (language === "zh" ? "虫子仍在移动" : "The worm is still moving");
  $("#wormInstruction").textContent = state.phase === "finished"
    ? (language === "zh" ? "重新开始可再次挑战智能对手。" : "Start again to challenge the adversary once more.")
    : (language === "zh"
      ? "系统始终选择所有合法轨迹中最难抓的一条；没有随机位置，也不能靠运气撞中。"
      : "The system always preserves the hardest legal escape path. There is no random position and no lucky capture.");

  $("#holeRow").innerHTML = state.holes.map((hole) => `
    <button class="hole ${hole.possible ? "" : "impossible"} ${hole.worm ? "worm-found" : ""}"
      data-hole="${hole.id}" ${state.phase === "finished" ? "disabled" : ""}
      aria-label="${language === "zh" ? `检查 ${hole.id} 号洞` : `Check hole ${hole.id}`}">${hole.worm ? "●" : hole.id}</button>
  `).join("");
  document.querySelectorAll(".hole:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => act("check_hole", { holeId: Number(button.dataset.hole) }));
  });

  $("#strategySequence").innerHTML = state.strategy.map((hole, index) => {
    const status = index < state.turn ? "done" : index === state.turn && state.followedStrategy ? "next" : "";
    return `<span class="strategy-step ${status}">${hole}</span>`;
  }).join("");
  $("#wormHistory").innerHTML = state.history.slice().reverse().map((item) =>
    `<li>${language === "zh" ? `第 ${item.turn} 次检查 ${item.holeId} 号洞：` : `Check ${item.turn}, hole ${item.holeId}: `}${item.result === "caught"
      ? (language === "zh" ? "所有轨迹均被封锁，保证抓到" : "all legal paths are blocked — guaranteed capture")
      : (language === "zh" ? "智能对手仍有合法逃脱轨迹" : "the adversary still has a legal escape path")}</li>`
  ).join("");
}

function caseDisabled(item) {
  if (currentState.phase === "choose") return item.status !== "closed";
  if (currentState.phase === "opening") return item.status !== "closed";
  return true;
}

function renderMetrics(metrics) {
  $("#emptyInsight").classList.toggle("hidden", Boolean(metrics));
  $("#metrics").classList.toggle("hidden", !metrics);
  if (!metrics) return;
  const labels = language === "zh" ? {
    ev: "剩余期望值", ce: "确定性等价", ratio: "报价 / 期望值",
    beat: "箱内金额超过报价", volatility: "剩余波动", recommendation: "模型建议：",
    deal: "接受报价", noDeal: "继续开箱",
  } : {
    ev: "Expected value", ce: "Certainty equivalent", ratio: "Offer / expected value",
    beat: "Chance case beats offer", volatility: "Remaining volatility", recommendation: "Model guidance: ",
    deal: "Take the deal", noDeal: "Keep opening",
  };
  $("#metrics").innerHTML = `
    <div class="metric"><span>${labels.ev}</span><strong>${formatMoney(metrics.expectedValue)}</strong></div>
    <div class="metric"><span>${labels.ce}</span><strong>${formatMoney(metrics.certaintyEquivalent)}</strong></div>
    <div class="metric"><span>${labels.ratio}</span><strong>${(metrics.offerRatio * 100).toFixed(1)}%</strong></div>
    <div class="metric"><span>${labels.beat}</span><strong>${(metrics.chanceToBeatOffer * 100).toFixed(1)}%</strong></div>
    <div class="metric"><span>${labels.volatility}</span><strong>${formatMoney(metrics.standardDeviation)}</strong></div>
    <div class="recommendation">${labels.recommendation}${metrics.reservationRecommendation === "deal" ? labels.deal : labels.noDeal}</div>
  `;
}

function renderHistory(history) {
  const labels = language === "zh" ? {
    choose: (item) => `选择 ${item.caseId} 号作为自己的箱子`,
    reveal: (item) => `打开 ${item.caseId} 号：${formatMoney(item.value)}`,
    offer: (item) => `第 ${item.round} 轮报价：${formatMoney(item.value)}`,
    deal: (item) => `接受报价：${formatMoney(item.value)}`,
    no_deal: (item) => `第 ${item.round} 轮拒绝报价`,
    case_payout: (item) => `坚持到底：箱内为 ${formatMoney(item.value)}`,
  } : {
    choose: (item) => `Kept case ${item.caseId}`,
    reveal: (item) => `Opened case ${item.caseId}: ${formatMoney(item.value)}`,
    offer: (item) => `Round ${item.round} offer: ${formatMoney(item.value)}`,
    deal: (item) => `Accepted ${formatMoney(item.value)}`,
    no_deal: (item) => `Rejected the round ${item.round} offer`,
    case_payout: (item) => `Went to the end: case held ${formatMoney(item.value)}`,
  };
  $("#historyList").innerHTML = history.slice().reverse().map((item) =>
    `<li>${labels[item.kind](item)}</li>`
  ).join("");
}

function formatMoney(value) {
  return `${language === "zh" ? "¥" : "$"}${money.format(value ?? 0)}`;
}

function findCase(caseId) {
  return currentState.cases.find((item) => item.id === caseId);
}

function showLobby() {
  $("#offerModal").classList.add("hidden");
  $("#gameView").classList.add("hidden");
  $("#wormView").classList.add("hidden");
  $("#pirateView").classList.add("hidden");
  $("#pokerView").classList.add("hidden");
  $("#eCardView").classList.add("hidden");
  $("#lobbyView").classList.remove("hidden");
}

$("#homeButton").addEventListener("click", showLobby);
$("#languageZh").addEventListener("click", () => setLanguage("zh"));
$("#languageEn").addEventListener("click", () => setLanguage("en"));
$("#backButton").addEventListener("click", showLobby);
document.querySelectorAll(".back-to-lobby").forEach((button) => button.addEventListener("click", showLobby));
$("#newGameButton").addEventListener("click", () => startGame("cases"));
$("#newWormButton").addEventListener("click", () => startGame("worm"));
$("#newPirateButton").addEventListener("click", () => startGame("pirates"));
$("#newPokerMatch").addEventListener("click", () => startGame("kuhn-poker"));
$("#newECardMatch").addEventListener("click", () => startGame("e-card"));
$("#submitPirateProposal").addEventListener("click", () => {
  const allocation = [...document.querySelectorAll(".pirate-gold-input")].map((input) => Number(input.value));
  act("submit_proposal", { allocation });
});
$("#dealButton").addEventListener("click", () => act("deal"));
$("#noDealButton").addEventListener("click", () => act("no_deal"));
applyLanguage();
loadLobby().catch((error) => showToast(error.message));
