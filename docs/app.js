const $ = (selector) => document.querySelector(selector);
function readPreference(key) {
  try { return window.localStorage.getItem(key); } catch (_error) { return null; }
}
function writePreference(key, value) {
  try { window.localStorage.setItem(key, value); return true; } catch (_error) { return false; }
}
const savedLanguage = readPreference("aip-language");
let language = ["zh", "en"].includes(savedLanguage) ? savedLanguage : "zh";
let money = new Intl.NumberFormat(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: 2 });
let sessionId = null;
let currentState = null;
let currentGameId = null;
let lobbyGames = [];
let pirateDraft = [];
let guessWhoSelected = null;
let openRulesGameId = null;
let rulesReturnFocus = null;
let offerModalOpen = false;
let actionPending = false;
let investmentOffer = null;
let investmentFraction = 0.25;
let activeOperation = null;
let toastTimer = null;
let routeReady = false;
let wormDisclosure = 0;
let blackjackPracticeMode = readPreference("aip-blackjack-mode") === "practice";
let pokerMode = readPreference("aip-kuhn-poker-mode") === "advanced" ? "advanced" : "basic";
let goofspielMode = readPreference("aip-goofspiel-mode") === "advanced" ? "advanced" : "basic";

const gameViews = {
  cases: "gameView",
  worm: "wormView",
  pirates: "pirateView",
  "kuhn-poker": "pokerView",
  "e-card": "eCardView",
  "restricted-rps": "rpsView",
  "liars-dice": "liarView",
  mastermind: "mastermindView",
  "guess-who": "guessWhoView",
  "hidden-pursuit": "pursuitView",
  battleship: "battleshipView",
  "love-letter": "loveLetterView",
  investment: "investmentView",
  goofspiel: "goofspielView",
  blackjack: "blackjackView",
};

const copy = {
  zh: {
    brandName: "非对称博弈实验室", localOnly: "浏览器临时会话",
    heroLine1: "把推理变成一场", heroLine2: "真正可以玩的博弈",
    heroCopy: "选择一个实验。你做决定，系统隐藏信息、扮演对手，并在关键时刻揭示概率与代价。",
    backLobby: "← 返回大厅", restart: "重新开始", restartCouncil: "重新召开议会", playNow: "开始游戏 →", comingSoon: "后续开放",
    caseEyebrow: "CASE 01 · 风险与谈判 · 入门", caseTitle: "命运之箱",
    wormEyebrow: "CASE 15 · 隐藏状态追踪 · 挑战", wormTitle: "移动虫穴",
    pirateEyebrow: "CASE 09 · 逆向归纳与联盟 · 中等", pirateTitle: "海盗议会",
    pokerEyebrow: "CASE 12 · 私有信息与诈唬 · 较难", pokerTitle: "库恩扑克",
    restartMatch: "重新开始比赛", handNumber: "当前牌局", yourScore: "你的净筹码",
    potSize: "底池", aiScore: "AI 净筹码", strategyAi: "策略型 AI", you: "你",
    yourInformationSet: "你的信息集", quickRules: "快速规则",
    pokerModeTitle: "选择 AI 难度", pokerBasicMode: "基础模式", pokerAdvancedMode: "高级 GTO",
    goofModeTitle: "选择 AI 难度", goofBasicMode: "基础模式", goofAdvancedMode: "高级均衡",
    pokerRules: "双方各投入 1 枚底注，K > Q > J。AI 固定先手，你固定后手；后手的均衡长期价值为每局 +1/18，但单局并不保证获胜。基础 AI 可被利用，高级 AI 使用精确 GTO。",
    eCardEyebrow: "CASE 08 · 非对称收益与混合策略 · 中等", eCardTitle: "E-Card 皇帝牌",
    currentDuel: "本轮对决", emperor: "皇帝", citizen: "市民", slave: "奴隶",
    eCardYourScore: "你的得分", eCardAiScore: "AI 得分",
    duelHistory: "公开对局记录",
    eCardPayoff: "皇帝获胜得 1 分，奴隶获胜得 5 分。双方市民相撞时只弃掉两张牌并继续本轮。",
    rpsEyebrow: "CASE 03 · 有限资源与策略随机化 · 简单", rpsTitle: "限定猜拳实验室",
    currentRound: "当前轮次", draws: "平局", yourInventory: "你的剩余库存",
    aiInventory: "AI 剩余库存", equilibriumGuide: "不可利用的均衡建议",
    rpsEquilibriumCopy: "系统从比赛终点逆向计算每一种剩余库存，求解当前零和矩阵的极小极大混合策略；后期建议可能从均匀随机转为确定性出牌。",
    aiAnalysis: "AI 上轮策略分析",
    blackjackEyebrow: "CASE 02 · 条件概率与策略审计 · 入门", blackjackTitle: "21 点策略实验室",
    restartSession: "重新开始实验", netUnits: "净收益单位", record: "胜 / 负 / 和",
    strategyAccuracy: "基础策略吻合率", dealer: "庄家", basicStrategyAi: "基础策略 AI",
    letAiPlay: "让 AI 执行这一步", decisionAudit: "决策审计",
    blackjackScope: "当前可操作：要牌、停牌、加倍。当前版本尚未开放分牌、投降和保险；基础策略只在六副牌、庄家软 17 停牌且不计牌的规则内成立。",
    blackjackNormalMode: "普通模式", blackjackPracticeMode: "练习模式",
    liarEyebrow: "CASE 13 · 隐藏骰子与公开信号 · 较难", liarTitle: "骗子骰子", liarRound: "回合",
    opponentDice: "对手隐藏骰子", yourDice: "你的骰子", aiHiddenDice: "AI 的隐藏骰子",
    currentBid: "当前公开叫价", quantity: "数量", face: "点数", raiseBid: "加注", challengeBid: "质疑叫价",
    liarInstruction: "你只能看见自己的骰子。1 点是万能牌；判断公开叫价是否值得相信。",
    liarHistory: "公开叫价记录", liarInformation: "你的信息集", liarProbability: "模型认为该叫价为真的概率",
    mastermindEyebrow: "CASE 04 · 候选集合与反馈学习 · 简单", mastermindTitle: "猜数字 · 密码破解",
    mastermindAttempts: "已用尝试", mastermindCandidates: "剩余候选", mastermindGuess: "提交猜测",
    mastermindSuggested: "AI 建议", mastermindExact: "位置正确", mastermindPartial: "数字正确但位置不同",
    mastermindAverage: "你的平均步数", mastermindUseSuggestion: "采用 AI 建议",
    mastermindLeadingZero: "这是密码而非整数，因此 0 可以放在第一位；四个数字不能重复。",
    mastermindInstruction: "AI 已藏好一个由 0–9 组成、数字不重复的四位密码。输入猜测并利用两类反馈排除候选。",
    guessWhoEyebrow: "CASE 05 · 身份推理与信息分割 · 简单", guessWhoTitle: "猜猜我是谁",
    guessWhoTurns: "已用回合", guessWhoCandidates: "剩余候选", guessWhoOptimal: "最优预计总步数",
    guessWhoBest: "你的最佳成绩", guessWhoAdvisor: "精确策略建议", guessWhoUseSuggestion: "执行 AI 建议",
    guessWhoRoster: "角色候选板", guessWhoConfirm: "确认猜测",
    pursuitEyebrow: "CASE 06 · 隐藏移动与公共信号 · 中等", pursuitTitle: "隐形追踪",
    possibleLocations: "可能位置", nextReveal: "下次现身", pursuitRecord: "侦探战绩",
    lastTransport: "最近交通信号", publicMoveLog: "公开移动记录",
    battleshipEyebrow: "CASE 07 · 隐藏部署与概率搜索 · 中等", battleshipTitle: "海战棋",
    loveLetterEyebrow: "CASE 10 · 手牌推断与风险控制 · 较难", loveLetterTitle: "情书决斗",
    loveDeck: "牌堆剩余", lovePrinceTarget: "王子目标", loveGuardGuess: "卫兵猜测",
    loveUseSuggestion: "执行 AI 建议", loveChooseCard: "点击一张合法手牌将它打出", loveRemoved: "开局公开移除", loveYourScore: "你的得分", loveAiScore: "AI 得分", loveSelf: "自己",
    investmentEyebrow: "CASE 11 · 增长率与淘汰压力 · 较难", investmentTitle: "Kelly 生存投资赛",
    investmentCapital: "虚拟资金", investmentRank: "当前排名", investmentNextCut: "下次淘汰", investmentStake: "仓位比例", investmentConfirm: "确认本轮决策", investmentLeaderboard: "生存榜", investmentAnalysis: "赔率分析师面板",
    goofspielEyebrow: "CASE 14 · 同时行动与秘密竞价 · 较难", goofspielTitle: "秘密竞价 · Goofspiel",
    goofYourScore: "你的奖牌分", goofPrizeLabel: "当前奖牌", goofAiScore: "AI 奖牌分", goofAiInventory: "AI 剩余竞价牌（公开）", goofRevealedPrize: "本轮已揭晓奖牌", goofYourInventory: "你的剩余竞价牌", goofAdvisor: "精确均衡建议",
    yourFleet: "你的舰队", enemyWaters: "敌方海域", randomizeFleet: "重新随机布阵", startBattle: "确认布阵，开始战斗",
    shipsRemaining: "剩余舰船", candidateWorlds: "候选部署", advisorShot: "概率建议", battleHistory: "交火记录",
    rulesEyebrow: "玩法说明", rulesTitle: "游戏规则", closeRules: "关闭",
    prizePool: "奖金池", round: "回合", decisionPanel: "决策仪表",
    emptyInsight: "银行家报价后，这里会显示期望值、风险和模型建议。",
    gameHistory: "博弈记录", liveChecks: "实时检查次数", possiblePositions: "仍可能的位置",
    strategyHint: "解法帮助", guaranteedSequence: "保证抓捕答案", showHint: "显示提示", showAnswer: "查看答案",
    wormAnswerLocked: "答案默认隐藏，先独立尝试；需要时再主动揭示。",
    wormStrategyCopy: "只要从第一步开始严格执行该序列，即使虫子选择最不利的移动，也能在序列结束前抓到。",
    searchHistory: "搜索记录", availableGold: "可分配金币", votesNeeded: "通过所需票数",
    unallocated: "尚未分配", yourProposal: "你的提案", submitProposal: "提交提案并投票",
    pirateInstruction: "你是最资深的 A。为每名海盗分配金币，然后让所有人同时投票。",
    backwardBenchmark: "逆向归纳基准", bankerOffer: "银行家报价", acceptOffer: "接受报价",
    counterOfferLabel: "你的一次议价金额", counterOfferButton: "讨价还价一次", counterOfferHelp: "银行家接受则立即成交；拒绝则自动继续开箱，且本局不能再次议价。",
    offerRemainingValues: "仍可能留在保留箱中的金额",
    rejectOffer: "拒绝，继续开箱", operationFailed: "操作失败", operationPending: "正在处理，请稍候…",
    connectionFailed: "连接暂时失败，请检查网络后重试。", invalidResponse: "页面收到异常响应，请刷新后重试。",
    sessionExpired: "这局临时游戏已经过期，请重新开始。",
  },
  en: {
    brandName: "Asymmetric Games Lab", localOnly: "Browser session",
    heroLine1: "Turn reasoning into", heroLine2: "games you can actually play",
    heroCopy: "Choose an experiment. You decide; the system hides information, plays the opposition, and reveals probability and cost at decisive moments.",
    backLobby: "← Back to lobby", restart: "New game", restartCouncil: "New council", playNow: "Play now →", comingSoon: "Coming later",
    caseEyebrow: "CASE 01 · RISK & NEGOTIATION · BEGINNER", caseTitle: "Cases of Fate",
    wormEyebrow: "CASE 15 · HIDDEN-STATE TRACKING · CHALLENGE", wormTitle: "The Moving Worm",
    pirateEyebrow: "CASE 09 · BACKWARD INDUCTION & COALITIONS · MEDIUM", pirateTitle: "Pirate Council",
    pokerEyebrow: "CASE 12 · PRIVATE INFORMATION & BLUFFING · HARD", pokerTitle: "Kuhn Poker",
    restartMatch: "Restart match", handNumber: "Current hand", yourScore: "Your net chips",
    potSize: "Pot", aiScore: "AI net chips", strategyAi: "Strategy AI", you: "You",
    yourInformationSet: "Your information set", quickRules: "Quick rules",
    pokerModeTitle: "Choose AI difficulty", pokerBasicMode: "Basic mode", pokerAdvancedMode: "Advanced GTO",
    goofModeTitle: "Choose AI difficulty", goofBasicMode: "Basic mode", goofAdvancedMode: "Advanced equilibrium",
    pokerRules: "Both players ante 1; K > Q > J. The AI always acts first and you always act second. The second seat is worth +1/18 chip per hand in equilibrium over the long run, not a guaranteed win. Basic AI is exploitable; Advanced uses exact GTO.",
    eCardEyebrow: "CASE 08 · ASYMMETRIC PAYOFFS & MIXED STRATEGY · MEDIUM", eCardTitle: "E-Card",
    currentDuel: "Duel", emperor: "Emperor", citizen: "Citizen", slave: "Slave",
    eCardYourScore: "Your score", eCardAiScore: "AI score",
    duelHistory: "Public duel history",
    eCardPayoff: "An Emperor win scores 1; a Slave win scores 5. Citizen versus Citizen discards both cards and continues the round.",
    rpsEyebrow: "CASE 03 · FINITE RESOURCES & RANDOMIZATION · EASY", rpsTitle: "Restricted RPS Lab",
    currentRound: "Current round", draws: "Draws", yourInventory: "Your remaining inventory",
    aiInventory: "AI remaining inventory", equilibriumGuide: "Unexploitable equilibrium guide",
    rpsEquilibriumCopy: "The solver works backward through every remaining-inventory state and solves the current zero-sum matrix for its minimax mixture. Late-game advice can become deterministic rather than uniformly random.",
    aiAnalysis: "AI strategy from the last round",
    blackjackEyebrow: "CASE 02 · CONDITIONAL PROBABILITY & STRATEGY AUDIT · BEGINNER", blackjackTitle: "Blackjack Strategy Lab",
    restartSession: "Restart session", netUnits: "Net units", record: "Win / Loss / Push",
    strategyAccuracy: "Basic-strategy match", dealer: "Dealer", basicStrategyAi: "Basic-strategy AI",
    letAiPlay: "Let AI take this action", decisionAudit: "Decision audit",
    blackjackScope: "Available actions: Hit, Stand, and Double. Split, Surrender, and Insurance are not yet implemented. Basic strategy is scoped to six decks, dealer standing on soft 17, and no card counting.",
    blackjackNormalMode: "Normal mode", blackjackPracticeMode: "Practice mode",
    liarEyebrow: "CASE 13 · HIDDEN DICE & PUBLIC SIGNALS · HARD", liarTitle: "Liar's Dice", liarRound: "Round",
    opponentDice: "Opponent hidden dice", yourDice: "Your dice", aiHiddenDice: "AI hidden dice",
    currentBid: "Current public bid", quantity: "Quantity", face: "Face", raiseBid: "Raise", challengeBid: "Challenge",
    liarInstruction: "You see only your own dice. Ones are wild; decide whether the public claim is worth believing.",
    liarHistory: "Public bid history", liarInformation: "Your information set", liarProbability: "Model probability the bid is true",
    mastermindEyebrow: "CASE 04 · CANDIDATE SETS & FEEDBACK · EASY", mastermindTitle: "Bulls & Cows Lab",
    mastermindAttempts: "Attempts", mastermindCandidates: "Candidates left", mastermindGuess: "Submit guess",
    mastermindSuggested: "AI suggestion", mastermindExact: "Exact position", mastermindPartial: "Right digit, wrong position",
    mastermindAverage: "Your average", mastermindUseSuggestion: "Use AI suggestion",
    mastermindLeadingZero: "This is a code, not an integer, so zero may come first; all four digits must be distinct.",
    mastermindInstruction: "The AI has hidden four distinct digits from 0–9. Submit experiments and use both feedback counts to eliminate candidates.",
    guessWhoEyebrow: "CASE 05 · IDENTITY DEDUCTION & INFORMATION SPLITS · EASY", guessWhoTitle: "Guess Who?",
    guessWhoTurns: "Turns used", guessWhoCandidates: "Candidates left", guessWhoOptimal: "Optimal expected total",
    guessWhoBest: "Your best", guessWhoAdvisor: "Exact-strategy advice", guessWhoUseSuggestion: "Take AI advice",
    guessWhoRoster: "Character board", guessWhoConfirm: "Confirm guess",
    pursuitEyebrow: "CASE 06 · HIDDEN MOVEMENT & PUBLIC SIGNALS · MEDIUM", pursuitTitle: "Hidden Pursuit",
    possibleLocations: "Possible locations", nextReveal: "Next reveal", pursuitRecord: "Detective record",
    lastTransport: "Latest transport signal", publicMoveLog: "Public move log",
    battleshipEyebrow: "CASE 07 · HIDDEN DEPLOYMENT & PROBABILITY SEARCH · MEDIUM", battleshipTitle: "Battleship",
    loveLetterEyebrow: "CASE 10 · HAND INFERENCE & RISK CONTROL · HARD", loveLetterTitle: "Love Letter Duel",
    loveDeck: "Deck remaining", lovePrinceTarget: "Prince target", loveGuardGuess: "Guard guess",
    loveUseSuggestion: "Take AI advice", loveChooseCard: "Click a legal card to play it", loveRemoved: "Face-up removals", loveYourScore: "Your score", loveAiScore: "AI score", loveSelf: "Yourself",
    investmentEyebrow: "CASE 11 · GROWTH & ELIMINATION PRESSURE · HARD", investmentTitle: "Kelly Survival Tournament",
    investmentCapital: "Virtual capital", investmentRank: "Current rank", investmentNextCut: "Next elimination", investmentStake: "Stake fraction", investmentConfirm: "Lock this decision", investmentLeaderboard: "Survival table", investmentAnalysis: "Odds analyst panel",
    goofspielEyebrow: "CASE 14 · SIMULTANEOUS SECRET BIDDING · HARD", goofspielTitle: "Secret Bidding · Goofspiel",
    goofYourScore: "Your prize points", goofPrizeLabel: "Current prize", goofAiScore: "AI prize points", goofAiInventory: "AI bid cards left (public)", goofRevealedPrize: "Revealed prize this round", goofYourInventory: "Your bid cards left", goofAdvisor: "Exact-equilibrium guide",
    yourFleet: "Your fleet", enemyWaters: "Enemy waters", randomizeFleet: "Randomize fleet", startBattle: "Lock fleet and start",
    shipsRemaining: "Ships remaining", candidateWorlds: "Candidate placements", advisorShot: "Probability hint", battleHistory: "Battle log",
    rulesEyebrow: "HOW TO PLAY", rulesTitle: "Rules", closeRules: "Close",
    prizePool: "Prize board", round: "Round", decisionPanel: "Decision dashboard",
    emptyInsight: "Expected value, risk, and model guidance appear after the banker's offer.",
    gameHistory: "Game history", liveChecks: "Live check count", possiblePositions: "Possible positions",
    strategyHint: "Solution help", guaranteedSequence: "Guaranteed-capture answer", showHint: "Show hint", showAnswer: "Reveal answer",
    wormAnswerLocked: "The answer is hidden by default. Try independently, then reveal it only if needed.",
    wormStrategyCopy: "Follow this sequence from the first move and even a worst-case worm must be caught before it ends.",
    searchHistory: "Search history", availableGold: "Gold available", votesNeeded: "Votes required",
    unallocated: "Unallocated", yourProposal: "Your proposal", submitProposal: "Submit proposal and vote",
    pirateInstruction: "You are A, the most senior pirate. Allocate gold to every pirate, then call a simultaneous vote.",
    backwardBenchmark: "Backward-induction benchmark", bankerOffer: "Banker's offer", acceptOffer: "Deal",
    counterOfferLabel: "Your one counter-offer", counterOfferButton: "Negotiate once", counterOfferHelp: "If accepted, the deal closes immediately. If rejected, play continues and bargaining is gone for this game.",
    offerRemainingValues: "Values still possible in your kept case",
    rejectOffer: "No deal — keep opening", operationFailed: "Action failed", operationPending: "Working…",
    connectionFailed: "Connection failed. Check your network and try again.", invalidResponse: "The page received an invalid response. Refresh and try again.",
    sessionExpired: "This temporary game has expired. Please start a new game.",
  },
};

const gamesCopy = {
  zh: {
    cases: ["命运之箱", "从 26 个密封箱中保留一个，在不断缩小的风险中与银行家谈判。", "单人 · 决策与风险"],
    worm: ["移动虫穴", "面对无随机性的智能虫子；错误方法永远无法靠运气抓到它。", "单人 · 对抗搜索"],
    pirates: ["海盗议会", "亲自分配 100 枚金币，面对会做逆向归纳的理性海盗投票。", "单人 · 人机投票"],
    "kuhn-poker": ["库恩扑克", "在三张牌的极简牌局中读取信号、抓诈唬，并与混合策略 AI 连续对战。", "单人 · 隐藏手牌与诈唬"],
    "e-card": ["E-Card 皇帝牌", "轮流扮演皇帝方与奴隶方，在非对称收益下猜测 AI 的隐藏出牌时机。", "单人 · 非对称混合策略"],
    "restricted-rps": ["限定猜拳实验室", "管理公开的有限手势库存，对抗以均衡随机化为底线、同时学习你偏好的 AI。", "单人 · 资源约束与机制设计"],
    blackjack: ["21 点策略实验室", "对抗固定规则庄家，逐步比较你的行动与规则限定的最优基础策略。", "单人 · 概率决策与策略审计"],
    "liars-dice": ["骗子骰子", "隐藏骰子、公开叫价与质疑概率；判断何时加注，何时抓住 AI 的虚张声势。", "单人 · 隐藏骰子与公开信号"],
    mastermind: ["猜数字 · 密码破解", "从 5,040 个隐藏密码中推理答案，比较自己的步数与 minimax 信息策略。", "单人 · 信息集搜索"],
    "guess-who": ["猜猜我是谁", "通过公开的是非问题缩小 24 人候选集合，并与精确最优提问策略比较步数。", "单人 · 身份推理与信息分割"],
    "hidden-pursuit": ["隐形追踪", "控制两名侦探封锁交通网络，从公开的出行方式和间歇现身中推断隐藏目标。", "单人 · 隐藏移动与信念追踪"],
    battleship: ["海战棋", "部署舰队，在未知海域中逐格搜索敌舰，对抗概率热力图 AI。", "单人 · 隐藏部署与概率搜索"],
    "love-letter": ["情书决斗", "读取公开弃牌与隐藏手牌，在保护、换牌、试探和点杀之间先赢得四轮。", "单人 · 手牌推断与风险控制"],
    investment: ["Kelly 生存投资赛", "比较赔率、胜率和仓位，在周期淘汰制下兼顾资金增长与存活。", "单人 · 增长率、风险与相对排名"],
    goofspiel: ["秘密竞价", "奖牌逐轮揭晓，双方同时秘密竞价；在直觉型与精确均衡 AI 之间切换挑战。", "单人 · 同时行动与秘密竞价"],
    auction: ["百元全支付拍卖", "用公开价格争夺主导权，并观察联盟与背叛。", "本地多人 · 即将开放"],
  },
  en: {
    cases: ["Cases of Fate", "Keep one of 26 sealed cases and negotiate with the banker as uncertainty narrows.", "Solo · Risk & decision"],
    worm: ["The Moving Worm", "Face a deterministic adversary: a wrong method can never win by luck.", "Solo · Adversarial search"],
    pirates: ["Pirate Council", "Allocate 100 coins and face rational pirates who reason backward before voting.", "Solo · Human vs AI vote"],
    "kuhn-poker": ["Kuhn Poker", "Read signals, catch bluffs, and battle a mixed-strategy AI in the classic three-card game.", "Solo · Hidden cards & bluffing"],
    "e-card": ["E-Card", "Alternate between Emperor and Slave, reading the AI's hidden timing under asymmetric rewards.", "Solo · Asymmetric mixed strategy"],
    "restricted-rps": ["Restricted RPS Lab", "Manage a public finite move inventory against an AI that combines equilibrium randomization with learning.", "Solo · Resource constraints & mechanism design"],
    blackjack: ["Blackjack Strategy Lab", "Play against a fixed-rule dealer and audit every choice against the rule-scoped optimal basic strategy.", "Solo · Probability & strategy audit"],
    "liars-dice": ["Liar's Dice", "Private dice, public bids, and probability-guided challenges against a bluffing AI.", "Solo · Hidden dice & public signals"],
    mastermind: ["Bulls & Cows Lab", "Reason through 5,040 hidden codes and compare your attempts with a minimax information strategy.", "Solo · Information-set search"],
    "guess-who": ["Guess Who?", "Narrow 24 identities with public yes/no questions and compare your choices with an exact optimal policy.", "Solo · Identity deduction & information splits"],
    "hidden-pursuit": ["Hidden Pursuit", "Control two detectives and infer an evasive target from public transport signals and scheduled reveals.", "Solo · Hidden movement & belief tracking"],
    battleship: ["Battleship", "Deploy a fleet, search unknown waters cell by cell, and face a probability-density AI.", "Solo · Hidden deployment & search"],
    "love-letter": ["Love Letter Duel", "Read public discards and a hidden hand while balancing protection, trades, probes, and elimination.", "Solo · Hand inference & risk control"],
    investment: ["Kelly Survival Tournament", "Trade odds, probability, and position size while periodic eliminations reward both growth and survival.", "Solo · Growth, risk & relative rank"],
    goofspiel: ["Secret Bidding", "Reveal prizes, commit simultaneous hidden bids, and switch between intuitive and exact-equilibrium AI.", "Solo · Simultaneous hidden bidding"],
    auction: ["100-Unit All-Pay Auction", "Fight for leadership through public prices, alliances, and defection.", "Local multiplayer · Coming soon"],
  },
};

const difficultyCopy = {
  zh: { cases: "入门", blackjack: "入门", "restricted-rps": "简单", mastermind: "简单", "guess-who": "简单", "hidden-pursuit": "中等", battleship: "中等", "love-letter": "较难", investment: "较难", "e-card": "中等", pirates: "中等", "kuhn-poker": "较难", "liars-dice": "较难", goofspiel: "较难", worm: "挑战", auction: "未开放" },
  en: { cases: "Beginner", blackjack: "Beginner", "restricted-rps": "Easy", mastermind: "Easy", "guess-who": "Easy", "hidden-pursuit": "Medium", battleship: "Medium", "love-letter": "Hard", investment: "Hard", "e-card": "Medium", pirates: "Medium", "kuhn-poker": "Hard", "liars-dice": "Hard", goofspiel: "Hard", worm: "Challenge", auction: "Coming soon" },
};

const rulesCopy = {
  zh: {
    cases: ["目标：在 26 个箱子中尽可能拿到高奖金。", "先点击任意一个箱子作为你的保留箱；之后不要再打开它。", "按页面提示点击指定数量的其他箱子；刚打开的金额会保留在报价窗口中，方便判断奖池变好还是变差。", "银行家报价始终低于剩余金额的算术期望。你可以接受、拒绝，或在整局中使用一次议价；议价被拒后会自动继续开箱。", "若所有报价都拒绝，坚持到最后会自动打开保留箱，并明确显示最终所得金额。"],
    worm: ["目标：在最坏情况下也抓到不断移动的虫子。五个洞按 1–5 排成一行。", "每回合点击一个洞检查；若未抓到，虫子必须立刻移动到相邻洞。", "观察“仍可能的位置”和奇偶节奏，自行设计检查顺序。", "具体提示和完整答案默认隐藏；卡住时再点击“显示提示”或“查看答案”。"],
    pirates: ["目标：让你的提案获得足够票数，并让海盗 A 活下来。", "在每个海盗的金币输入框中填整数，所有分配之和必须正好等于 100。", "点击“提交提案并投票”。每名海盗会比较你的报价与否决后按逆向归纳得到的金币/生存结果。", "达到页面显示的赞成票数就通过；否则 A 被处决，系统展示实际结果和理论最优方案。"],
    "kuhn-poker": ["目标：你固定担任后手，在连续牌局中取得正的净筹码。你和 AI 从 J、Q、K 中各拿一张私牌，并各投入 1 枚底注。", "AI 先选择过牌或下注。AI 过牌后，你可过牌直接比牌，或额外投入 1 枚下注；面对 AI 下注时，你只能跟注或弃牌。", "跟注再投入 1 枚并亮牌；弃牌立即损失底注。牌力为 K > Q > J。下注既可能是 K 的价值下注，也可能是 J 的诈唬。", "基础模式保留合理混合策略，但在一次 Q 跟注频率上存在可利用偏差；高级模式使用穷举最佳回应验证、可利用度为零的精确 GTO。", "后手在双方都采用 GTO 时长期期望为每局 +1/18 枚筹码。它是大量牌局的平均值，不代表每局或短期比赛必胜。切换模式会重新开始并清空比分。"],
    "e-card": ["目标：利用特殊牌的循环克制关系赢得高分。你和 AI 各有 1 张特殊牌与 4 张市民牌。", "点击手中的一张牌，双方会同时出牌，AI 的选择在揭示前保持隐藏。", "皇帝击败市民，市民击败奴隶，奴隶击败皇帝；奴隶获胜通常得到更高收益。", "市民对市民不会结束本轮，两张牌会被消耗后继续；特殊牌相遇则按克制关系结束本轮。"],
    "restricted-rps": ["目标：在有限库存耗尽前赢得更多回合。你和 AI 各有相同数量的石头、剪刀、布。", "点击一张仍有库存的手势牌；双方同时出牌，使用过的牌永久减少。", "石头胜剪刀，剪刀胜布，布胜石头；相同手势为平局。双方库存和历史都会公开。", "库存全部用完后比赛结束。赛后复盘会比较实际频率、均衡支持集和 AI 的针对权重；单场输赢仍会受到随机出牌影响。"],
    blackjack: ["目标：让自己的点数尽量接近 21，但超过 21 就爆牌并立即输。", "A 可算 1 或 11；J/Q/K 算 10。开始时你会看到两张手牌和庄家的一张明牌。", "普通模式不会提前揭示建议；练习模式会在每次操作后判断是否符合基础策略并告诉你正确动作。", "当前可点击要牌、停牌，以及仅首个决定可用的加倍。庄家按软 17 停牌；分牌、投降和保险尚未开放。"],
    "liars-dice": ["目标：判断公开叫价是真实还是虚张声势，并在质疑中赢下本轮。", "你能看到自己的骰子，但看不到 AI 的骰子。叫价“数量 × 点数”表示全桌至少有这么多个该点数。", "点击“加注”提交更高的数量，或在数量相同时提交更高点数；1 点对 2–6 点是万能牌。", "如果你认为上一口不可信，点击“质疑”。系统揭示全部骰子并根据实际数量判定胜负。"],
    mastermind: ["目标：在 10 次尝试内破解 AI 隐藏的四位密码。密码从 0–9 中选择四个不同数字，共有 5,040 种可能。", "输入恰好四个不同数字，例如 0123；首位可以是 0。点击“提交猜测”后才能得到反馈。", "“位置正确”表示数字和位置都对；“数字正确但位置不同”表示数字存在但放错位置。反馈只给数量，不指出具体是哪一位。", "观察每轮排除的候选数并继续推理。你可以完全自己猜，也可以点击“采用 AI 建议”复制 minimax 建议，再提交。", "得到 4 个位置正确即获胜。连续完成多局后，页面会计算你的成功局平均步数与最佳成绩。"],
    "guess-who": ["目标：在 8 回合内找出 AI 从 24 张公开角色卡中秘密选中的人。", "先查看角色特征，再点击一个仍能切分候选集的是非问题；按钮会预告回答“是”和“否”各剩多少人。", "AI 只回答“是”或“否”。不符合答案的角色会变暗，信息集和最优建议会立即更新。", "要猜身份时，先点击一张仍亮起的角色卡，再点击“确认猜测”。猜错会消耗一回合并排除该角色，猜对即获胜。", "“执行 AI 建议”会采用固定角色表与问题库下经过动态规划证明的最小期望策略；候选唯一时，它会执行最终猜测。"],
    "hidden-pursuit": ["目标：在第 12 回合结束前，让任一侦探移动到隐藏目标当前所在的节点。", "地图上蓝色 A、青色 B 是你的两名侦探。每回合先移动 A，再移动 B；只能点击当前侦探通过线路直接相连的节点。", "两名侦探都行动后，目标会沿黄色出租车线或紫色公交线移动一次，并公开所用交通方式，但通常不公开终点。", "带问号的节点是仍符合全部公开信息的位置。你移动到其中一个节点却没有抓到人，也会排除该位置。", "目标会在第 3、6、9 回合移动后强制现身；利用现身位置、之后的交通信号和两名侦探的封锁完成包围。", "抓到目标即获胜；撑过 12 回合则目标逃脱。AI 根据距离、出口和移动后的候选数量规避，但不是已证明的全局最优逃跑策略。"],
    battleship: ["目标：在概率 AI 击沉你的全部舰船之前，先找到并击沉它的舰队。", "布阵阶段先选择 10×10、12×12 或 15×15 海域；地图越大，双方舰船也越多。", "不同颜色表示不同舰船。点击舰船卡可旋转 90°，也可点击“重新随机布阵”；直线舰船翻转 180°占据的格子不变。", "满意后点击“确认布阵，开始战斗”。战斗阶段点击敌方未知格；淡点表示落空，红色表示命中，深红色表示击沉。", "10×10 与 12×12 中双方每次各开一炮；15×15 使用对称双炮齐射，你连续打完两炮后 AI 才还击两炮。已经射击过的格子不能重复选择。", "候选部署表示目前仍符合反馈的舰船位置数量；概率建议给出高密度目标，AI 面板还会公开搜索/追击模式与覆盖强度。"],
    "love-letter": ["目标：比 AI 更早获得 4 枚胜利标记。每轮只有 16 张牌，你必须从公开弃牌推测 AI 留在手里的角色。", "开局双方各持一张牌；轮到你时再摸一张，然后点击两张手牌中的一张打出。牌面效果会立即执行。", "卫兵需要在右侧选择一个 2–8 的角色进行猜测；王子需要选择让 AI 或自己弃掉手牌。其他牌的目标由规则自动决定。", "侍女会保护你直到下次行动；男爵比较双方手牌；国王交换手牌；若同时持有伯爵夫人与国王或王子，必须打出伯爵夫人。", "打出公主或因卫兵、男爵、王子效果被淘汰会立刻输掉本轮；牌堆用完则比较手牌点数。点击“执行 AI 建议”可查看并采用信念策略。"],
    investment: ["目标：用 1,000 单位虚拟资金完成 12 轮并最终排名第一；第 4、7、10 轮资金最低者会被淘汰。", "每轮比较三张机会卡。1:1 表示投入 100、成功净赚 100；3:1 表示成功净赚 300，失败都损失投入的 100。", "成功率×净赔率−失败率得到期望回报。正值只表示大量重复后的平均优势，不保证本轮获利。", "选择机会，再选 0%、10%、25%、50% 或 75% 仓位。0% 能保本，但可能被增长型对手超过。", "Kelly 最大化长期对数增长，不保证淘汰赛夺冠；AI 分别使用全 Kelly、半 Kelly、追赶、长赔率和保本技能。所有金额均为虚拟数值。"],
    goofspiel: ["目标：四轮结束后赢得比 AI 更多的奖牌分数。", "你和 AI 各有数值 1–4 的四张竞价牌；奖牌 1–4 随机排序，每轮只揭晓当前奖牌。", "点击一张尚未使用的竞价牌后，你和 AI 同时揭晓选择。出牌前看不到 AI 本轮选了什么。", "较大的竞价牌赢得当前奖牌对应的分数；相同则奖牌作废。双方使用过的竞价牌都会永久移除并公开。", "基础 AI 会直觉性地打出最接近奖牌值的剩余牌，容易理解但可被利用；高级 AI 从当前状态的精确零和均衡中随机出牌。切换难度会开始一场新比赛。", "四张牌全部用完后比较总分。赛后复盘会检查每轮选择在当时均衡中的概率，而不是仅凭最终输赢评价策略。"],
  },
  en: {
    cases: ["Goal: maximize your payout from 26 cases.", "Click one case to keep; never open it afterward.", "Open the required cases; the latest revealed values remain visible while you assess the offer.", "Every banker offer is below the remaining arithmetic mean. Deal, continue, or spend your one counter-offer; rejection automatically continues play.", "Reject every offer and the kept case is revealed with a clear final payout."],
    worm: ["Goal: catch the moving worm even under worst-case play. Five holes are arranged from 1 to 5.", "Check one hole per turn. After a miss, the worm must immediately move to a neighbor.", "Watch the possible-position set and reason about alternating parity as you build a search rhythm.", "The specific hint and full answer are hidden by default; reveal either only when you want help."],
    pirates: ["Goal: pass your proposal and keep pirate A alive.", "Enter integer gold allocations totaling exactly 100, then submit the proposal.", "Each pirate compares your offer with the continuation payoff after A's execution.", "If enough votes support the proposal it passes; otherwise A is executed and the benchmark is shown."],
    "kuhn-poker": ["Goal: play every hand from the second seat and build positive net chips over repeated hands. You and the AI receive different private cards from J, Q, and K, then ante 1 each.", "The AI acts first with Check or Bet. After a check, choose Check for showdown or Bet for 1 more. Facing an opening bet, choose Call or Fold.", "Calling adds 1 and reveals both cards; folding loses the ante. K > Q > J. A bet may be value with K or a bluff with J.", "Basic mode keeps a coherent mixed strategy but under-calls with Q in one information set, creating a measurable weakness. Advanced uses exact GTO with zero exploitability under exhaustive pure best-response checks.", "Against GTO, the second seat is worth +1/18 chip per hand in long-run expectation. This is an average over many hands, never a promise to win one hand or a short match. Switching modes resets the score."],
    "e-card": ["Goal: exploit the asymmetric special-card cycle. Each side holds one special card and four citizens.", "Click one card; both sides reveal simultaneously.", "Emperor beats Citizen, Citizen beats Slave, and Slave beats Emperor. Slave wins pay more.", "Citizen versus Citizen consumes both cards and continues the round."],
    "restricted-rps": ["Goal: win more rounds before your finite inventory runs out.", "Click an available Rock, Paper, or Scissors card; both choices are simultaneous and the card is consumed.", "Rock beats Scissors, Scissors beats Paper, and Paper beats Rock. Equal moves draw.", "The post-match review compares your frequencies, equilibrium support, and the AI's exploit weight. One match still contains variance from randomized play."],
    blackjack: ["Goal: approach 21 without going over.", "A counts as 1 or 11; face cards count as 10. You see your hand and the dealer upcard.", "Normal mode keeps advice out of the way. Practice mode grades every decision and reveals the basic-strategy action afterward.", "Choose Hit, Stand, or Double on the first decision. The dealer stands on soft 17; Split, Surrender, and Insurance are not yet available."],
    "liars-dice": ["Goal: identify a bluff and win the round.", "You see your dice only. A bid Quantity × Face claims at least that many matching dice across both hands.", "Raise quantity, or raise face at equal quantity; ones are wild for faces 2–6.", "Challenge the current bid to reveal all dice and settle the round."],
    mastermind: ["Goal: crack a four-digit hidden code in ten attempts. It uses four distinct digits from 0–9, creating 5,040 possible worlds.", "Enter exactly four different digits, such as 0123. A leading zero is valid, then submit.", "Exact means right digit and position; misplaced means a right digit in the wrong position. Counts never identify the individual digits.", "Reason independently or copy the bounded-minimax AI suggestion. Each history row shows how many candidates that experiment removed.", "Four exact positions win. Across solved rounds, the page tracks your average and best attempt count."],
    "guess-who": ["Goal: identify the AI's secret person from 24 public character cards within eight turns.", "Inspect the traits, then ask a yes/no question that still splits the candidate set. Each button previews how many people remain after Yes and No.", "The AI answers truthfully. Inconsistent cards dim immediately, and both the information set and exact recommendation update.", "To name the person, select a bright card and press Confirm guess. A wrong guess costs one turn and eliminates that card; a correct guess wins.", "Take AI advice uses a dynamic-programming policy proven to minimize expected turns for this fixed roster and question bank. When one candidate remains, it makes the final guess."],
    "hidden-pursuit": ["Goal: move either detective onto the hidden fugitive before round 12 ends.", "Blue A and cyan B are your detectives. Move A, then B each round by clicking a directly connected node.", "After both moves, the fugitive takes one yellow Taxi or purple Bus edge. The transport is public; the destination usually remains hidden.", "Question-mark nodes form the current information set. Visiting one without a capture also eliminates it.", "The fugitive must reveal after moves 3, 6, and 9. Combine that sighting with later transport signals and two-token blocking.", "Capture wins; surviving round 12 lets the fugitive escape. The AI is a distance-and-ambiguity heuristic, not a proven globally optimal evader."],
    battleship: ["Goal: sink the enemy fleet before the probability AI sinks yours.", "Choose a 10×10, 12×12, or 15×15 sea during deployment; larger boards add ships to preserve action density.", "Each ship has its own color. Click a ship card to rotate it 90°, or randomize the fleet. A 180° flip of a straight ship occupies the same cells.", "Lock the layout, then click unknown enemy cells. A pale dot is a miss, red is a hit, and dark red is a sunk ship.", "The 10×10 and 12×12 boards alternate one shot each. On 15×15, you fire a two-shot salvo before the AI returns two shots. Fired cells cannot be selected again.", "Candidate placements count positions consistent with observations; the hint marks a dense target, while the AI panel reports hunt/target mode and coverage strength."],
    "love-letter": ["Goal: earn four tokens before the AI. Only 16 cards exist, so public discards let you infer the hidden opposing hand.", "Each side begins with one card. On your turn you draw a second card, then click one of the two cards to play it and resolve its effect.", "A Guard needs a 2–8 character guess; a Prince needs a target. Choose those controls before clicking the card. Other targets are automatic.", "Handmaid protects until your next turn; Baron compares hands; King trades hands. Countess must be played while held with King or Prince.", "Discarding Princess or losing to Guard, Baron, or Prince ends the round. An empty deck triggers a high-card showdown. Take AI advice uses public-card beliefs, not the hidden hand."],
    investment: ["Goal: finish first after 12 rounds with 1,000 units of virtual capital. The lowest bankroll leaves after rounds 4, 7, and 10.", "Compare three opportunities. Net odds 1:1 mean a 100 stake wins 100 profit; 3:1 wins 300, while failure loses the 100 stake.", "Expected return is probability × odds − failure probability. A positive value is a long-run average edge, never a guarantee this round.", "Choose an opportunity and a 0%, 10%, 25%, 50%, or 75% stake. Cash preserves capital but may lose relative rank.", "Kelly maximizes asymptotic log growth, not tournament title probability. Rivals use full-Kelly, half-Kelly, chasing, longshot, and capital-preserving skills. All capital is virtual."],
    goofspiel: ["Goal: finish four rounds with more prize points than the AI.", "Both sides hold bid cards 1–4. Prize cards 1–4 are shuffled, and only the current prize is revealed each round.", "Click one unused bid card. Your bid and the AI's hidden choice are then revealed simultaneously.", "The higher bid wins the current prize value; equal bids discard it. Both used bid cards leave their public inventories permanently.", "Basic AI intuitively spends the remaining card closest to the prize; it is understandable but exploitable. Advanced AI samples the exact zero-sum equilibrium for the current state. Changing difficulty starts a fresh match.", "After four bids, the review checks every choice's probability in its exact public-state equilibrium instead of judging strategy from the final score alone."],
  },
};

const ruleDetails = {
  zh: {
    cases: { role: "你是一名电视游戏参赛者。26 个箱子里分别装着从极小到一百万不等的奖金，但你看不到每个箱子的金额。你要一边排除金额，一边决定是否接受银行家的现金报价。", example: "例：你保留了 7 号箱，本轮打开 3 号箱并发现里面是 1 元。报价窗口会保留刚揭晓金额、全部剩余金额和剩余价值期望。你也可以把整局唯一一次议价用在这一轮，但若银行家拒绝，就必须继续开箱。", finish: "接受报价或议价成功时立即结算；若一直拒绝，就在最后打开保留箱并明确显示最终金额。这里没有唯一正确风险偏好。", terms: "保留箱＝最初选中且暂不打开的箱子；剩余价值期望＝所有未揭晓金额的算术平均；风险调整参考值最低按 0 显示，不会再出现难以解释的负金额。" },
    worm: { role: "你是搜捕者，虫子是会主动躲避你的对手。你看不到它在哪个洞，只能根据它每次必须移动到相邻洞的规则推理。", example: "例：你检查 2 号洞但没抓到。虫子此前若在 1 号，只能移到 2 号；若在 3 号，可移到 2 或 4。系统会把仍然可能的洞显示出来。", finish: "当你检查的洞覆盖虫子所有仍合法的可能位置时，保证抓捕成功。乱点可能永远抓不到；具体提示和完整答案默认隐藏，只有主动点击相应按钮才会揭示。", terms: "可能位置＝根据全部历史仍合法的位置；奇偶节奏＝虫子每移动一步就会在奇数洞与偶数洞之间切换；保证策略＝面对任何合法逃法都能成功的顺序。" },
    pirates: { role: "你扮演最资深海盗 A。规则是：A 提出如何分 100 枚金币，所有海盗投票；若票数不足，A 被处决，下一位海盗重新提案。每个人都知道之后会发生什么。", example: "例：如果海盗 C 在 A 死后能得到 1 枚金币，那么给 C 仍然只有 1 枚通常买不到他的票；给 2 枚才比他的后续结果更好。也可以收买那些 A 死后会一无所有的人。", finish: "分配总和恰好为 100 后提交。赞成票达到页面要求，A 存活并按提案分金币；票数不足则 A 死亡，页面展示后续结果。你的核心任务是用尽量少的金币买到足够票数。", terms: "逆向归纳＝先算只剩最后几名海盗时会怎样，再一步步倒推到现在；延续收益＝否决当前提案后，该海盗预计能否存活以及能拿多少金币。" },
    "kuhn-poker": { role: "这是把扑克压缩到三张牌的练习。AI 固定先手、你固定后手；你只知道自己的牌，不知道 AI 的牌。基础模式可被利用，高级模式是精确 GTO。", example: "例：你拿 Q，AI 下注。AI 可能拿 K 认真下注，也可能拿 J 诈唬。跟注要再投入 1 枚并亮牌；弃牌会损失已投入的底注，但避免继续亏损。", finish: "一方弃牌或双方完成过牌/跟注后，本局结束并结算筹码。后手的 GTO 长期价值是 +1/18/局；基础 AI 的最佳回应价值可达 +1/6/局。两者都是精确期望值，不保证单局胜负。", terms: "过牌＝不加钱；下注＝额外投入 1；跟注＝支付同样金额并要求亮牌；GTO＝对手无法通过单方面改变策略获得更多收益的均衡策略。切换模式会清空当前比分。" },
    "e-card": { role: "你和 AI 轮流扮演皇帝方与奴隶方。皇帝通常强，但奴隶能击败皇帝且回报更高，因此双方都要猜特殊牌会在哪一次出现。", example: "例：你是奴隶方，前两次先出市民试探。若 AI 也出市民，两张市民消耗后继续。你第三次出奴隶，若 AI 此时出皇帝，你将以弱胜强获得高分；若 AI 出市民，你会输。", finish: "出现非市民平局的胜负关系时，本轮结束并计分，然后双方交换阵营开始下一轮。重点不是只看单张强弱，而是推测对方何时使用唯一的特殊牌。", terms: "皇帝＞市民、 市民＞奴隶、奴隶＞皇帝；特殊牌＝皇帝或奴隶；市民相撞＝平局并消耗双方各一张市民。" },
    "restricted-rps": { role: "这是有库存的猜拳。普通猜拳每轮都能随便出，但这里每种手势只有有限张；你刚才用掉什么，会改变后面还能怎么出。", example: "例：你只剩 1 石头、0 剪刀、2 布，AI 能看到这个库存，所以知道你不可能出剪刀。你仍需在石头和布之间随机选择，避免行为过于容易预测。", finish: "双方所有手势卡用完后结束，胜局多的一方获胜。每轮后可以看公开库存、均衡建议和 AI 对你历史偏好的分析。", terms: "库存＝每种手势还可使用几次；均衡建议＝即使对手知道你的概率，也难以稳定利用你的随机方案；适应＝AI 根据你过去偏爱哪种手势调整。" },
    blackjack: { role: "你是玩家，与按固定规则行动的庄家比较点数。普通模式保留决策压力；练习模式会在每次操作后对照基础策略给出反馈。", example: "例：你有 10+6=16 点，庄家明牌是 10。练习模式会在你选择后说明该操作是否匹配基础策略，并显示这个规则集下建议的动作。", finish: "你爆牌时立即输；你停牌或加倍后庄家自动补牌，最后不爆牌且更接近 21 的一方获胜，同点为和局。当前完整可用动作是要牌、停牌和加倍；分牌、投降、保险尚未实现。", terms: "要牌＝再抽一张；停牌＝不再抽；加倍＝赌注翻倍且只抽一张；软牌＝有 A 暂时按 11 计算的手牌；基础策略最优性只适用于页面注明的固定规则。" },
    "liars-dice": { role: "你和 AI 各有五颗隐藏骰子。双方看不到对方点数，只能通过越来越高的公开叫价传递信息或诈唬。", example: "例：你手里有两个 4 和一个 1。因为 1 是万能牌，你已知道全桌至少有三个可算作 4。叫“3×4”很安全；AI 若叫到“7×4”，你需要判断它真的有很多 4，还是在虚张声势。", finish: "当任一方质疑时揭开所有骰子。实际匹配数量达到叫价，质疑者输；数量不足，最后叫价者输。赢一轮得 1 分，可继续开始下一轮。", terms: "叫价 3×4＝声称全桌至少有三个 4（包括可作万能牌的 1）；加注＝提高数量，或数量不变时提高点数；质疑＝认为当前叫价不成立。" },
    mastermind: { role: "这是经典 Bulls and Cows（几A几B）数字推理。AI 从 0–9 中秘密选择四个不重复数字，包括 0123 这样的前导零密码。你看到的不是答案，而是逐轮反馈形成的信息集。", example: "例：答案假设为 0-3-5-6，你猜 0-2-6-4。数字 0 的位置也正确，因此位置正确为 1；数字 6 存在但位置错误，因此错位正确为 1；2 和 4 不在密码中。", finish: "十次之内得到 4 个位置正确即获胜；十次仍未破解则答案揭晓。建议策略最小化下一轮最大的反馈分组，再比较平均剩余候选；它是强而快速的单步 minimax 启发式，不是已经证明的全局最少平均步数策略。", terms: "候选数量＝与全部历史反馈一致的密码数；信息集＝你当前无法区分的所有候选；最坏剩余＝采用该建议后，无论收到哪种反馈，最大反馈分组的大小。" },
    "guess-who": { role: "AI 秘密选择一张身份卡，但所有人的外貌属性和全部问题都公开。你的任务不是靠运气点人，而是利用每次公开的是非答案系统地缩小信息集。", example: "例：还剩 Ada、Bruno、Cleo、Dante 四人，其中两人戴眼镜。提问“是否戴眼镜？”无论答案是什么都只剩两人，因此是 2/2 的平衡切分；4/0 的问题则完全没有信息。", finish: "确认正确身份立即获胜；错误身份会被排除但消耗一回合。第 8 回合仍未猜中则失败并揭晓答案。精确策略在当前固定模型中平均 5.667 回合、最坏 6 回合。", terms: "候选＝与所有公开答案一致的人；信息分割＝问题把候选分成“是/否”两组；期望剩余＝按两种回答概率加权后的平均候选数；精确最优只针对本页固定角色与问题库。" },
    "hidden-pursuit": { role: "你控制两名公开位置的侦探，AI 控制一名隐藏目标。目标每回合必须移动，并公开乘坐出租车还是公交车；只有规定回合才公开实际位置。", example: "例：目标第 3 回合在 8 号节点现身，下一回合公开乘坐公交。你应把候选缩小到所有从 8 号经公交可达、且未被侦探占据的节点，再用 A、B 分别封锁出口。", finish: "任一侦探落到目标所在节点时立即抓捕；如果目标没有合法出口也算被包围。目标完成第 12 次移动仍未被抓则逃脱。", terms: "候选节点＝与所有交通信号、现身记录和落空搜查相容的位置；交通信号＝只公开线路类型，不公开终点；最后现身＝最近一次强制公开的位置，不保证目标现在仍在那里。" },
    battleship: { role: "你和 AI 在相互隔离的海域秘密部署舰队。标准、扩展和大型地图分别为 10×10、12×12、15×15；你只能看到自己的彩色舰船，敌舰通过命中反馈逐步暴露。", example: "例：你把蓝色长度 4 舰旋转为垂直方向，然后向敌方 B7 开火并命中。下一炮打 B8：若再次命中，可沿同一方向搜索；若落空，就要考虑舰船可能纵向延伸。15×15 中这两炮属于同一轮齐射，之后 AI 连续还击两炮。", finish: "一艘船的所有格子都被命中时即被击沉；任一方全部舰船沉没时比赛结束。结束后敌方完整彩色舰队会揭晓，便于复盘。", terms: "旋转 90°＝在水平与垂直之间切换；齐射＝一方连续完成本轮全部炮击后另一方行动；候选部署＝与命中、落空和击沉反馈相容的位置总数。" },
    "love-letter": { role: "你和 AI 都只有一张隐藏手牌。牌很少且弃牌完全公开，因此每次行动既会触发角色能力，也会改变对手对你手牌的判断。AI 只能使用它应当知道的信息。", example: "例：5 张卫兵已有 4 张公开离场，而 AI 没有保护。此时 AI 手牌是卫兵的概率很低；若你打出卫兵，应根据剩余牌数猜最可能的高价值角色，而不是平均随机。", finish: "任何一方被角色能力淘汰，该轮立即结束并让胜者得 1 分；牌堆耗尽则比较手牌，较高者获胜。先到 4 分赢得整场比赛。", terms: "公开移除＝双人开局额外翻开的三张牌；信念概率＝根据你的手牌、公开移除和双方弃牌估计的对手手牌分布；保护＝对手效果不能以你为目标，直到你下一回合开始。" },
    investment: { role: "你是赔率分析师，与五种风格的 AI 管理人参加虚拟资金淘汰赛。你能看到校准成功率，但对手本轮的选择在结算前保密。", example: "1:1、55% 成功率的期望回报是 +10%，Kelly 仓位为 10%。投入 25% 能更快抢排名，但失败也会损失 25%。", finish: "第 4、7、10 轮淘汰资金最低者；你出局即失败。活到第 12 轮后，资金第一才获胜。", terms: "净赔率＝成功时相对本金的净利润；期望回报＝平均收益率；Kelly＝最大化长期对数增长的理论仓位；存活率与夺冠率并非同一目标。" },
    goofspiel: { role: "这是一个同时行动的有限手牌竞价游戏。奖牌价值公开，但双方本轮用哪张牌在提交前互相隐藏；高牌不一定应该立刻用在高奖牌上，因为剩余库存决定后续威胁。", example: "例：本轮奖牌为 3，你剩 1、3、4，AI 剩 1、2、4。出 4 几乎能确保 3 分，却会失去以后压制 AI 的最高牌；出 3 可能保留 4，但要承担 AI 也出 4 的风险。", finish: "每轮揭晓双方竞价牌并结算奖牌，平局奖牌作废。四轮后总分高者获胜，同分为和局。", terms: "当前奖牌＝本轮可争夺分数；竞价牌＝每张整场只能使用一次；混合策略＝按多个概率随机选择，使对手无法稳定利用你的规律；未来价值＝从当前状态开始、双方最优时你的预期分差。" },
  },
  en: {
    cases: { role: "You are a TV-game contestant. Twenty-six cases hide prizes from tiny amounts to one million. You eliminate prizes and decide whether to accept the banker's cash offer.", example: "After a reveal, the offer window keeps the latest values, every remaining value, and their arithmetic mean visible. You may spend the game's only counter-offer now; rejection forces play to continue.", finish: "A deal or accepted counter settles immediately. Reject everything and the kept case is revealed with a clear final payout.", terms: "Expected remaining value is the arithmetic mean of unrevealed prizes. The risk-adjusted reference is floored at zero so the UI never presents a confusing negative currency amount." },
    worm: { role: "You are the searcher; the worm actively avoids capture. You cannot see it and must reason from the rule that every miss forces it to move to a neighboring hole.", example: "Example: after you miss at hole 2, a worm formerly at 1 can only move to 2, while one at 3 may move to 2 or 4. The possible-position display updates these paths.", finish: "Capture is guaranteed only when your check covers every remaining legal location. The specific hint and complete sequence remain hidden until you deliberately reveal them.", terms: "Possible positions fit all history. Parity flips after every mandatory move. A guaranteed strategy wins against every legal escape path." },
    pirates: { role: "You are senior pirate A. You propose how to split 100 coins. If the vote fails, A dies and the next pirate proposes, so everyone compares the present offer with that future outcome.", example: "Example: if C expects 1 coin after A dies, offering C 1 is normally insufficient; 2 is better than C's continuation payoff and can buy the vote.", finish: "Submit allocations totaling exactly 100. Enough yes votes pass the plan and keep A alive; otherwise A dies. Your challenge is buying enough votes as cheaply as possible.", terms: "Backward induction solves later councils first and works back. Continuation payoff is a pirate's expected survival and gold after rejection." },
    "kuhn-poker": { role: "This is poker reduced to J, Q, and K. The AI always acts first and you always act second. Basic mode is deliberately exploitable; Advanced is exact GTO.", example: "If you hold Q and the AI bets, it may hold K for value or J as a bluff. Calling pays 1 more to reveal; folding loses the ante but limits the loss.", finish: "A fold or completed check/call sequence settles the hand. The second-seat GTO value is +1/18 chip per hand; a best response to Basic reaches +1/6. These are exact long-run expectations, not guaranteed hand outcomes.", terms: "Check adds nothing. Bet adds 1. Call matches and reveals. GTO is an equilibrium from which no unilateral deviation earns more. Switching mode resets the score." },
    "e-card": { role: "You and the AI alternate Emperor and Slave sides. Emperor is usually strong, but Slave beats Emperor for a larger reward, so timing the unique special card is the central decision.", example: "Example: as Slave, you spend citizens on early probes. If you play Slave exactly when the AI commits Emperor, you score the upset; against Citizen, Slave loses.", finish: "A decisive non-citizen tie outcome ends and scores the round, then roles swap. Track which cards were consumed and infer when the AI will commit its special card.", terms: "Emperor beats Citizen; Citizen beats Slave; Slave beats Emperor. Citizen versus Citizen consumes both and continues." },
    "restricted-rps": { role: "This is Rock-Paper-Scissors with limited cards. Every move you spend changes what remains possible later, and both inventories are public.", example: "Example: with 1 Rock, 0 Scissors, and 2 Paper left, the AI knows Scissors is impossible. Randomizing between Rock and Paper keeps your choice less predictable.", finish: "The match ends when all cards are used; more round wins takes the match. Review inventory, equilibrium guidance, and AI adaptation after each reveal.", terms: "Inventory is remaining uses. Equilibrium guidance is a mixture that is hard to exploit. Adaptation is the AI reacting to your historical bias." },
    blackjack: { role: "You compare your hand with a fixed-rule dealer. Normal mode preserves the decision challenge; Practice mode grades each completed action against basic strategy.", example: "With 16 against a dealer 10, Practice mode waits for your choice, then explains whether it matched the rule-scoped recommendation.", finish: "Bust loses immediately. Stand or Double starts dealer resolution. Hit, Stand, and Double are complete; Split, Surrender, and Insurance are not yet implemented.", terms: "Hit draws; Stand stops; Double doubles the stake and draws once. Basic-strategy optimality applies only to the displayed fixed rules." },
    "liars-dice": { role: "You and the AI each hold five hidden dice. Public bids rise while private dice stay secret, so every bid can be information or a bluff.", example: "Example: two 4s and one wild 1 give you three known matches for face 4. A bid of 3×4 is safe; after the AI raises to 7×4, decide whether its private hand supports that claim.", finish: "A challenge reveals all dice. If the bid's quantity exists, the challenger loses; otherwise the last bidder loses. The winner scores one point.", terms: "3×4 claims at least three 4-matches across both hands. Raise increases quantity or face. Challenge says the current claim is false." },
    mastermind: { role: "This is classic Bulls and Cows. The AI secretly chooses four distinct digits from 0–9, including leading-zero codes such as 0123. Public feedback transforms the set of hidden worlds after every guess.", example: "If the code is 0-3-5-6 and you guess 0-2-6-4, digit 0 gives one exact match and digit 6 gives one misplaced match; 2 and 4 are absent.", finish: "Four exact matches within ten guesses wins; otherwise the code is revealed. The adviser minimizes the largest next feedback bucket, then expected survivors. It is a strong, responsive one-step minimax heuristic, not a proof of globally minimal average guesses.", terms: "Candidate count is the number of codes consistent with every clue. The information set is the candidates you cannot yet distinguish. Worst-case remaining is the largest possible feedback bucket after the suggested guess." },
    "guess-who": { role: "The AI secretly selects one identity card, while every visible trait and every permitted question is public. Use truthful yes/no answers to shrink your information set instead of guessing blindly.", example: "Suppose Ada, Bruno, Cleo, and Dante remain and exactly two wear glasses. Asking about glasses creates a 2/2 split, so either answer leaves two candidates. A 4/0 question provides no information and is disabled.", finish: "A correct confirmed identity wins. A wrong identity is eliminated but costs a turn. Failing to identify the person by turn eight reveals the answer. The exact fixed-model policy averages 5.667 turns and needs at most six.", terms: "Candidate means consistent with every public answer. Information split is the Yes/No partition. Expected remaining is the probability-weighted next candidate count. Exact optimality applies only to this roster and question bank." },
    "hidden-pursuit": { role: "You control two visible detectives while the AI controls a hidden fugitive. Every fugitive move publicly reveals Taxi or Bus, but the destination appears only on scheduled reveal rounds.", example: "Example: the fugitive appears at node 8 after round 3, then reports Bus. The next information set is every unblocked node reachable from 8 by a Bus edge; position A and B to cover separate exits.", finish: "Landing on the fugitive captures immediately; leaving no legal escape also counts as containment. The fugitive wins by completing move 12.", terms: "Candidate nodes fit every signal, reveal, and failed search. A transport signal reveals edge type only. Last seen is historical and may not be the current location." },
    battleship: { role: "You and the AI deploy private fleets on separate 10×10, 12×12, or 15×15 seas. You see your individually colored ships only; enemy ships emerge through hit feedback.", example: "Example: rotate the blue length-4 ship vertically, then hit B7. Firing at B8 tests an extension; on 15×15 those two shots form one salvo before the AI returns two shots.", finish: "A ship sinks when every cell is hit. The match ends when either fleet is gone, then the complete colored enemy fleet is revealed for review.", terms: "Rotate 90° switches horizontal and vertical. A salvo means one side completes every shot in its turn before the other responds. Candidate placements count legal positions consistent with feedback." },
    "love-letter": { role: "You and the AI each keep one hidden card. The tiny deck and public discards make every role effect both an action and a signal. The AI uses only information it is entitled to know.", example: "If four of five Guards are already public, the opposing hand is unlikely to be a Guard. Playing your Guard should target the most frequent remaining non-Guard role rather than guessing uniformly.", finish: "An effect that eliminates a player ends the round for one point. If the deck empties, the higher hand wins. The first player to four points wins the match.", terms: "Face-up removals are the three extra cards revealed in a two-player setup. Belief probability is estimated from your hand and all public cards. Protection prevents opposing effects until your next turn." },
    investment: { role: "You are the odds analyst facing five AI managers in a virtual-capital elimination tournament. You see calibrated probabilities; rival choices remain private until settlement.", example: "At 1:1 and 55% success, expected return is +10% and Kelly is 10%. Staking 25% gains rank faster but loses 25% on failure.", finish: "The lowest bankroll leaves after rounds 4, 7, and 10. Your elimination ends the game; after round 12, only first place wins.", terms: "Net odds are profit relative to stake. Expected return is average profit per staked unit. Kelly maximizes long-run log growth. Survival and title probability are different objectives." },
    goofspiel: { role: "This is simultaneous bidding with a finite hand. The prize is public, but each current bid stays hidden until both commit. Spending the largest card now changes every threat available later.", example: "With prize 3, your 1/3/4 against the AI's 1/2/4 creates a tradeoff: bid 4 to strongly contest three points, or preserve it and risk losing the prize.", finish: "Each reveal awards the prize to the higher bid; a tie discards it. After four rounds, higher total prize points wins and equal scores draw.", terms: "Prize is the points at stake. A bid card is usable once. Mixed strategy randomizes across cards so a rival cannot exploit a fixed pattern. Future value is your optimal expected score difference from the public state." },
  },
};

const ruleLabels = {
  zh: { role: "先弄懂：你在做什么", goal: "你的目标", steps: "按这个顺序操作", example: "看一个具体例子", finish: "怎样判断结束与胜负", terms: "页面上的词是什么意思" },
  en: { role: "First: what are you doing?", goal: "Your goal", steps: "Do this in order", example: "A concrete example", finish: "How the game ends", terms: "Terms on the screen" },
};

function installRulesButtons() {
  document.querySelectorAll(".game-heading").forEach((heading) => {
    if (heading.querySelector(".rules-button")) return;
    const view = heading.closest(".view");
    const gameId = { gameView: "cases", wormView: "worm", pirateView: "pirates", pokerView: "kuhn-poker", eCardView: "e-card", rpsView: "restricted-rps", liarView: "liars-dice", blackjackView: "blackjack", mastermindView: "mastermind", guessWhoView: "guess-who", pursuitView: "hidden-pursuit", battleshipView: "battleship", loveLetterView: "love-letter", investmentView: "investment", goofspielView: "goofspiel" }[view?.id];
    if (!gameId) return;
    const button = document.createElement("button");
    button.className = "rules-button";
    button.dataset.rulesGame = gameId;
    button.addEventListener("click", () => openRules(gameId));
    const restart = heading.querySelector(".secondary-button");
    heading.insertBefore(button, restart || null);
  });
}

function openRules(gameId) {
  if (!openRulesGameId) rulesReturnFocus = document.activeElement;
  openRulesGameId = gameId;
  const lines = rulesCopy[language][gameId] || [];
  const details = ruleDetails[language][gameId] || {};
  const labels = ruleLabels[language];
  const [goal, ...steps] = lines;
  $("#rulesTitle").textContent = `${gamesCopy[language][gameId]?.[0] || gameId} · ${tr("rulesTitle")}`;
  $("#rulesBody").innerHTML = `
    <section class="rules-intro"><h3>${labels.role}</h3><p>${details.role || ""}</p></section>
    <section class="rules-section"><h3>${labels.goal}</h3><p>${goal || ""}</p></section>
    <section class="rules-section"><h3>${labels.steps}</h3><ol>${steps.map((line) => `<li>${line}</li>`).join("")}</ol></section>
    <section class="rules-example"><h3>${labels.example}</h3><p>${details.example || ""}</p></section>
    <section class="rules-section"><h3>${labels.finish}</h3><p>${details.finish || ""}</p></section>
    <section class="rules-terms"><h3>${labels.terms}</h3><p>${details.terms || ""}</p></section>`;
  $("#rulesModal").classList.remove("hidden");
  $("#rulesModal .rules-card").scrollTop = 0;
  syncModalState();
  window.requestAnimationFrame(() => $("#rulesClose").focus());
}

function closeRules() {
  if (!openRulesGameId) return;
  const gameId = openRulesGameId;
  const returnFocus = rulesReturnFocus;
  openRulesGameId = null;
  rulesReturnFocus = null;
  $("#rulesModal").classList.add("hidden");
  syncModalState();
  const fallback = document.querySelector(`[data-rules-game="${gameId}"]`);
  const target = returnFocus?.getClientRects().length ? returnFocus : fallback;
  target?.focus();
}

function visibleModal() {
  if (!$("#rulesModal").classList.contains("hidden")) return $("#rulesModal");
  if (!$("#offerModal").classList.contains("hidden")) return $("#offerModal");
  return null;
}

function syncModalState() {
  const modal = visibleModal();
  const hasModal = Boolean(modal);
  document.body.classList.toggle("modal-open", hasModal);
  document.querySelector("header").inert = hasModal;
  document.querySelector("main").inert = hasModal;
  if (modal?.id === "offerModal" && !offerModalOpen) {
    window.requestAnimationFrame(() => {
      const target = $("#counterOfferPanel").classList.contains("hidden")
        ? $("#dealButton")
        : $("#counterOfferInput");
      target.focus();
    });
  }
  offerModalOpen = modal?.id === "offerModal";
}

function tr(key) { return copy[language][key] ?? key; }

function setOperationPending(pending) {
  actionPending = pending;
  document.querySelector("main").toggleAttribute("aria-busy", pending);
  const status = $("#operationStatus");
  status.textContent = tr("operationPending");
  status.classList.toggle("hidden", !pending);
}

function applyLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.title = language === "zh" ? "AIP · 非对称博弈实验室" : "AIP · Asymmetric Games Lab";
  $("#homeButton").setAttribute("aria-label", language === "zh" ? "返回游戏大厅" : "Return to game lobby");
  $("#rulesClose").setAttribute("aria-label", tr("closeRules"));
  $("#operationStatus").textContent = tr("operationPending");
  money = new Intl.NumberFormat(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: 2 });
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = tr(element.dataset.i18n);
  });
  installRulesButtons();
  document.querySelectorAll(".rules-button").forEach((button) => { button.textContent = tr("rulesTitle"); });
  $("#languageZh").classList.toggle("active", language === "zh");
  $("#languageEn").classList.toggle("active", language === "en");
  $("#languageZh").setAttribute("aria-pressed", String(language === "zh"));
  $("#languageEn").setAttribute("aria-pressed", String(language === "en"));
  renderLobby();
  if (currentState) render();
  if (openRulesGameId) openRules(openRulesGameId);
}

function setLanguage(nextLanguage) {
  language = nextLanguage;
  writePreference("aip-language", language);
  applyLanguage();
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(tr("connectionFailed"));
  }
  const raw = await response.text();
  let data;
  try { data = raw ? JSON.parse(raw) : {}; } catch (_error) {
    throw new Error(tr("invalidResponse"));
  }
  if (!response.ok) {
    const message = String(data.error || "");
    throw new Error(/expired session|unknown or expired/i.test(message) ? tr("sessionExpired") : message || tr("operationFailed"));
  }
  return data;
}

function showToast(message) {
  const toast = $("#toast");
  if (toastTimer !== null) window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.remove("hidden");
  toastTimer = window.setTimeout(() => {
    toast.classList.add("hidden");
    toastTimer = null;
  }, 2400);
}

async function loadLobby() {
  const { games } = await request("/api/games");
  lobbyGames = games;
  renderLobby();
  routeReady = true;
  await applyRoute();
}

function renderLobby() {
  if (!lobbyGames.length) return;
  $("#gameGrid").innerHTML = lobbyGames.map((game, index) => {
    const localized = gamesCopy[language][game.id] || [game.title, game.summary, game.playerMode];
    return `
    <button class="game-card" data-game="${game.id}" ${game.available ? "" : "disabled"}>
      <span class="game-index">${String(index + 1).padStart(2, "0")}</span>
      <h2>${localized[0]}</h2>
      <p>${localized[1]}</p>
      <span class="difficulty-badge">${language === "zh" ? "难度" : "Difficulty"} · ${difficultyCopy[language][game.id] || "—"}</span>
      <span class="game-mode">${localized[2]}</span>
      <span class="game-cta">${game.available ? tr("playNow") : tr("comingSoon")}</span>
    </button>
  `; }).join("");
  document.querySelectorAll(".game-card:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => navigateToGame(button.dataset.game));
  });
}

function routeGameId() {
  const match = window.location.hash.match(/^#game\/([^/]+)$/);
  if (!match) return null;
  try { return decodeURIComponent(match[1]); } catch (_error) { return null; }
}

function navigateToGame(gameId) {
  const hash = `#game/${encodeURIComponent(gameId)}`;
  if (window.location.hash === hash) startGame(gameId);
  else window.location.hash = hash;
}

function navigateToLobby() {
  if (window.location.hash === "#lobby") showLobby();
  else window.location.hash = "#lobby";
}

async function applyRoute() {
  if (!routeReady) return;
  const gameId = routeGameId();
  const available = lobbyGames.some((game) => game.id === gameId && game.available);
  if (gameId && available) {
    if (currentGameId === gameId && currentState) showGameView(gameId);
    else await startGame(gameId);
    return;
  }
  if (window.location.hash !== "#lobby") {
    window.history.replaceState(null, "", "#lobby");
  }
  showLobby();
}

function showGameView(gameId) {
  $("#lobbyView").classList.add("hidden");
  Object.entries(gameViews).forEach(([id, viewId]) => {
    $(`#${viewId}`).classList.toggle("hidden", id !== gameId);
  });
  window.scrollTo(0, 0);
  render();
}

async function startGame(gameId = "cases", options = {}) {
  if (actionPending) return;
  const controller = new AbortController();
  activeOperation = controller;
  setOperationPending(true);
  try {
    const gameOptions = gameId === "cases"
      ? { riskTolerance: 100000, ...options }
      : gameId === "kuhn-poker"
        ? { mode: pokerMode, ...options }
        : gameId === "goofspiel"
          ? { mode: goofspielMode, ...options }
        : options;
    const result = await request("/api/sessions", {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({ gameId, options: gameOptions }),
    });
    if (controller.signal.aborted) return;
    sessionId = result.sessionId;
    currentState = result.state;
    currentGameId = gameId;
    if (gameId === "kuhn-poker") pokerMode = currentState.mode;
    if (gameId === "goofspiel") goofspielMode = currentState.mode;
    if (gameId === "pirates") pirateDraft = currentState.pirates.map(() => 0);
    if (gameId === "worm") wormDisclosure = 0;
    if (gameId === "guess-who") guessWhoSelected = null;
    if (gameId === "investment") { investmentOffer = currentState.suggestion?.offerId || "A"; investmentFraction = 0.25; }
    showGameView(gameId);
    const rulesSeenKey = `aip-rules-seen-${gameId}`;
    if (!readPreference(rulesSeenKey)) {
      writePreference(rulesSeenKey, "1");
      openRules(gameId);
    }
  } catch (error) {
    if (error.name !== "AbortError") showToast(error.message);
  } finally {
    if (activeOperation === controller) {
      activeOperation = null;
      setOperationPending(false);
    }
  }
}

async function act(action, payload = {}) {
  if (actionPending) return;
  const controller = new AbortController();
  activeOperation = controller;
  setOperationPending(true);
  try {
    const result = await request(`/api/sessions/${sessionId}/actions`, {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({ action, payload }),
    });
    if (controller.signal.aborted) return;
    currentState = result.state;
    if (currentState.gameId === "guess-who" && ["ask_question", "guess_character", "new_game"].includes(action)) {
      guessWhoSelected = null;
    }
    render();
    if (currentState.gameId === "mastermind" && ["submit_guess", "new_game"].includes(action)) {
      $("#mastermindInput").value = "";
    }
  } catch (error) {
    if (error.name !== "AbortError") showToast(error.message);
  } finally {
    if (activeOperation === controller) {
      activeOperation = null;
      setOperationPending(false);
    }
  }
}

function render() {
  renderFirstTurnGuide();
  if (currentState.gameId === "guess-who") {
    renderGuessWho();
    return;
  }
  if (currentState.gameId === "hidden-pursuit") {
    renderHiddenPursuit();
    return;
  }
  if (currentState.gameId === "battleship") {
    renderBattleship();
    return;
  }
  if (currentState.gameId === "love-letter") {
    renderLoveLetter();
    return;
  }
  if (currentState.gameId === "investment") {
    renderInvestment();
    return;
  }
  if (currentState.gameId === "goofspiel") {
    renderGoofspiel();
    return;
  }
  if (currentState.gameId === "blackjack") {
    renderBlackjack();
    return;
  }
  if (currentState.gameId === "restricted-rps") {
    renderRestrictedRps();
    return;
  }
  if (currentState.gameId === "liars-dice") {
    renderLiarDice();
    return;
  }
  if (currentState.gameId === "mastermind") {
    renderMastermind();
    return;
  }
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
  const finalPayout = Number.isFinite(state.payout) ? formatMoney(state.payout) : (language === "zh" ? "金额待确认" : "Payout unavailable");
  const acceptedDeal = ["deal", "counter_deal"].includes(state.result?.kind);
  const instructions = language === "zh" ? {
    choose: "第一步：点击一个箱子作为你的保留箱",
    opening: `本轮请再打开 ${state.opensRemaining} 个箱子，完成后银行家会报价`,
    offer: state.isFinalOffer ? "最终阶段：只剩你的保留箱，请决定接受最终报价还是直接揭晓" : "银行家正在等待：接受报价，或拒绝并继续开箱",
    finished: acceptedDeal ? `本局结束 · 你最终获得 ${finalPayout}` : `最终揭晓 · 你的保留箱奖金为 ${finalPayout}`,
  } : {
    choose: "First: click one case to keep",
    opening: `Open ${state.opensRemaining} more case(s); the banker will then make an offer`,
    offer: state.isFinalOffer ? "Final stage: only your kept case remains. Take the final offer or reveal it" : "The banker is waiting: take the offer or reject it and keep opening",
    finished: acceptedDeal ? `Game over · You receive ${finalPayout}` : `Final reveal · Your kept case pays ${finalPayout}`,
  };
  $("#instruction").textContent = instructions[state.phase];
  const chosenCase = state.chosenCase ? findCase(state.chosenCase) : null;
  $("#chosenStrip").textContent = state.chosenCase
    ? (language === "zh"
      ? `你的保留箱：${state.chosenCase} 号${state.phase === "finished" ? ` · 最终金额 ${Number.isFinite(chosenCase?.value) ? formatMoney(chosenCase.value) : "尚未取得"}` : " · 游戏结束前不会打开"}`
      : `Your kept case: No. ${state.chosenCase}${state.phase === "finished" ? ` · Final value ${Number.isFinite(chosenCase?.value) ? formatMoney(chosenCase.value) : "unavailable"}` : " · stays sealed until the game ends"}`)
    : (language === "zh" ? "尚未选择保留箱：请点击下方任意箱子开始" : "No kept case yet: click any case below to begin");

  $("#caseGrid").innerHTML = state.cases.map((item) => {
    const label = item.status === "opened" || (state.phase === "finished" && item.status === "chosen") ? formatMoney(item.value) : item.id;
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
    const recentReveals = state.history.filter((item) => item.kind === "reveal").slice(-state.openedThisRound);
    const revealText = recentReveals.map((item) => formatMoney(item.value)).join(" · ");
    $("#offerContext").textContent = state.isFinalOffer
      ? (language === "zh" ? `这是最终报价。接受可立即获得 ${formatMoney(state.offer)}；拒绝后会直接打开 ${state.chosenCase} 号保留箱并领取其中金额。` : `This is the final offer. Take ${formatMoney(state.offer)} now, or reject it to reveal and receive kept case No. ${state.chosenCase}.`)
      : (language === "zh" ? `本轮刚打开：${revealText || "—"}。还有 ${remaining} 个可能金额；接受即结束，拒绝则继续开箱。` : `Just revealed: ${revealText || "—"}. ${remaining} values remain; Deal ends the game and No Deal continues.`);
    $("#offerComparison").innerHTML = `<div><span>${language === "zh" ? "银行家报价" : "Bank offer"}</span><strong>${formatMoney(state.offer)}</strong></div><div><span>${language === "zh" ? "剩余箱子价值期望" : "Expected remaining value"}</span><strong>${formatMoney(state.metrics.expectedValue)}</strong></div><div><span>${language === "zh" ? "报价仅为期望的" : "Offer as % of expectation"}</span><strong>${(state.metrics.offerRatio * 100).toFixed(1)}%</strong></div>`;
    $("#offerRemainingValues").innerHTML = state.prizeBoard.filter((prize) => prize.remaining).map((prize) => `<span>${formatMoney(prize.value)}</span>`).join("");
    $("#counterOfferPanel").classList.toggle("hidden", !state.counterOfferAvailable);
    if (state.counterOfferAvailable) {
      $("#counterOfferInput").value = state.suggestedCounterOffer;
      $("#counterOfferInput").min = (state.offer + 0.01).toFixed(2);
    }
    $("#dealButton").textContent = state.isFinalOffer ? (language === "zh" ? "接受最终报价" : "Take final offer") : tr("acceptOffer");
    $("#noDealButton").textContent = state.isFinalOffer ? (language === "zh" ? "拒绝并揭晓保留箱" : "Reject and reveal my case") : tr("rejectOffer");
  }
  syncModalState();
}

function renderFirstTurnGuide() {
  document.querySelectorAll(".first-turn-guide").forEach((node) => node.remove());
  const state = currentState;
  const visible = {
    worm: state.gameId === "worm" && state.phase === "playing" && state.turn === 0,
    "kuhn-poker": state.gameId === "kuhn-poker" && state.handNumber === 1 && state.phase === "playing" && !state.history.some((item) => item.actor === "player"),
    "liars-dice": state.gameId === "liars-dice" && state.roundNumber === 1 && state.phase === "bidding" && state.history.length === 0,
    "love-letter": state.gameId === "love-letter" && state.roundNumber === 1 && state.phase === "player_turn" && state.history.length === 0,
    investment: state.gameId === "investment" && state.roundNumber === 1 && state.phase === "decision" && !state.lastRound,
    goofspiel: state.gameId === "goofspiel" && state.phase === "bidding" && state.history.length === 0,
    battleship: state.gameId === "battleship" && state.phase === "placement" && state.boardSize === 15,
  }[state.gameId];
  if (!visible) return;
  const guides = language === "zh" ? {
    worm: ["首回合怎么做", ["先任选一个洞开始检查，观察失手后可能位置如何变化。", "虫子每次必须移动到相邻洞，因此奇偶节奏比猜位置更重要。", "页面不会直接展示解法；需要时可主动打开提示或答案。"]],
    "kuhn-poker": ["第一手怎么判断", ["你固定是后手：先看自己的 J、Q 或 K，再阅读 AI 已经公开的过牌或下注。", "AI 过牌后，你可过牌摊牌或下注；AI 下注后，你只能跟注或弃牌。", "只根据自己的牌与公开行动更新判断。基础模式可寻找稳定偏差，高级模式则无法获得超过后手均衡价值的长期优势。"]],
    "liars-dice": ["第一轮怎么叫价", ["先数自己手中的目标点数；除叫 1 点外，1 都是万能点。", "输入一个数量和点数后加注，AI 会选择继续抬价或质疑。", "轮到你面对公开叫价时，可看真实概率再决定加注或质疑。"]],
    "love-letter": ["第一回合怎么出牌", ["你每回合抽到两张牌，必须打出其中一张。", "若打卫兵，先选择要猜的牌；若打王子，先选择目标。", "右侧信念概率只依据公开信息，建议是启发式而非已证明的全局最优。"]],
    investment: ["第一轮怎么投资", ["先比较每个方案的成功率、赔率和期望回报。", "再选择投入比例；0% 可以保本，Kelly 比例偏向长期增长。", "每到淘汰轮资金最低者出局，所以生存压力可能改变最优仓位。"]],
    goofspiel: ["第一轮怎么竞价", ["先看本轮奖牌分值，再从 1–4 中秘密打出一张牌。", "双方较高者拿走奖牌，同价则奖牌作废；出过的牌不能再用。", "黄色标记只是均衡中的最高频动作，真正的均衡需要按概率随机。"]],
    battleship: ["15×15 大海域提示", ["大型海域采用双方对称的双炮齐射：你连续打两炮后，AI 才还击两炮。", "第一炮后界面会显示本轮还剩一炮，不要误以为AI停住。", "命中后优先沿相邻方向追击；AI面板会公开其搜索模式与覆盖强度。"]],
  } : {
    worm: ["Your first move", ["Probe any hole first and watch how the possible positions change after a miss.", "The worm must move to a neighbor, so parity and rhythm matter more than guessing a location.", "The solution stays hidden unless you deliberately open a hint or the answer."]],
    "kuhn-poker": ["Your first hand", ["You always act second: read your J, Q, or K, then the AI's public Check or Bet.", "After a check, choose showdown or bet; after a bet, choose Call or Fold.", "Use only your card and public actions. Seek a stable leak in Basic mode; Advanced cannot yield more than the second-seat equilibrium value in the long run."]],
    "liars-dice": ["Your opening bid", ["Count matching dice in your hand; ones are wild unless the bid itself is ones.", "Enter a quantity and face, then raise; the AI may raise again or challenge.", "When a bid returns to you, use its probability before raising or challenging."]],
    "love-letter": ["Your first turn", ["You hold two cards each turn and must play one.", "Choose a guess before Guard or a target before Prince.", "Belief probabilities use public information only; the advice is heuristic, not globally proven optimal."]],
    investment: ["Your first investment", ["Compare success probability, odds, and expected return.", "Then choose a stake; 0% preserves capital while Kelly targets long-run growth.", "The lowest bankroll is eliminated at checkpoints, so survival pressure can change the best stake."]],
    goofspiel: ["Your opening bid", ["Read the revealed prize, then secretly spend one card from 1–4.", "The higher bid wins the prize; ties discard it, and spent cards never return.", "The gold card is only the most frequent equilibrium action—the exact policy randomizes."]],
    battleship: ["15×15 sea briefing", ["The large board uses symmetric two-shot salvos: fire twice, then the AI returns two shots.", "After your first shot, the interface shows one shot left; the AI has not stalled.", "After a hit, pursue adjacent cells; the AI panel exposes its search mode and coverage strength."]],
  };
  const [title, steps] = guides[state.gameId];
  const view = $(`#${gameViews[state.gameId]}`);
  const heading = view?.querySelector(".game-heading");
  if (!heading) return;
  const guide = document.createElement("section");
  guide.className = "first-turn-guide panel";
  guide.setAttribute("aria-label", title);
  guide.innerHTML = `<div><span>${language === "zh" ? "新手起步" : "FIRST-TURN GUIDE"}</span><strong>${title}</strong></div><ol>${steps.map((step) => `<li>${step}</li>`).join("")}</ol>`;
  heading.insertAdjacentElement("afterend", guide);
}

function renderModeContract(selector, details) {
  const labels = language === "zh"
    ? { changes: "改变内容", applies: "生效时机", score: "成绩处理" }
    : { changes: "CHANGES", applies: "TAKES EFFECT", score: "SCORE HANDLING" };
  const container = $(selector);
  const rows = Object.keys(labels).map((key) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    const value = document.createElement("span");
    label.textContent = labels[key];
    value.textContent = details[key];
    row.append(label, value);
    return row;
  });
  container.replaceChildren(...rows);
}

function renderBlackjack() {
  const state = currentState;
  const actionNames = language === "zh"
    ? { hit: "要牌", stand: "停牌", double: "加倍", new_round: "下一局" }
    : { hit: "Hit", stand: "Stand", double: "Double", new_round: "Next hand" };
  $("#blackjackRound").textContent = state.roundNumber;
  $("#blackjackBankroll").textContent = signed(state.bankroll);
  $("#blackjackRecord").textContent = `${state.wins} / ${state.losses} / ${state.pushes}`;
  $("#shoeRemaining").textContent = `${state.shoeRemaining} ${language === "zh" ? "张剩余" : "CARDS LEFT"}`;
  $("#playerTotal").textContent = `${state.playerSoft ? (language === "zh" ? "软 " : "Soft ") : ""}${state.playerTotal}`;
  $("#dealerTotal").textContent = state.dealerTotal == null ? (language === "zh" ? "明牌" : "Upcard") : state.dealerTotal;
  $("#playerCards").innerHTML = state.playerHand.map(renderBlackjackCard).join("");
  $("#dealerCards").innerHTML = state.dealerHand.map(renderBlackjackCard).join("") + (state.dealerHoleHidden ? '<div class="blackjack-card hidden-card">?</div>' : "");
  $("#blackjackNormalMode").classList.toggle("active", !blackjackPracticeMode);
  $("#blackjackPracticeMode").classList.toggle("active", blackjackPracticeMode);
  $("#blackjackNormalMode").setAttribute("aria-pressed", String(!blackjackPracticeMode));
  $("#blackjackPracticeMode").setAttribute("aria-pressed", String(blackjackPracticeMode));
  renderModeContract("#blackjackModeDescription", language === "zh"
    ? {
      changes: blackjackPracticeMode ? "开启提交后的基础策略讲评与可选 AI 示范。" : "隐藏策略答案、练习评分与 AI 示范，只保留公开操作记录。",
      applies: "立即作用于当前牌局；切换不会重新发牌。",
      score: blackjackPracticeMode ? "净收益与既有练习成绩保留；只统计此后由玩家亲自提交的练习决策。" : "净收益与既有练习成绩保留；普通模式决策不计入练习吻合率。",
    }
    : {
      changes: blackjackPracticeMode ? "Enables post-decision basic-strategy review and an optional AI demonstration." : "Hides strategy answers, practice grading, and the AI demonstration; only the public action log remains.",
      applies: "Applies immediately to the current hand; switching does not redeal.",
      score: blackjackPracticeMode ? "Bankroll and existing practice results stay; only future human Practice decisions are scored." : "Bankroll and existing practice results stay; Normal decisions do not enter Practice accuracy.",
    });
  $("#blackjackAccuracy").textContent = blackjackPracticeMode && state.practiceAccuracy != null ? `${(state.practiceAccuracy * 100).toFixed(0)}%` : "—";
  $("#blackjackActions").innerHTML = state.legalActions.map((action) => `<button data-blackjack-action="${action}">${actionNames[action]}</button>`).join("");
  document.querySelectorAll("[data-blackjack-action]").forEach((button) => button.addEventListener("click", () => act(button.dataset.blackjackAction, { practice: blackjackPracticeMode })));
  const latestDecision = state.history.slice().reverse().find((item) => item.practiceAssessed);
  $("#blackjackRecommendation").textContent = blackjackPracticeMode
    ? (latestDecision
      ? `${language === "zh" ? "上一操作的正确策略" : "Correct play last decision"}: ${actionNames[latestDecision.recommended]}`
      : (language === "zh" ? "先独立选择；提交后显示正确策略" : "Decide first; the correct play appears afterward"))
    : (language === "zh" ? "普通模式不提前揭示" : "Hidden in normal mode");
  $("#blackjackAiPlay").classList.toggle("hidden", !blackjackPracticeMode);
  $("#blackjackAiPlay").disabled = !blackjackPracticeMode || state.phase !== "player_turn";
  $("#blackjackHeadline").textContent = state.phase === "player_turn"
    ? (language === "zh" ? "根据手牌与庄家明牌做决定" : "Decide from your hand and the dealer upcard")
    : (language === "zh" ? "庄家底牌与最终结果已经揭晓" : "The dealer hole card and result are revealed");
  $("#blackjackHistory").innerHTML = state.history.length ? state.history.map((item) => {
    if (item.actor === "dealer") return `<div><b>${language === "zh" ? "庄家" : "Dealer"}</b><span>${language === "zh" ? "要牌" : "hits"} ${item.card} → ${item.total}</span></div>`;
    const audit = blackjackPracticeMode && item.practiceAssessed
      ? ` · ${item.matched ? (language === "zh" ? "符合基础策略" : "matched basic strategy") : `${language === "zh" ? "正确策略" : "correct play"}: ${actionNames[item.recommended]}`}`
      : "";
    return `<div><b>${item.actor === "ai" ? "AI" : (language === "zh" ? "你" : "You")}</b><span>${actionNames[item.action]}${audit}</span></div>`;
  }).join("") : `<p>${language === "zh" ? "尚无决策记录。" : "No decisions yet."}</p>`;
  const feedback = $("#blackjackPracticeFeedback");
  feedback.classList.toggle("hidden", !blackjackPracticeMode);
  if (blackjackPracticeMode) {
    feedback.className = `practice-feedback ${latestDecision ? (latestDecision.matched ? "correct" : "review") : "waiting"}`;
    feedback.textContent = latestDecision
      ? (latestDecision.matched
        ? (language === "zh" ? `符合基础策略：${actionNames[latestDecision.action]} 是这个规则集下的正确操作。` : `Basic strategy matched: ${actionNames[latestDecision.action]} was correct for this rule set.`)
        : (language === "zh" ? `本次选择了${actionNames[latestDecision.action]}；基础策略应为${actionNames[latestDecision.recommended]}。` : `You chose ${actionNames[latestDecision.action]}; basic strategy called for ${actionNames[latestDecision.recommended]}.`))
      : (language === "zh" ? "做出一次操作后，AI 会立即解释是否符合基础策略。" : "Make a decision and the AI will immediately grade it against basic strategy.");
  }
  $("#blackjackResult").classList.toggle("hidden", state.phase !== "finished");
  if (state.phase === "finished") {
    const labels = language === "zh" ? { player: "你赢了", dealer: "庄家获胜", push: "平局" } : { player: "You win", dealer: "Dealer wins", push: "Push" };
    $("#blackjackResult").className = `blackjack-result ${state.result.winner}`;
    $("#blackjackResult").textContent = `${labels[state.result.winner]} · ${signed(state.result.delta)}`;
  }
}

function renderBlackjackCard(card) {
  const red = ["A", "3", "5", "7", "9", "J", "K"].includes(card);
  return `<div class="blackjack-card ${red ? "red" : ""}">${card}</div>`;
}

function renderRestrictedRps() {
  const state = currentState;
  const moveNames = language === "zh"
    ? { rock: "石头", paper: "布", scissors: "剪刀" }
    : { rock: "Rock", paper: "Paper", scissors: "Scissors" };
  const moveMarks = { rock: "●", paper: "▰", scissors: "✕" };
  $("#rpsRound").textContent = `${state.roundNumber} / ${state.roundsTotal}`;
  $("#rpsPlayerScore").textContent = state.playerScore;
  $("#rpsAiScore").textContent = state.aiScore;
  $("#rpsDraws").textContent = state.draws;
  $("#rpsCards").innerHTML = Object.entries(state.playerInventory).map(([move, count]) => `
    <button class="rps-move ${move}" data-rps-move="${move}" ${count === 0 || state.phase !== "playing" ? "disabled" : ""}>
      <strong>${moveMarks[move]}</strong><span>${moveNames[move]}</span><b>×${count}</b>
    </button>`).join("");
  document.querySelectorAll("[data-rps-move]:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => act("play_move", {move: button.dataset.rpsMove}));
  });
  $("#rpsAiInventory").innerHTML = Object.entries(state.aiInventory).map(([move, count]) => `<span>${moveNames[move]} ×${count}</span>`).join("");
  const last = state.history[state.history.length - 1];
  $("#rpsReveal").innerHTML = last
    ? `<span>${moveMarks[last.playerMove]}<small>${moveNames[last.playerMove]}</small></span><b>VS</b><span>${moveMarks[last.aiMove]}<small>${moveNames[last.aiMove]}</small></span>`
    : '<span>?</span><b>VS</b><span>?</span>';
  const winnerText = state.playerScore > state.aiScore
    ? (language === "zh" ? "你领先" : "You lead")
    : state.playerScore < state.aiScore
      ? (language === "zh" ? "AI 领先" : "AI leads")
      : (language === "zh" ? "比分持平" : "Scores tied");
  $("#rpsHeadline").textContent = state.phase === "finished"
    ? `${language === "zh" ? "比赛结束" : "Match over"} · ${winnerText}`
    : last
      ? (last.outcome === "draw" ? (language === "zh" ? "这一轮平局" : "That round was a draw") : last.outcome === "player" ? (language === "zh" ? "你赢下这一轮" : "You won that round") : (language === "zh" ? "AI 赢下这一轮" : "AI won that round"))
      : (language === "zh" ? "选择一张有限卡牌" : "Choose a limited card");
  $("#rpsSubline").textContent = state.phase === "finished"
    ? (language === "zh" ? "所有库存均已耗尽，可以重新开始观察另一条策略轨迹。" : "All cards are exhausted. Restart to explore another strategy path.")
    : (language === "zh" ? "AI 同时隐藏出牌；使用过的卡不能再使用。" : "The AI chooses simultaneously; spent cards cannot be reused.");
  $("#rpsRecommendation").innerHTML = probabilityBars(state.equilibriumRecommendation, moveNames);
  if (state.lastAnalysis) {
    const analysis = state.lastAnalysis;
    $("#rpsAnalysis").innerHTML = `<p>${language === "zh" ? `AI 保留 ${(100 - analysis.exploitWeight * 100).toFixed(0)}% 的均衡基线，并用 ${(analysis.exploitWeight * 100).toFixed(0)}% 权重尝试针对你的模式；本轮最佳回应为${moveNames[analysis.bestResponse]}。` : `The AI kept ${(100 - analysis.exploitWeight * 100).toFixed(0)}% equilibrium weight and used ${(analysis.exploitWeight * 100).toFixed(0)}% to exploit your pattern; its best response was ${moveNames[analysis.bestResponse]}.`}</p>${probabilityBars(analysis.finalDistribution, moveNames)}`;
  } else {
    $("#rpsAnalysis").textContent = language === "zh" ? "第一轮结束后显示 AI 实际采用的混合概率。" : "The AI's actual mixed probabilities appear after round one.";
  }
  $("#rpsHistory").innerHTML = state.history.slice().reverse().map((item) => `<div><span>${item.round}</span><b>${moveNames[item.playerMove]}</b><em>VS</em><b>${moveNames[item.aiMove]}</b><small>${item.outcome === "draw" ? (language === "zh" ? "平" : "Draw") : item.outcome === "player" ? (language === "zh" ? "胜" : "Win") : (language === "zh" ? "负" : "Loss")}</small></div>`).join("");
  const review = state.postMatchReview;
  $("#rpsPostMatch").classList.toggle("hidden", !review);
  if (review) {
    $("#rpsReviewTitle").textContent = language === "zh" ? "赛后策略复盘" : "Post-match strategy review";
    const difference = signed(review.scoreDifference);
    $("#rpsReviewMetrics").innerHTML = [
      [language === "zh" ? "最终分差" : "Score difference", difference],
      [language === "zh" ? "均衡支持内" : "In equilibrium support", `${review.equilibriumSupportedRounds} / ${state.roundsTotal}`],
      [language === "zh" ? "所选动作平均权重" : "Avg chosen weight", `${(review.averageChosenProbability * 100).toFixed(1)}%`],
      [language === "zh" ? "AI 最高针对权重" : "Peak exploit weight", `${(review.maxExploitWeight * 100).toFixed(0)}%`],
    ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
    const favorites = review.mostUsedMoves.map((move) => moveNames[move]).join(language === "zh" ? "、" : ", ");
    $("#rpsReviewCopy").textContent = language === "zh"
      ? `你最常使用${favorites}。AI 会利用已观察到的重复倾向，但仍保留均衡基线。进入均衡支持集并不表示某一次结果必胜；真正目标是让长期出牌频率接近建议分布。`
      : `Your most-used move${review.mostUsedMoves.length > 1 ? "s were" : " was"} ${favorites}. The AI exploited observed repetition while retaining its equilibrium baseline. Support membership does not guarantee a win in one round; the goal is to make long-run frequencies resemble the advised mixture.`;
  }
  if (state.phase === "finished") {
    $("#rpsCards").innerHTML += `<button class="rps-new-match" data-rps-new>${language === "zh" ? "重新洗牌" : "New match"}</button>`;
    $("[data-rps-new]").addEventListener("click", () => act("new_match"));
  }
}

function probabilityBars(distribution, labels) {
  return Object.entries(distribution).map(([move, probability]) => `<div class="probability-row"><span>${labels[move]}</span><progress max="1" value="${probability}" aria-label="${labels[move]} ${(probability * 100).toFixed(1)}%"></progress><strong>${(probability * 100).toFixed(1)}%</strong></div>`).join("");
}

function renderLiarDice() {
  const state = currentState;
  $("#liarRound").textContent = state.roundNumber;
  $("#liarPlayerScore").textContent = state.playerScore;
  $("#liarAiScore").textContent = state.aiScore;
  $("#liarOpponentDice").textContent = state.opponentDiceCount;
  $("#liarPlayerDice").innerHTML = state.playerDice.map((face) => `<span class="liar-die">${face}</span>`).join("");
  $("#liarAiDice").innerHTML = Array.from({ length: state.opponentDiceCount }, () => '<span class="liar-die hidden-die">?</span>').join("");
  $("#liarCurrentBid").textContent = state.currentBid ? `${state.currentBid[0]} × ${state.currentBid[1]}` : "—";
  $("#liarProbability").textContent = state.claimProbability == null ? "" : `${tr("liarProbability")}: ${(state.claimProbability * 100).toFixed(1)}%`;
  const playerTurn = state.phase === "bidding" && state.turn === "player";
  $("#liarActions").classList.toggle("hidden", !playerTurn);
  $("#liarChallenge").disabled = !state.currentBid;
  if (state.minimumBid) {
    const minimumQuantity = state.minimumBid.quantity;
    $("#liarQuantity").min = minimumQuantity;
    $("#liarQuantity").value = String(Math.max(minimumQuantity, Number($("#liarQuantity").value) || minimumQuantity));
    $("#liarFace").value = String(Math.min(6, state.minimumBid.face));
  }
  $("#liarInstruction").textContent = state.phase === "finished"
    ? (language === "zh" ? `本轮结束：实际符合叫价的骰子数量为 ${state.result.actualCount}。` : `Round over: ${state.result.actualCount} dice matched the claim.`)
    : state.turn === "ai"
      ? (language === "zh" ? "AI 正在根据公开叫价与自己的骰子判断。" : "The AI is evaluating the public bid against its private dice.")
      : tr("liarInstruction");
  $("#liarHistory").innerHTML = state.history.length ? state.history.map((item) => {
    const actor = item.actor === "player" ? (language === "zh" ? "你" : "You") : "AI";
    const action = item.action === "challenge" ? (language === "zh" ? "质疑" : "challenged") : (language === "zh" ? `加注 ${item.quantity} × ${item.face}` : `raised to ${item.quantity} × ${item.face}`);
    return `<div><b>${actor}</b><span>${action}</span>${item.confidence == null ? "" : `<small>${(item.confidence * 100).toFixed(0)}%</small>`}</div>`;
  }).join("") : `<p>${language === "zh" ? "还没有公开叫价。" : "No public bids yet."}</p>`;
  const info = state.claimProbability == null
    ? (language === "zh" ? "第一轮由你先叫价。把自己骰子的分布作为先验，再观察 AI 是否愿意继续加注。" : "You open the round. Use your own dice as a prior, then observe whether the AI is willing to raise.")
    : (language === "zh" ? `在把 1 点视为万能牌后，模型估计当前叫价为真的概率是 ${(state.claimProbability * 100).toFixed(1)}%。概率低不等于必假，但它决定质疑的风险边界。` : `Treating ones as wild, the model estimates a ${(state.claimProbability * 100).toFixed(1)}% chance the current bid is true. Low probability is not certainty, but it sets a useful challenge threshold.`);
  $("#liarInformation").textContent = info;
  $("#liarResult").classList.toggle("hidden", state.phase !== "finished");
  if (state.phase === "finished") {
    const winner = state.result.winner === "player" ? (language === "zh" ? "你赢下本轮" : "You win the round") : (language === "zh" ? "AI 赢下本轮" : "AI wins the round");
    $("#liarResult").textContent = `${winner} · ${state.result.claimTrue ? (language === "zh" ? "叫价成立" : "claim true") : (language === "zh" ? "叫价被揭穿" : "claim false")}`;
  }
}

function battleCoordinate(cell) {
  if (!cell) return "—";
  return `${String.fromCharCode(65 + cell[0])}${cell[1] + 1}`;
}

function pursuitTransportLabel(mode) {
  if (!mode) return "—";
  if (language === "zh") return mode === "taxi" ? "出租车 · 黄色线路" : "公交车 · 紫色线路";
  return mode === "taxi" ? "Taxi · yellow lines" : "Bus · purple lines";
}

function drawPursuitRoutes(state, nodeById) {
  const canvas = $("#pursuitRoutes");
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.lineCap = "round";
  state.edges.forEach((edge) => {
    const start = nodeById[edge.from];
    const end = nodeById[edge.to];
    context.beginPath();
    context.moveTo(start.x * 10, start.y * 10);
    context.lineTo(end.x * 10, end.y * 10);
    context.strokeStyle = edge.transport === "taxi" ? "#d5a83f" : "#8762b5";
    context.globalAlpha = edge.transport === "taxi" ? 0.48 : 0.62;
    context.lineWidth = edge.transport === "taxi" ? 3 : 5;
    context.stroke();
  });
  context.globalAlpha = 1;
}

function renderHiddenPursuit() {
  const state = currentState;
  const finished = state.phase === "finished";
  const legal = new Set(state.legalMoves);
  const belief = new Set(state.belief);
  const nodeById = Object.fromEntries(state.nodes.map((node) => [node.id, node]));
  const nextReveal = state.revealRounds.find((round) => round >= state.round);
  $("#pursuitRound").textContent = `${state.round} / ${state.maxRounds}`;
  $("#pursuitCandidates").textContent = state.belief.length;
  $("#pursuitNextReveal").textContent = nextReveal
    ? (language === "zh" ? `第 ${nextReveal} 回合` : `Round ${nextReveal}`)
    : (language === "zh" ? "不再现身" : "No more reveals");
  $("#pursuitRecord").textContent = `${state.sessionStats.detectiveWins} / ${state.sessionStats.gamesCompleted}`;
  $("#pursuitTransport").textContent = pursuitTransportLabel(state.lastTransport);
  $("#pursuitMap").setAttribute("aria-label", language === "zh" ? "隐形追踪交通地图" : "Hidden pursuit transport map");

  const nodes = state.nodes.map((node) => {
    const detectiveIndex = state.detectives.indexOf(node.id);
    const isLegal = legal.has(node.id);
    const isPossible = belief.has(node.id);
    const isLastSeen = state.lastReveal === node.id;
    const isFugitive = finished && state.fugitivePosition === node.id;
    const classes = ["pursuit-node", `node-${node.id}`, detectiveIndex === 0 ? "detective-a" : "", detectiveIndex === 1 ? "detective-b" : "", isLegal ? "legal" : "", isPossible ? "possible" : "", isLastSeen ? "last-seen" : "", isFugitive ? "fugitive" : ""].filter(Boolean).join(" ");
    const marker = detectiveIndex === 0 ? "A" : detectiveIndex === 1 ? "B" : isFugitive ? "X" : isPossible ? "?" : node.id;
    const label = language === "zh" ? `${node.id} 号节点${isLegal ? "，可移动" : ""}` : `Node ${node.id}${isLegal ? ", legal move" : ""}`;
    return `<button class="${classes}" data-pursuit-node="${node.id}" ${isLegal && !finished ? "" : "disabled"} aria-label="${label}"><span>${marker}</span><small>${node.id}</small></button>`;
  }).join("");
  $("#pursuitMap").innerHTML = `<canvas class="pursuit-routes" id="pursuitRoutes" width="1000" height="1000" aria-hidden="true"></canvas>${nodes}`;
  drawPursuitRoutes(state, nodeById);
  document.querySelectorAll("[data-pursuit-node]:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => act("move_detective", {node: Number(button.dataset.pursuitNode)}));
  });

  $("#pursuitHeadline").textContent = finished
    ? (state.winner === "detectives" ? (language === "zh" ? "围捕成功" : "Fugitive captured") : (language === "zh" ? "目标成功逃脱" : "The fugitive escaped"))
    : (language === "zh" ? `移动侦探 ${state.currentDetective === 0 ? "A" : "B"}` : `Move detective ${state.currentDetective === 0 ? "A" : "B"}`);
  $("#pursuitInstruction").textContent = finished
    ? (language === "zh" ? `目标最终位于 ${state.fugitivePosition} 号节点；可以结合记录复盘候选集合。` : `The fugitive finished at node ${state.fugitivePosition}. Review the candidate trail below.`)
    : (language === "zh" ? `点击发光的相邻节点。A、B 都行动后，目标移动并公开交通方式。` : "Click a glowing adjacent node. After A and B move, the fugitive moves and reveals transport.");
  $("#pursuitInformation").textContent = language === "zh"
    ? `现在有 ${state.belief.length} 个节点与全部公开信号一致。${state.lastReveal ? `最近一次在 ${state.lastReveal} 号节点现身；之后要继续根据交通信号更新。` : "目标尚未强制现身。"}`
    : `${state.belief.length} ${state.belief.length === 1 ? "node matches" : "nodes match"} every public signal. ${state.lastReveal ? `The last reveal was node ${state.lastReveal}; update it with each later transport signal.` : "No scheduled reveal has occurred yet."}`;
  $("#pursuitBelief").innerHTML = state.belief.map((node) => `<span>${node}</span>`).join("");
  $("#pursuitHistory").innerHTML = state.history.length ? state.history.slice().reverse().map((item) => {
    if (item.actor === "fugitive") return `<div><strong>${language === "zh" ? `第 ${item.round} 回合 · 目标` : `Round ${item.round} · Fugitive`}</strong><span>${pursuitTransportLabel(item.transport)}${item.revealed ? (language === "zh" ? ` · 在 ${item.to} 号现身` : ` · revealed at ${item.to}`) : (language === "zh" ? " · 终点隐藏" : " · destination hidden")}</span></div>`;
    return `<div><strong>${language === "zh" ? `第 ${item.round} 回合 · 侦探 ${item.actor === 0 ? "A" : "B"}` : `Round ${item.round} · Detective ${item.actor === 0 ? "A" : "B"}`}</strong><span>${item.from} → ${item.to}${item.capture ? (language === "zh" ? " · 抓捕" : " · capture") : ""}</span></div>`;
  }).join("") : `<p>${language === "zh" ? "尚未移动。先选择侦探 A 的发光相邻节点。" : "No moves yet. Start with a glowing neighbor of detective A."}</p>`;
  $("#pursuitResult").classList.toggle("hidden", !finished);
  if (finished) $("#pursuitResult").textContent = state.winner === "detectives"
    ? (language === "zh" ? `侦探获胜 · 第 ${state.round} 回合` : `Detectives win · round ${state.round}`)
    : (language === "zh" ? "目标获胜 · 撑过 12 回合" : "Fugitive wins · survived 12 rounds");
}

function renderBattleGrid(selector, cells, isEnemy, state) {
  const suggested = state.suggestedShot?.join(",");
  $(selector).classList.remove("board-size-10", "board-size-12", "board-size-15");
  $(selector).classList.add(`board-size-${state.boardSize}`);
  $(selector).innerHTML = cells.map((cell) => {
    const key = `${cell.row},${cell.column}`;
    const classes = ["battle-cell", cell.ship ? "ship" : "", cell.shipId != null ? `ship-${cell.shipId}` : "", cell.shot && !cell.hit ? "miss" : "", cell.hit ? "hit" : "", cell.sunk ? "sunk" : "", isEnemy && key === suggested ? "suggested" : ""].filter(Boolean).join(" ");
    const marker = cell.sunk ? "×" : cell.hit ? "●" : cell.shot ? "·" : "";
    const coordinate = battleCoordinate([cell.row, cell.column]);
    if (!isEnemy) return `<div class="${classes}" title="${coordinate}">${marker}</div>`;
    const disabled = state.phase !== "player_turn" || cell.shot;
    return `<button class="${classes}" data-battle-row="${cell.row}" data-battle-column="${cell.column}" ${disabled ? "disabled" : ""} aria-label="${language === "zh" ? `向 ${coordinate} 开火` : `Fire at ${coordinate}`}">${marker}</button>`;
  }).join("");
  if (isEnemy) {
    document.querySelectorAll("[data-battle-row]:not(:disabled)").forEach((button) => {
      button.addEventListener("click", () => act("fire", {
        row: Number(button.dataset.battleRow),
        column: Number(button.dataset.battleColumn),
      }));
    });
  }
}

function renderBattleship() {
  const state = currentState;
  $("#battleshipView").classList.toggle("placement-phase", state.phase === "placement");
  $("#battleEnemyBoard").setAttribute("aria-label", language === "zh" ? "敌方海域" : "Enemy waters");
  $("#battlePlayerBoard").setAttribute("aria-label", language === "zh" ? "你的舰队" : "Your fleet");
  const playerShips = state.playerShipsRemaining.length;
  const enemyShips = state.enemyShipsRemaining.length;
  $("#battleTurn").textContent = state.salvoSize > 1
    ? `${language === "zh" ? "齐射" : "Volley"} ${state.volleyNumber}`
    : state.turn;
  $("#battlePlayerShips").textContent = `${playerShips} / ${state.shipLengths.length}`;
  $("#battleCandidates").textContent = state.candidatePlacementCount;
  $("#battleSuggestion").textContent = battleCoordinate(state.suggestedShot);
  $("#battleOwnShips").textContent = `${playerShips} ${language === "zh" ? "艘" : "SHIPS"}`;
  $("#battleEnemyShips").textContent = `${enemyShips} ${language === "zh" ? "艘" : "SHIPS"}`;
  $("#battleDeployment").classList.toggle("hidden", state.phase !== "placement");
  $("#battleFleetControls").classList.toggle("hidden", state.phase !== "placement");
  $("#battleBoardSize").value = String(state.boardSize);
  $("#battleBoardSize").disabled = state.phase !== "placement";
  $("#battleDeploymentTitle").textContent = language === "zh" ? "先确认你的舰队布置" : "Confirm your fleet layout";
  $("#battleDeploymentCopy").textContent = language === "zh"
    ? `选择海域规模；每种颜色是一艘舰船。点击下方舰船卡旋转 90°，也可以整体随机布阵。${state.boardSize === 15 ? "15×15 将启用双方各两炮的齐射制。" : ""}`
    : `Choose a sea size; every color is one ship. Rotate individual ship cards 90°, or randomize the full fleet.${state.boardSize === 15 ? " The 15×15 board uses symmetric two-shot salvos." : ""}`;
  renderBattleGrid("#battleEnemyBoard", state.enemyBoard, true, state);
  renderBattleGrid("#battlePlayerBoard", state.playerBoard, false, state);
  $("#battleFleetControls").innerHTML = state.fleet.map((ship) => `
    <button class="battle-ship-control ship-${ship.id}" data-rotate-ship="${ship.id}">
      <span>${language === "zh" ? `舰船 ${ship.id + 1}` : `Ship ${ship.id + 1}`}</span>
      <strong>${language === "zh" ? `长度 ${ship.length}` : `Length ${ship.length}`}</strong>
      <small>${ship.orientation === "horizontal" ? (language === "zh" ? "水平 ↔" : "Horizontal ↔") : (language === "zh" ? "垂直 ↕" : "Vertical ↕")}</small>
      <b>${language === "zh" ? "旋转 90°" : "Rotate 90°"}</b>
    </button>`).join("");
  document.querySelectorAll("[data-rotate-ship]").forEach((button) => {
    button.addEventListener("click", () => act("rotate_ship", { shipId: Number(button.dataset.rotateShip) }));
  });

  $("#battleHeadline").textContent = state.phase === "placement"
    ? (language === "zh" ? "先完成布阵" : "Deploy before battle")
    : state.phase === "finished"
      ? (state.winner === "player" ? (language === "zh" ? "你击沉了敌方舰队" : "You sank the enemy fleet") : (language === "zh" ? "AI 击沉了你的舰队" : "The AI sank your fleet"))
      : state.salvoSize > 1
        ? (language === "zh" ? `第 ${state.volleyNumber} 轮齐射：还可打 ${state.shotsRemainingInVolley} 炮` : `Volley ${state.volleyNumber}: ${state.shotsRemainingInVolley} shot(s) left`)
        : (language === "zh" ? `第 ${state.turn + 1} 回合：选择攻击坐标` : `Turn ${state.turn + 1}: choose a target`);
  $("#battleInstruction").textContent = state.phase === "placement"
    ? (language === "zh" ? "查看自己的舰船位置；点击确认后布阵将锁定。" : "Review your ship positions. Locking the fleet makes the layout final.")
    : state.phase === "finished"
      ? (language === "zh" ? "敌方完整布阵已经揭示，可以对照交火记录复盘。" : "The complete enemy fleet is now revealed for review.")
      : state.salvoSize > 1
        ? (language === "zh" ? `点击敌方未知格开火；完成本轮剩余 ${state.shotsRemainingInVolley} 炮后，AI 将对称还击 ${state.salvoSize} 炮。` : `Fire at an unknown cell. After your ${state.shotsRemainingInVolley} remaining shot(s), the AI returns ${state.salvoSize} shots.`)
        : (language === "zh" ? "点击敌方未知格开火；AI 会依据概率热力图立即还击。" : "Fire at an unknown enemy cell; the probability AI immediately returns fire.");

  const info = state.informationSet;
  $("#battleInformation").textContent = language === "zh"
    ? `已搜索 ${info.searchedCells}/${info.boardCells} 格（${(info.searchedCells / info.boardCells * 100).toFixed(0)}%），确认命中 ${info.confirmedEnemyHits}/${info.enemySegmentsTotal} 段。敌方仍有 ${info.remainingShipLengths.length} 艘船；当前枚举到 ${info.candidatePlacementCount} 个合法单舰部署。`
    : `Searched ${info.searchedCells}/${info.boardCells} cells (${(info.searchedCells / info.boardCells * 100).toFixed(0)}%) and confirmed ${info.confirmedEnemyHits}/${info.enemySegmentsTotal} enemy segments. ${info.remainingShipLengths.length} ships remain across ${info.candidatePlacementCount} legal single-ship placements.`;
  $("#battleAiAnalysis").textContent = state.lastAiAnalysis
    ? (language === "zh"
      ? `AI 上轮采用${state.lastAiAnalysis.searchMode === "target" ? "追击" : "搜索"}模式，计算并发射 ${state.lastAiAnalysis.volleyShots?.length || 1} 炮；最后选择 ${battleCoordinate(state.lastAiAnalysis.chosenCell)}。该格覆盖 ${state.lastAiAnalysis.peakDensity} 个候选部署（占 ${(state.lastAiAnalysis.coverageShare * 100).toFixed(1)}%），并列最佳格 ${state.lastAiAnalysis.tiedBestCells} 个。`
      : `The AI used ${state.lastAiAnalysis.searchMode === "target" ? "target" : "hunt"} mode and calculated ${state.lastAiAnalysis.volleyShots?.length || 1} shot(s); its last choice was ${battleCoordinate(state.lastAiAnalysis.chosenCell)}. That cell covered ${state.lastAiAnalysis.peakDensity} candidate placements (${(state.lastAiAnalysis.coverageShare * 100).toFixed(1)}%), with ${state.lastAiAnalysis.tiedBestCells} cells tied for best.`)
    : (language === "zh" ? "开战后，这里会解释 AI 为什么选择上一炮。" : "After battle starts, this panel explains the AI's previous shot.");

  $("#battleHistory").innerHTML = state.history.length ? state.history.slice().reverse().map((item) => {
    const player = item.playerShot;
    const aiShots = item.aiShots?.length ? item.aiShots : item.aiShot ? [item.aiShot] : [];
    const resultLabel = (shot) => shot.sunk ? (language === "zh" ? `击沉长度 ${shot.sunkLength}` : `sank length ${shot.sunkLength}`) : shot.hit ? (language === "zh" ? "命中" : "hit") : (language === "zh" ? "落空" : "miss");
    const turnLabel = state.salvoSize > 1 ? (language === "zh" ? `齐射 ${item.volley} · 第 ${item.turn} 炮` : `Volley ${item.volley} · shot ${item.turn}`) : (language === "zh" ? `回合 ${item.turn}` : `Turn ${item.turn}`);
    return `<div><strong>${turnLabel}</strong><span>${language === "zh" ? "你" : "You"} ${battleCoordinate(player.cell)} · ${resultLabel(player)}</span>${aiShots.map((ai, index) => `<span>AI${aiShots.length > 1 ? ` ${index + 1}` : ""} ${battleCoordinate(ai.cell)} · ${resultLabel(ai)}</span>`).join("")}</div>`;
  }).join("") : `<p>${language === "zh" ? "战斗尚未开始。" : "The battle has not started."}</p>`;
  $("#battleResult").classList.toggle("hidden", state.phase !== "finished");
  if (state.phase === "finished") $("#battleResult").textContent = state.winner === "player"
    ? (language === "zh" ? `胜利 · 共使用 ${state.turn} 炮` : `Victory in ${state.turn} shots`)
    : (language === "zh" ? `失败 · 坚持了 ${state.turn} 回合` : `Defeat after ${state.turn} turns`);
}

function renderMastermind() {
  const state = currentState;
  const stats = state.sessionStats;
  const analysis = state.suggestionAnalysis;
  $("#mastermindAttempts").textContent = `${state.attemptsUsed} / ${state.maxAttempts}`;
  $("#mastermindCandidates").textContent = money.format(state.candidateCount);
  $("#mastermindSuggestion").textContent = state.suggestedGuess ? state.suggestedGuess.join(" · ") : "—";
  $("#mastermindAverage").textContent = stats.averageSolvedAttempts === null
    ? "—"
    : `${stats.averageSolvedAttempts.toFixed(2)} ${language === "zh" ? "步" : "guesses"}`;
  $("#mastermindSubmit").disabled = state.phase !== "playing";
  $("#mastermindUseSuggestion").disabled = state.phase !== "playing" || !state.suggestedGuess;
  $("#mastermindInput").disabled = state.phase !== "playing";
  $("#mastermindInstruction").textContent = state.phase === "finished"
    ? (state.result.won ? (language === "zh" ? `破解成功！用了 ${state.result.attempts} 次。` : `Cracked in ${state.result.attempts} attempts.`) : (language === "zh" ? `本轮结束，密码是 ${state.result.secret.join(" · ")}。` : `Out of attempts. The code was ${state.result.secret.join(" · ")}.`))
    : tr("mastermindInstruction");
  $("#mastermindHistory").innerHTML = state.attempts.length ? state.attempts.map((item, index) => `<div class="mastermind-attempt"><span class="attempt-number">${index + 1}</span><b>${item.guess.join(" · ")}</b><span class="feedback-chip exact">${item.exact} ${tr("mastermindExact")}</span><span class="feedback-chip partial">${item.partial} ${tr("mastermindPartial")}</span><small>${language === "zh" ? `排除 ${money.format(item.eliminated)} 个，剩余 ${money.format(item.afterCandidates)}` : `Eliminated ${money.format(item.eliminated)}; ${money.format(item.afterCandidates)} remain`}</small></div>`).join("") : `<p>${language === "zh" ? "还没有提交猜测。先输入四位不同数字；若不知从哪里开始，可以采用 AI 建议 0123。" : "No guesses yet. Enter four distinct digits, or use the AI's 0123 opening."}</p>`;
  const eliminatedShare = 1 - state.candidateCount / state.initialCandidateCount;
  $("#mastermindInformation").textContent = language === "zh"
    ? `公开反馈已排除 ${(eliminatedShare * 100).toFixed(1)}% 的初始密码；仍有 ${money.format(state.candidateCount)} 个隐藏世界与你看到的记录完全一致。`
    : `Public feedback has eliminated ${(eliminatedShare * 100).toFixed(1)}% of the original codes; ${money.format(state.candidateCount)} hidden worlds still match every clue.`;
  $("#mastermindCandidatePreview").innerHTML = state.informationSet.candidatePreview.map((code) => `<span>${code.join("")}</span>`).join("");
  $("#mastermindStrategy").textContent = analysis
    ? (language === "zh"
      ? `建议 ${analysis.exactSearch ? "来自完整猜测空间搜索" : "来自受限计算池"}：评估 ${money.format(analysis.evaluatedGuesses)} 个猜法；下一次反馈的最坏分支不超过 ${money.format(analysis.worstCaseRemaining)} 个候选，平均预计剩余 ${analysis.expectedRemaining.toFixed(1)} 个。它优化下一步的信息分割，但不等于已证明的全局最优总步数。`
      : `The suggestion ${analysis.exactSearch ? "searched the full guess space" : "used a bounded search pool"}: ${money.format(analysis.evaluatedGuesses)} guesses evaluated, at most ${money.format(analysis.worstCaseRemaining)} candidates in the worst next bucket, and ${analysis.expectedRemaining.toFixed(1)} expected survivors. It optimizes the next split, not a proven global minimum total.`)
    : (language === "zh" ? `本次会话完成 ${stats.gamesCompleted} 局，成功 ${stats.gamesSolved} 局，最佳 ${stats.bestAttempts ?? "—"} 步。` : `${stats.gamesCompleted} games completed, ${stats.gamesSolved} solved, best ${stats.bestAttempts ?? "—"} guesses.`);
  $("#mastermindResult").classList.toggle("hidden", state.phase !== "finished");
  if (state.phase === "finished") $("#mastermindResult").textContent = state.result.won
    ? (language === "zh" ? `成功破解 · 密码 ${state.result.secret.join("")}` : `Code cracked · ${state.result.secret.join("")}`)
    : (language === "zh" ? `机会用尽 · 密码 ${state.result.secret.join("")}` : `Attempts exhausted · ${state.result.secret.join("")}`);
}

const loveNames = {
  zh: {1:"卫兵",2:"牧师",3:"男爵",4:"侍女",5:"王子",6:"国王",7:"伯爵夫人",8:"公主"},
  en: {1:"Guard",2:"Priest",3:"Baron",4:"Handmaid",5:"Prince",6:"King",7:"Countess",8:"Princess"},
};

function playLoveCard(card) {
  let target = null;
  let guess = null;
  if ([1, 2, 3, 6].includes(card)) target = "ai";
  if (card === 5) target = $("#loveTarget").value;
  if (card === 1) guess = Number($("#loveGuess").value);
  act("play_card", { card, target, guess });
}

function renderLoveLetter() {
  const state = currentState;
  const names = loveNames[language];
  const active = state.phase === "player_turn";
  const finished = ["round_finished", "match_finished"].includes(state.phase);
  const loveTarget = $("#loveTarget");
  const aiTarget = loveTarget.querySelector('option[value="ai"]');
  aiTarget.disabled = state.protected.ai;
  if (state.protected.ai && loveTarget.value === "ai") loveTarget.value = "player";
  $("#loveRound").textContent = state.roundNumber;
  $("#lovePlayerScore").textContent = `${state.scores.player} / ${state.targetScore}`;
  $("#loveAiScore").textContent = `${state.scores.ai} / ${state.targetScore}`;
  $("#loveDeck").textContent = state.deckRemaining;
  $("#loveOpponentStatus").textContent = finished && state.opponentHand
    ? `${names[state.opponentHand[0]]} · ${state.opponentHand[0]}`
    : state.protected.ai
      ? (language === "zh" ? "手牌隐藏 · 受侍女保护" : "Hidden · protected by Handmaid")
      : (language === "zh" ? "手牌隐藏" : "Hidden hand");

  $("#loveHand").innerHTML = state.playerHand.map((card) => {
    const legal = state.legalCards.includes(card);
    return `<button class="love-card love-card-${card}" data-love-card="${card}" ${!active || !legal ? "disabled" : ""}><span>${card}</span><strong>${names[card]}</strong></button>`;
  }).join("");
  document.querySelectorAll("[data-love-card]").forEach((button) => button.addEventListener("click", () => playLoveCard(Number(button.dataset.loveCard))));

  const suggestion = state.suggestedPlay;
  $("#loveUseSuggestion").disabled = active ? !suggestion : !finished;
  $("#loveUseSuggestion").textContent = finished
    ? (state.phase === "match_finished" ? (language === "zh" ? "开始新比赛" : "New match") : (language === "zh" ? "进入下一轮" : "Next round"))
    : tr("loveUseSuggestion");
  $("#loveInstruction").textContent = finished
    ? (state.roundResult.winner === "player" ? (language === "zh" ? "你赢得了这一轮" : "You won the round") : (language === "zh" ? "AI 赢得了这一轮" : "The AI won the round"))
    : state.protected.player
      ? (language === "zh" ? "侍女保护已在本回合开始时结束；选择一张牌行动" : "Your Handmaid protection ended as this turn began; choose a card")
      : (language === "zh" ? "从两张手牌中打出一张；先设置卫兵猜测或王子目标" : "Play one of two cards; set a Guard guess or Prince target first");

  const known = state.informationSet.knownOpponentCard;
  $("#loveInformation").textContent = known
    ? (language === "zh" ? `你通过角色效果确认 AI 当前持有 ${known} · ${names[known]}。` : `A role effect confirms the AI currently holds ${known} · ${names[known]}.`)
    : (language === "zh" ? "以下概率只使用你的手牌、公开移除牌和双方弃牌计算，不读取 AI 的隐藏手牌。" : "These probabilities use your hand, face-up removals, and public discards only; they do not read the AI's hidden card.");
  $("#loveBeliefs").innerHTML = state.informationSet.possibleCards.map((item) => `<div><span>${item.value} · ${names[item.value]}</span><strong>${(item.probability * 100).toFixed(1)}%</strong><progress max="1" value="${item.probability}" aria-label="${names[item.value]} ${(item.probability * 100).toFixed(1)}%"></progress></div>`).join("");
  $("#loveSuggestion").textContent = suggestion
    ? (language === "zh" ? `信念策略建议：打出 ${suggestion.card} · ${names[suggestion.card]}${suggestion.guess ? `，卫兵猜 ${suggestion.guess} · ${names[suggestion.guess]}` : ""}${suggestion.card === 5 ? `，目标为${suggestion.target === "player" ? "自己" : "AI"}` : ""}。这是公开信息上的启发式策略，并非完整博弈树最优证明。` : `Belief advice: play ${suggestion.card} · ${names[suggestion.card]}${suggestion.guess ? ` and guess ${suggestion.guess} · ${names[suggestion.guess]}` : ""}${suggestion.card === 5 ? ` targeting ${suggestion.target === "player" ? "yourself" : "the AI"}` : ""}. This is a public-information heuristic, not a full-game optimality proof.`)
    : (language === "zh" ? "本轮已经结束；双方手牌均已公开，可以结合弃牌记录复盘。" : "The round is over. Both hands are now available for review with the discard log.");

  const effectLabels = language === "zh"
    ? {none:"无额外效果",guard_hit:"卫兵猜中并淘汰对手",guard_miss:"卫兵猜错",priest_seen:"查看了手牌",baron_loss:"男爵比较后淘汰较低手牌",baron_tie:"男爵比较平手",protected:"获得侍女保护",prince_discard:"王子强制弃牌",traded:"交换手牌"}
    : {none:"no extra effect",guard_hit:"Guard guessed correctly",guard_miss:"Guard missed",priest_seen:"looked at the hand",baron_loss:"Baron eliminated the lower hand",baron_tie:"Baron tied",protected:"gained Handmaid protection",prince_discard:"Prince forced a discard",traded:"traded hands"};
  $("#loveHistory").innerHTML = state.history.length ? state.history.slice().reverse().map((item) => `<div><strong>${item.actor === "player" ? tr("you") : "AI"}</strong><span>${item.card} · ${names[item.card]}</span><small>${effectLabels[item.effect] || item.effect}${item.guess ? ` · ${language === "zh" ? "猜" : "guess"} ${item.guess}` : ""}${item.discarded ? ` · ${language === "zh" ? "弃掉" : "discarded"} ${item.discarded} ${names[item.discarded]}` : ""}</small></div>`).join("") : `<p>${language === "zh" ? "尚无公开行动。" : "No public actions yet."}</p>`;
  $("#loveRemoved").textContent = state.faceUpRemoved.map((card) => `${card}·${names[card]}`).join(" · ");
  $("#loveResult").classList.toggle("hidden", !finished);
  if (finished) $("#loveResult").textContent = state.phase === "match_finished"
    ? (state.matchWinner === "player" ? (language === "zh" ? "比赛胜利 · 你率先获得 4 分" : "Match won · you reached four points") : (language === "zh" ? "比赛结束 · AI 率先获得 4 分" : "Match over · the AI reached four points"))
    : (language === "zh" ? "本轮结束；检查公开记录后进入下一轮。" : "Round over; review the public log, then continue.");
}

function renderInvestment() {
  const state = currentState;
  const active = state.phase === "decision";
  const nextCut = state.eliminationRounds.find((round) => round >= state.roundNumber);
  $("#investmentRound").textContent = `${state.roundNumber} / ${state.maxRounds}`;
  $("#investmentCapital").textContent = money.format(state.playerBankroll);
  const playerAlive = state.rankings.find((item) => item.id === "player").alive;
  $("#investmentRank").textContent = playerAlive ? `${state.playerRank} / ${state.rankings.length}` : (language === "zh" ? "已淘汰" : "Eliminated");
  $("#investmentNextCut").textContent = !active ? "—" : nextCut ? (language === "zh" ? `第 ${nextCut} 轮` : `Round ${nextCut}`) : (language === "zh" ? "最终结算" : "Final ranking");
  if (active && !state.offers.some((offer) => offer.id === investmentOffer)) investmentOffer = state.suggestion.offerId;
  $("#investmentOffers").innerHTML = active ? state.offers.map((offer) => `<button class="investment-offer ${offer.id === investmentOffer ? "selected" : ""}" data-investment-offer="${offer.id}"><span>${language === "zh" ? "方案" : "Offer"} ${offer.id}</span><strong>${offer.netOdds}:1</strong><small>${language === "zh" ? "成功率" : "Success"} ${(offer.probability * 100).toFixed(1)}%</small><small class="${offer.expectedReturn >= 0 ? "positive" : "negative"}">${language === "zh" ? "期望回报" : "Expected return"} ${(offer.expectedReturn * 100).toFixed(1)}%</small><em>Kelly ${(offer.kellyFraction * 100).toFixed(1)}%</em></button>`).join("") : "";
  document.querySelectorAll("[data-investment-offer]").forEach((button) => button.addEventListener("click", () => { investmentOffer = button.dataset.investmentOffer; renderInvestment(); }));
  const fractions = [0, .1, .25, .5, .75];
  $("#investmentFractions").innerHTML = fractions.map((fraction) => `<button class="fraction-button ${fraction === investmentFraction ? "selected" : ""}" data-investment-fraction="${fraction}">${fraction * 100}%</button>`).join("");
  document.querySelectorAll("[data-investment-fraction]").forEach((button) => button.addEventListener("click", () => { investmentFraction = Number(button.dataset.investmentFraction); renderInvestment(); }));
  $("#investmentSubmit").disabled = !active;
  $("#investmentInstruction").textContent = active
    ? (language === "zh" ? "选择一个赔率方案，再决定投入多少虚拟资金；对手选择在结算后公开。" : "Choose an odds profile and stake; rival decisions appear only after settlement.")
    : (state.winner === "player" ? (language === "zh" ? "你以最高资金赢得锦标赛" : "You finished with the highest bankroll") : (language === "zh" ? "比赛结束：复盘增长与存活之间的取舍" : "Tournament over: review the growth-survival tradeoff"));
  const skillNames = language === "zh" ? {odds_analyst:"赔率分析师",full_kelly:"全 Kelly",half_kelly:"半 Kelly",rank_chaser:"落后追赶",longshot:"长赔率偏好",capital_preserver:"保本优先"} : {odds_analyst:"Odds analyst",full_kelly:"Full Kelly",half_kelly:"Half Kelly",rank_chaser:"Rank chaser",longshot:"Longshot",capital_preserver:"Capital preserver"};
  $("#investmentRanking").innerHTML = state.rankings.map((item, index) => `<div class="${!item.alive ? "eliminated" : ""}"><b>${index + 1}</b><span><strong>${item.id === "player" ? tr("you") : item.name}</strong><small>${skillNames[item.skill]}</small></span><em>${money.format(item.bankroll)}</em>${!item.alive ? `<i>${language === "zh" ? "已淘汰" : "Eliminated"}</i>` : ""}</div>`).join("");
  const suggestion = state.suggestion;
  $("#investmentAdvice").textContent = suggestion ? (language === "zh" ? `算术优势最高的是方案 ${suggestion.offerId}，Kelly 仓位 ${(suggestion.kellyFraction * 100).toFixed(1)}%。Kelly 只优化长期对数增长；临近淘汰时，你可能为了排名选择更低或更高仓位。` : `Offer ${suggestion.offerId} has the strongest arithmetic edge; Kelly is ${(suggestion.kellyFraction * 100).toFixed(1)}%. Kelly optimizes long-run log growth only; elimination pressure can justify less or more risk.`) : state.strategyScope;
  const last = state.lastRound;
  $("#investmentHistory").innerHTML = last ? last.results.map((result) => `<div><strong>${result.id === "player" ? tr("you") : state.rankings.find((item) => item.id === result.id)?.name}</strong><span>${result.offer} · ${(result.fraction * 100).toFixed(0)}%</span><em class="${result.won ? "positive" : "negative"}">${result.won ? "+" : ""}${money.format(result.after - result.before)}</em></div>`).join("") : `<p>${language === "zh" ? "首轮尚未结算。" : "Round one has not settled."}</p>`;
  $("#investmentResult").classList.toggle("hidden", active);
  if (!active) $("#investmentResult").textContent = state.winner === "player" ? (language === "zh" ? "锦标赛胜利" : "Tournament victory") : state.winner ? (language === "zh" ? `冠军：${state.rankings.find((item) => item.id === state.winner).name}` : `Champion: ${state.rankings.find((item) => item.id === state.winner).name}`) : (language === "zh" ? "你在淘汰点出局；其余经理继续比赛。" : "You were eliminated; the remaining managers continue.");
}

function renderGoofspiel() {
  const state = currentState;
  const active = state.phase === "bidding";
  const advanced = state.mode === "advanced";
  const winnerLabel = state.winner === "player"
    ? (language === "zh" ? "你赢得比赛" : "You win the match")
    : state.winner === "ai"
      ? (language === "zh" ? "AI 赢得比赛" : "The AI wins the match")
      : (language === "zh" ? "比赛以平局结束" : "The match ends in a draw");
  $("#goofRound").textContent = `${Math.min(state.roundNumber, state.roundsTotal)} / ${state.roundsTotal}`;
  $("#goofBasicMode").classList.toggle("active", !advanced);
  $("#goofAdvancedMode").classList.toggle("active", advanced);
  $("#goofBasicMode").setAttribute("aria-pressed", String(!advanced));
  $("#goofAdvancedMode").setAttribute("aria-pressed", String(advanced));
  $("#goofAiLabel").textContent = language === "zh"
    ? `${advanced ? "精确均衡" : "直觉竞价"} AI · 剩余牌公开`
    : `${advanced ? "Exact-equilibrium" : "Intuitive-bidding"} AI · public inventory`;
  renderModeContract("#goofModeDescription", language === "zh"
    ? {
      changes: advanced ? "AI 按当前公开状态的精确零和均衡随机竞价，可利用度为 0。" : "AI 总打出最接近当前奖牌值的剩余牌；最佳回应平均可赢 +2 分/场。",
      applies: "选择后立即开始一场使用该 AI 的新比赛，从第一轮起生效。",
      score: "当前奖牌分、竞价牌与行动记录全部重置；难度偏好在刷新后保留。",
    }
    : {
      changes: advanced ? "The AI samples the exact zero-sum equilibrium for each public state, with zero exploitability." : "The AI spends the remaining card closest to the prize; an exact best response earns +2 points per match on average.",
      applies: "Selecting it immediately starts a new match with that AI, effective from round one.",
      score: "Prize scores, bid cards, and action history reset; the difficulty preference survives refresh.",
    });
  $("#goofPlayerScore").textContent = state.playerScore;
  $("#goofAiScore").textContent = state.aiScore;
  $("#goofScorePrize").textContent = active ? state.currentPrize : "—";
  $("#goofPrize").textContent = active ? state.currentPrize : "✓";
  $("#goofHiddenPrizes").textContent = active
    ? (language === "zh" ? `之后还有 ${state.informationSet.unrevealedPrizeCount} 张奖牌尚未揭晓` : `${state.informationSet.unrevealedPrizeCount} later prize card(s) remain hidden`)
    : winnerLabel;
  $("#goofInstruction").textContent = active
    ? (language === "zh" ? `为 ${state.currentPrize} 分奖牌选择一张秘密竞价牌` : `Choose one secret bid for the ${state.currentPrize}-point prize`)
    : winnerLabel;
  $("#goofAiCards").innerHTML = state.aiCards.map((card) => `<span class="goof-bid-card passive">${card}</span>`).join("") || `<small>${language === "zh" ? "已全部使用" : "All used"}</small>`;
  $("#goofPlayerCards").innerHTML = state.playerCards.map((card) => `<button class="goof-bid-card ${card === state.recommendedBid ? "recommended" : ""}" data-goof-bid="${card}" ${active ? "" : "disabled"}><strong>${card}</strong>${card === state.recommendedBid ? `<small>${language === "zh" ? "最高频" : "Most likely"}</small>` : ""}</button>`).join("") || `<small>${language === "zh" ? "四张牌均已使用" : "All four cards used"}</small>`;
  document.querySelectorAll("[data-goof-bid]").forEach((button) => button.addEventListener("click", () => act("bid", { card: Number(button.dataset.goofBid) })));

  const last = state.lastRound;
  $("#goofLastRound").classList.toggle("hidden", !last);
  if (last) {
    const outcome = last.playerBid > last.aiBid ? (language === "zh" ? "你赢得奖牌" : "You won the prize") : last.aiBid > last.playerBid ? (language === "zh" ? "AI 赢得奖牌" : "AI won the prize") : (language === "zh" ? "同价，奖牌作废" : "Tie — prize discarded");
    $("#goofLastRound").innerHTML = `<span>${language === "zh" ? "上轮揭晓" : "Last reveal"}</span><strong>${last.playerBid} : ${last.aiBid}</strong><small>${last.prize} ${language === "zh" ? "分" : "pts"} · ${outcome}</small>`;
  }
  const distribution = state.advisorDistribution || [];
  $("#goofAdvice").textContent = active
    ? (language === "zh" ? `均衡参考中，${state.recommendedBid} 是最高频出牌，但不能每次固定选择它；精确策略是按下方概率随机。双方都最优时，剩余回合带来的预期额外分差为 ${Number(state.futureValue).toFixed(2)}。` : `In the equilibrium reference, ${state.recommendedBid} has the highest frequency, but it should not be chosen every time; the exact policy randomizes by the probabilities below. Optimal play gives an expected additional score difference of ${Number(state.futureValue).toFixed(2)} over the remaining rounds.`)
    : (language === "zh" ? `最终比分 ${state.playerScore} : ${state.aiScore}。本场 AI 使用${advanced ? "精确均衡随机策略" : "可被利用的匹配奖牌启发式"}。` : `Final score ${state.playerScore}:${state.aiScore}. This match used the ${advanced ? "exact equilibrium policy" : "exploitable match-prize heuristic"}.`);
  $("#goofDistribution").innerHTML = distribution.map((item) => `<div><span>${language === "zh" ? "出牌" : "Bid"} ${item.card}</span><strong>${(item.probability * 100).toFixed(1)}%</strong><progress max="1" value="${item.probability}" aria-label="${language === "zh" ? "出牌" : "Bid"} ${item.card} ${(item.probability * 100).toFixed(1)}%"></progress></div>`).join("") || `<p>${language === "zh" ? "比赛结束后不再需要决策。" : "No decision remains after the match."}</p>`;
  $("#goofHistory").innerHTML = state.history.length ? state.history.slice().reverse().map((item) => {
    const outcome = item.playerBid > item.aiBid ? (language === "zh" ? "你得分" : "you score") : item.aiBid > item.playerBid ? (language === "zh" ? "AI 得分" : "AI scores") : (language === "zh" ? "奖牌作废" : "discarded");
    return `<div><b>R${item.round}</b><span>${language === "zh" ? "奖牌" : "Prize"} ${item.prize}</span><strong>${item.playerBid} : ${item.aiBid}</strong><small>${outcome}</small></div>`;
  }).join("") : `<p>${language === "zh" ? "提交第一张竞价牌后，公开揭晓会记录在这里。" : "The first simultaneous reveal will appear here after you submit a bid."}</p>`;
  const review = state.postMatchReview;
  $("#goofPostMatch").classList.toggle("hidden", !review);
  if (review) {
    $("#goofReviewTitle").textContent = language === "zh" ? "赛后策略复盘" : "Post-match strategy review";
    $("#goofReviewMetrics").innerHTML = [
      [language === "zh" ? "最终分差" : "Score difference", signed(review.scoreDifference)],
      [language === "zh" ? "均衡支持内" : "In equilibrium support", `${review.equilibriumSupportedRounds} / ${state.roundsTotal}`],
      [language === "zh" ? "所选竞价平均权重" : "Avg chosen weight", `${(review.averageChosenProbability * 100).toFixed(1)}%`],
      [language === "zh" ? "支持集外决策" : "Off-support bids", review.offSupportRounds.length],
    ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
    const exceptions = review.offSupportRounds.length
      ? (language === "zh" ? `第 ${review.offSupportRounds.join("、")} 轮选择了均衡中概率为 0 的牌。` : `Rounds ${review.offSupportRounds.join(", ")} used a bid with zero equilibrium probability.`)
      : (language === "zh" ? "四轮竞价都位于对应公开状态的均衡支持集内。" : "All four bids stayed inside the equilibrium support for their public states.");
    const rare = review.lowFrequencyRounds.length
      ? (language === "zh" ? `第 ${review.lowFrequencyRounds.join("、")} 轮虽然合法，但属于低于 10% 的低频分支。` : `Rounds ${review.lowFrequencyRounds.join(", ")} were valid but rare branches below 10%.`)
      : "";
    $("#goofReviewCopy").textContent = `${exceptions}${rare ? ` ${rare}` : ""} ${language === "zh" ? "分数结果仍包含AI随机抽样的波动，策略质量应结合概率轨迹而非只看输赢。" : "The score still contains variance from the AI's random draw, so judge strategy from the probability trail—not wins alone."}`;
  }
}

function renderGuessWho() {
  const state = currentState;
  const info = state.informationSet;
  const stats = state.sessionStats;
  const suggestion = state.suggestion;
  const finished = state.phase === "finished";
  const questionLabels = language === "zh" ? {
    hair_black: "这个人是黑发吗？", hair_brown: "这个人是棕发吗？",
    hair_blond: "这个人是金发吗？", hair_red: "这个人是红发吗？",
    glasses: "这个人戴眼镜吗？", hat: "这个人戴帽子吗？",
    facial_hair: "这个人有胡须吗？", smiling: "这个人在微笑吗？",
  } : Object.fromEntries(state.questions.map((question) => [question.id, question.label]));
  const hairLabels = language === "zh"
    ? { black: "黑发", brown: "棕发", blond: "金发", red: "红发" }
    : { black: "black hair", brown: "brown hair", blond: "blond hair", red: "red hair" };
  const traitLabels = language === "zh"
    ? { glasses: "眼镜", hat: "帽子", facialHair: "胡须", smiling: "微笑" }
    : { glasses: "glasses", hat: "hat", facialHair: "facial hair", smiling: "smiling" };

  if (guessWhoSelected && !info.possibleNames.includes(guessWhoSelected)) guessWhoSelected = null;
  $("#guessWhoBoardHelp").textContent = language === "zh"
    ? "点击仍亮起的角色进行选择，再点击确认；错误猜测会消耗一回合并排除该角色。"
    : "Select any highlighted character, then confirm your guess. A wrong guess costs one turn and eliminates that character.";
  $("#guessWhoTurns").textContent = `${state.turnsUsed} / ${state.maxTurns}`;
  $("#guessWhoCandidates").textContent = info.possibleCount;
  $("#guessWhoOptimal").textContent = suggestion?.projectedExpectedTurns?.toFixed(3) ?? "—";
  $("#guessWhoBest").textContent = stats.bestTurns === null
    ? "—"
    : `${stats.bestTurns} ${language === "zh" ? "步" : "turns"}`;

  if (finished) {
    $("#guessWhoHeadline").textContent = state.result.won
      ? (language === "zh" ? "身份锁定，推理成功" : "Identity locked — case solved")
      : (language === "zh" ? "回合用尽，身份已经揭晓" : "Out of turns — identity revealed");
    $("#guessWhoInstruction").textContent = language === "zh"
      ? `秘密角色是 ${state.result.secret}。查看记录，比较每个问题排除了多少候选人。`
      : `The secret character was ${state.result.secret}. Review how many candidates each clue removed.`;
  } else if (info.possibleCount === 1) {
    $("#guessWhoHeadline").textContent = language === "zh" ? "只剩一人：完成最终猜测" : "One candidate remains: make the final guess";
    $("#guessWhoInstruction").textContent = language === "zh"
      ? "问题只负责缩小范围；最后仍需猜中角色才算获胜。"
      : "Questions narrow the field, but you must still name the character to win.";
  } else {
    $("#guessWhoHeadline").textContent = language === "zh" ? "提出问题，逐步排除角色" : "Ask a question and eliminate characters";
    $("#guessWhoInstruction").textContent = language === "zh"
      ? `AI 的身份始终隐藏。你还有 ${state.maxTurns - state.turnsUsed} 步，可以提问或直接猜人。`
      : `The AI's identity stays hidden. You have ${state.maxTurns - state.turnsUsed} turns left to ask or guess.`;
  }

  $("#guessWhoQuestions").innerHTML = state.questions.map((question) => {
    const disabled = finished || question.used || !question.informative;
    const status = question.used
      ? (language === "zh" ? "已经问过" : "Already asked")
      : !question.informative
        ? (language === "zh" ? "无法继续区分" : "No longer informative")
        : (language === "zh" ? `是 ${question.yesCount} 人 · 否 ${question.noCount} 人` : `Yes ${question.yesCount} · No ${question.noCount}`);
    return `<button class="guess-question ${suggestion?.questionId === question.id ? "recommended" : ""}" data-guess-question="${question.id}" ${disabled ? "disabled" : ""}>
      <strong>${questionLabels[question.id]}</strong>
      <span class="split">${question.informative ? `${question.yesCount}/${question.noCount}` : "—"}</span>
      <small>${status}</small>
    </button>`;
  }).join("");
  document.querySelectorAll("[data-guess-question]:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => act("ask_question", { questionId: button.dataset.guessQuestion }));
  });

  if (!suggestion) {
    $("#guessWhoSuggestion").textContent = language === "zh" ? "本局已经结束" : "Round complete";
    $("#guessWhoSuggestionDetail").textContent = language === "zh" ? "重新开始即可生成新的秘密身份。" : "Start again for a new secret identity.";
  } else if (suggestion.type === "guess") {
    $("#guessWhoSuggestion").textContent = language === "zh" ? `猜 ${suggestion.character}` : `Guess ${suggestion.character}`;
    $("#guessWhoSuggestionDetail").textContent = language === "zh"
      ? "公开答案只与这一名角色一致；再用一步提交最终猜测。"
      : "Only this character matches every public answer; spend one turn to submit the final guess.";
  } else {
    $("#guessWhoSuggestion").textContent = questionLabels[suggestion.questionId];
    $("#guessWhoSuggestionDetail").textContent = language === "zh"
      ? `精确动态规划建议把候选分成 ${suggestion.yesCount} / ${suggestion.noCount}；最坏剩 ${suggestion.worstRemaining} 人，预计从现在到猜中共 ${suggestion.projectedExpectedTurns.toFixed(3)} 步。`
      : `Exact dynamic programming splits the field ${suggestion.yesCount}/${suggestion.noCount}; at worst ${suggestion.worstRemaining} remain, with ${suggestion.projectedExpectedTurns.toFixed(3)} expected turns to a final guess.`;
  }
  $("#guessWhoUseSuggestion").disabled = finished || !suggestion;
  $("#guessWhoUseSuggestion").onclick = () => {
    if (!currentState?.suggestion || currentState.phase !== "playing") return;
    const advice = currentState.suggestion;
    if (advice.type === "guess") act("guess_character", { name: advice.character });
    else act("ask_question", { questionId: advice.questionId });
  };

  $("#guessWhoGrid").innerHTML = state.characters.map((character) => {
    const traits = [hairLabels[character.hair]];
    Object.keys(traitLabels).forEach((trait) => { if (character[trait]) traits.push(traitLabels[trait]); });
    const classes = [!character.possible ? "eliminated" : "", guessWhoSelected === character.name ? "selected" : "", character.secret ? "secret" : ""].filter(Boolean).join(" ");
    const aria = language === "zh" ? `选择 ${character.name} 作为最终猜测` : `Select ${character.name} as the final guess`;
    return `<button class="guess-character ${classes}" data-guess-character="${character.name}" ${!character.possible || finished ? "disabled" : ""} aria-label="${aria}">
      <span class="guess-avatar hair-${character.hair}"><b>${character.name.slice(0, 1)}</b></span>
      <strong>${character.name}</strong>
      <span class="guess-traits">${traits.map((trait) => `<span>${trait}</span>`).join("")}</span>
    </button>`;
  }).join("");
  document.querySelectorAll("[data-guess-character]:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => { guessWhoSelected = button.dataset.guessCharacter; renderGuessWho(); });
  });
  $("#guessWhoSelected").textContent = guessWhoSelected
    ? (language === "zh" ? `准备猜：${guessWhoSelected}` : `Ready to guess: ${guessWhoSelected}`)
    : (finished ? (language === "zh" ? `答案：${state.result.secret}` : `Answer: ${state.result.secret}`) : (language === "zh" ? "尚未选择要猜的角色" : "No character selected"));
  $("#guessWhoConfirm").disabled = finished || !guessWhoSelected;

  $("#guessWhoInformation").textContent = language === "zh"
    ? `根据 ${state.history.filter((item) => item.action === "question").length} 个公开答案，目前 ${info.possibleCount} 个身份仍有可能。被划掉的角色与至少一条答案矛盾。`
    : `After ${state.history.filter((item) => item.action === "question").length} public answers, ${info.possibleCount} identities remain possible. Every crossed-out character contradicts at least one answer.`;
  $("#guessWhoPossible").innerHTML = info.possibleNames.map((name) => `<span>${name}</span>`).join("");
  $("#guessWhoHistory").innerHTML = state.history.length ? state.history.slice().reverse().map((item) => {
    if (item.action === "question") return `<div><small>${language === "zh" ? `第 ${item.turn} 步` : `Turn ${item.turn}`}</small><span>${questionLabels[item.questionId]}</span><strong>${item.answer ? (language === "zh" ? "是" : "YES") : (language === "zh" ? "否" : "NO")}</strong><small></small><small>${item.beforeCandidates} → ${item.afterCandidates}</small></div>`;
    return `<div><small>${language === "zh" ? `第 ${item.turn} 步` : `Turn ${item.turn}`}</small><span>${language === "zh" ? `猜 ${item.character}` : `Guessed ${item.character}`}</span><strong>${item.correct ? (language === "zh" ? "正确" : "CORRECT") : (language === "zh" ? "错误" : "WRONG")}</strong><small></small><small>${item.beforeCandidates} → ${item.afterCandidates}</small></div>`;
  }).join("") : `<p>${language === "zh" ? "还没有公开记录。先选择一个问题；标出的数字表示回答“是/否”各会剩多少人。" : "No public record yet. Ask a question first; its two numbers show how many candidates survive Yes versus No."}</p>`;

  $("#guessWhoResult").classList.toggle("hidden", !finished);
  if (finished) $("#guessWhoResult").textContent = state.result.won
    ? (language === "zh" ? `推理成功 · ${state.result.secret} · ${state.result.turns} 步` : `Solved · ${state.result.secret} · ${state.result.turns} turns`)
    : (language === "zh" ? `本局结束 · 答案是 ${state.result.secret}` : `Round over · The answer was ${state.result.secret}`);
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
  const advanced = state.mode === "advanced";
  $("#pokerBasicMode").classList.toggle("active", !advanced);
  $("#pokerAdvancedMode").classList.toggle("active", advanced);
  $("#pokerBasicMode").setAttribute("aria-pressed", String(!advanced));
  $("#pokerAdvancedMode").setAttribute("aria-pressed", String(advanced));
  $("#pokerAiLabel").textContent = language === "zh"
    ? (advanced ? "完美 GTO AI" : "基础策略 AI")
    : (advanced ? "Exact GTO AI" : "Basic strategy AI");
  renderModeContract("#pokerModeDescription", language === "zh"
    ? {
      changes: advanced ? "AI 使用经穷举验证、可利用度为 0 的精确 GTO；你仍固定为后手。" : "AI 会价值下注和随机诈唬，但 Q 过度弃牌；最佳回应可达 +1/6 筹码/局。",
      applies: "选择后立即开始一场使用该 AI 的新比赛，从第一手起生效。",
      score: "当前牌局、累计净筹码与行动记录全部重置；难度偏好在刷新后保留。",
    }
    : {
      changes: advanced ? "The AI uses an exhaustively verified exact GTO policy with zero exploitability; you remain second to act." : "The AI value-bets and randomizes bluffs but folds Q too often; a best response reaches +1/6 chip per hand.",
      applies: "Selecting it immediately starts a new match with that AI, effective from hand one.",
      score: "The hand, cumulative net chips, and action history reset; the difficulty preference survives refresh.",
    });
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
  const facingBetInstruction = language === "zh"
    ? state.playerCard === "J"
      ? "你拿 J：按照均衡策略，AI 的这次下注只可能来自 K。"
      : state.playerCard === "K"
        ? "你拿 K：按照均衡策略，AI 的这次下注只可能是 J 诈唬。"
        : "AI 下注了：它拿着 K，还是在用 J 诈唬？"
    : state.playerCard === "J"
      ? "You hold J: under equilibrium play, this AI bet can only come from K."
      : state.playerCard === "K"
        ? "You hold K: under equilibrium play, this AI bet can only be a J bluff."
        : "The AI bet: is it holding K, or bluffing with J?";
  $("#pokerInstruction").textContent = state.phase === "finished"
    ? (language === "zh" ? "本局信息已经揭晓" : "The hand is revealed")
    : facingBet
      ? facingBetInstruction
      : (language === "zh" ? "利用你的私牌与公开行动做决定" : "Decide from your private card and the public actions");
  $("#pokerInformation").textContent = language === "zh"
    ? `你确定自己拿到 ${state.informationSet.privateCard}；因此 AI 只可能持有 ${state.informationSet.possibleOpponentCards.join(" 或 ")}。你固定担任后手。${advanced ? "当前 AI 是可利用度为 0 的精确 GTO。" : "当前 AI 是强启发式，存在 1/9 筹码/局的可利用度；观察它过牌后面对下注的反应。"}`
    : `You hold ${state.informationSet.privateCard}, so the AI can only hold ${state.informationSet.possibleOpponentCards.join(" or ")}. You always act second. ${advanced ? "This AI is exact GTO with zero exploitability." : "This strong heuristic has 1/9 chip per hand of exploitability; study how it responds to a bet after checking."}`;
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
  $("#pirateGoldLeft").classList.toggle("unallocated-warning", left !== 0);
  $("#submitPirateProposal").disabled = currentState.phase !== "proposing" || left !== 0;
  if (currentState.phase === "proposing") {
    $("#pirateInstruction").textContent = language === "zh"
      ? left === 0
        ? "100 枚金币已经全部分配。现在可以提交提案，让所有海盗同时投票。"
        : left > 0
          ? `必须先分完全部 100 枚金币；目前还有 ${left} 枚未分配，归零后提交按钮才会启用。`
          : `当前超出预算 ${Math.abs(left)} 枚；请减少分配，直到“尚未分配”恰好为 0。`
      : left === 0
        ? "All 100 coins are allocated. You can now submit the proposal for a simultaneous vote."
        : left > 0
          ? `Allocate all 100 coins first. ${left} remain; Submit unlocks when this reaches zero.`
          : `The proposal is ${Math.abs(left)} coins over budget. Reduce allocations until Unallocated is exactly zero.`;
  }
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
  const hintVisible = wormDisclosure >= 1;
  const answerVisible = wormDisclosure >= 2;
  $("#wormHint").classList.toggle("hidden", !hintVisible);
  $("#wormHint").textContent = state.phase === "finished"
    ? (language === "zh" ? "已成功抓捕" : "Captured")
    : state.suggestedHole
      ? (wormDisclosure >= 2 ? (language === "zh" ? `下一步检查 ${state.suggestedHole} 号洞` : `Next: check hole ${state.suggestedHole}`) : (language === "zh" ? "提示：保持同一奇偶节奏" : "Hint: preserve one parity rhythm"))
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

  $("#wormHintButton").classList.toggle("hidden", hintVisible);
  $("#wormAnswerButton").classList.toggle("hidden", answerVisible);
  $("#wormAnswerLocked").classList.toggle("hidden", answerVisible);
  $("#wormAnswer").classList.toggle("hidden", !answerVisible);

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
    ev: "剩余箱子价值期望", ce: "风险调整参考值", ratio: "报价 / 价值期望",
    beat: "箱内金额超过报价", volatility: "剩余波动", recommendation: "模型建议：",
    deal: "接受报价", noDeal: "继续开箱",
  } : {
    ev: "Expected remaining value", ce: "Risk-adjusted reference", ratio: "Offer / expected value",
    beat: "Chance case beats offer", volatility: "Remaining volatility", recommendation: "Model guidance: ",
    deal: "Take the deal", noDeal: "Keep opening",
  };
  $("#metrics").innerHTML = `
    <div class="metric"><span>${labels.ev}</span><strong>${formatMoney(metrics.expectedValue)}</strong></div>
    <div class="metric"><span>${labels.ce}</span><strong>${formatMoney(metrics.riskAdjustedValue)}</strong></div>
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
    counter_offer: (item) => `提出一次议价：${formatMoney(item.value)}（${item.accepted ? "银行家接受" : "银行家拒绝"}）`,
    counter_rejected: () => "议价失败，自动继续开箱",
    counter_deal: (item) => `议价成交：${formatMoney(item.value)}`,
    case_payout: (item) => `坚持到底：箱内为 ${formatMoney(item.value)}`,
  } : {
    choose: (item) => `Kept case ${item.caseId}`,
    reveal: (item) => `Opened case ${item.caseId}: ${formatMoney(item.value)}`,
    offer: (item) => `Round ${item.round} offer: ${formatMoney(item.value)}`,
    deal: (item) => `Accepted ${formatMoney(item.value)}`,
    no_deal: (item) => `Rejected the round ${item.round} offer`,
    counter_offer: (item) => `Countered at ${formatMoney(item.value)} (${item.accepted ? "accepted" : "rejected"})`,
    counter_rejected: () => "Counter rejected; play continued automatically",
    counter_deal: (item) => `Counter accepted at ${formatMoney(item.value)}`,
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
  if (activeOperation) activeOperation.abort();
  activeOperation = null;
  setOperationPending(false);
  if (openRulesGameId) closeRules();
  $("#offerModal").classList.add("hidden");
  syncModalState();
  $("#gameView").classList.add("hidden");
  $("#wormView").classList.add("hidden");
  $("#pirateView").classList.add("hidden");
  $("#pokerView").classList.add("hidden");
  $("#eCardView").classList.add("hidden");
  $("#rpsView").classList.add("hidden");
  $("#liarView").classList.add("hidden");
  $("#mastermindView").classList.add("hidden");
  $("#guessWhoView").classList.add("hidden");
  $("#pursuitView").classList.add("hidden");
  $("#battleshipView").classList.add("hidden");
  $("#blackjackView").classList.add("hidden");
  $("#loveLetterView").classList.add("hidden");
  $("#investmentView").classList.add("hidden");
  $("#goofspielView").classList.add("hidden");
  $("#lobbyView").classList.remove("hidden");
  window.scrollTo(0, 0);
}

$("#homeButton").addEventListener("click", navigateToLobby);
$("#languageZh").addEventListener("click", () => setLanguage("zh"));
$("#languageEn").addEventListener("click", () => setLanguage("en"));
$("#backButton").addEventListener("click", navigateToLobby);
document.querySelectorAll(".back-to-lobby").forEach((button) => button.addEventListener("click", navigateToLobby));
$("#newGameButton").addEventListener("click", () => startGame("cases"));
$("#newWormButton").addEventListener("click", () => startGame("worm"));
$("#wormHintButton").addEventListener("click", () => { wormDisclosure = Math.max(wormDisclosure, 1); renderWorm(); });
$("#wormAnswerButton").addEventListener("click", () => { wormDisclosure = 2; renderWorm(); });
$("#wormRevealAnswer").addEventListener("click", () => { wormDisclosure = 2; renderWorm(); });
$("#newPirateButton").addEventListener("click", () => startGame("pirates"));
$("#newPokerMatch").addEventListener("click", () => startGame("kuhn-poker", { mode: pokerMode }));
$("#pokerBasicMode").addEventListener("click", () => {
  if (pokerMode === "basic") return;
  pokerMode = "basic";
  writePreference("aip-kuhn-poker-mode", pokerMode);
  startGame("kuhn-poker", { mode: pokerMode });
});
$("#pokerAdvancedMode").addEventListener("click", () => {
  if (pokerMode === "advanced") return;
  pokerMode = "advanced";
  writePreference("aip-kuhn-poker-mode", pokerMode);
  startGame("kuhn-poker", { mode: pokerMode });
});
$("#newECardMatch").addEventListener("click", () => startGame("e-card"));
$("#newRpsMatch").addEventListener("click", () => startGame("restricted-rps"));
$("#newLiarMatch").addEventListener("click", () => startGame("liars-dice"));
$("#newBlackjackMatch").addEventListener("click", () => startGame("blackjack"));
$("#blackjackNormalMode").addEventListener("click", () => { blackjackPracticeMode = false; writePreference("aip-blackjack-mode", "normal"); renderBlackjack(); });
$("#blackjackPracticeMode").addEventListener("click", () => { blackjackPracticeMode = true; writePreference("aip-blackjack-mode", "practice"); renderBlackjack(); });
$("#guessWhoNew").addEventListener("click", () => startGame("guess-who"));
$("#guessWhoConfirm").addEventListener("click", () => {
  if (guessWhoSelected) act("guess_character", { name: guessWhoSelected });
});
$("#newPursuitMatch").addEventListener("click", () => startGame("hidden-pursuit"));
$("#newBattleshipMatch").addEventListener("click", () => startGame("battleship"));
$("#loveNewMatch").addEventListener("click", () => act("new_match"));
$("#investmentNew").addEventListener("click", () => startGame("investment"));
$("#goofspielNew").addEventListener("click", () => startGame("goofspiel", { mode: goofspielMode }));
$("#goofBasicMode").addEventListener("click", () => {
  if (goofspielMode === "basic") return;
  goofspielMode = "basic";
  writePreference("aip-goofspiel-mode", goofspielMode);
  startGame("goofspiel", { mode: goofspielMode });
});
$("#goofAdvancedMode").addEventListener("click", () => {
  if (goofspielMode === "advanced") return;
  goofspielMode = "advanced";
  writePreference("aip-goofspiel-mode", goofspielMode);
  startGame("goofspiel", { mode: goofspielMode });
});
$("#investmentSubmit").addEventListener("click", () => act("invest", { offerId: investmentOffer, fraction: investmentFraction }));
$("#loveUseSuggestion").addEventListener("click", () => {
  if (currentState.phase === "round_finished") { act("next_round"); return; }
  if (currentState.phase === "match_finished") { act("new_match"); return; }
  const play = currentState.suggestedPlay;
  if (play) act("play_card", play);
});
$("#battleRandomize").addEventListener("click", () => act("randomize_fleet"));
$("#battleStart").addEventListener("click", () => act("start_battle"));
$("#battleBoardSize").addEventListener("change", (event) => act("set_board_size", { boardSize: Number(event.target.value) }));
$("#blackjackAiPlay").addEventListener("click", () => act("ai_play"));
$("#counterOfferButton").addEventListener("click", () => act("counter_offer", { amount: Number($("#counterOfferInput").value) }));
$("#liarRaise").addEventListener("click", () => act("raise_bid", {
  quantity: Number($("#liarQuantity").value),
  face: Number($("#liarFace").value),
}));
$("#liarChallenge").addEventListener("click", () => act("challenge"));
$("#mastermindNew").addEventListener("click", () => act("new_game"));
function submitMastermindGuess() {
  const raw = $("#mastermindInput").value.trim();
  if (!/^\d{4}$/.test(raw) || new Set(raw).size !== 4) {
    showToast(language === "zh" ? "请输入四个不重复的数字，例如 0123。" : "Enter four distinct digits, such as 0123.");
    return;
  }
  act("submit_guess", { guess: [...raw].map(Number) });
}
$("#mastermindSubmit").addEventListener("click", submitMastermindGuess);
$("#mastermindUseSuggestion").addEventListener("click", () => {
  if (!currentState?.suggestedGuess) return;
  $("#mastermindInput").value = currentState.suggestedGuess.join("");
  $("#mastermindInput").focus();
});
$("#mastermindInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.repeat) submitMastermindGuess();
});
$("#submitPirateProposal").addEventListener("click", () => {
  const allocation = [...document.querySelectorAll(".pirate-gold-input")].map((input) => Number(input.value));
  act("submit_proposal", { allocation });
});
$("#dealButton").addEventListener("click", () => act("deal"));
$("#noDealButton").addEventListener("click", () => act("no_deal"));
$("#rulesClose").addEventListener("click", closeRules);
$("#rulesModal").addEventListener("click", (event) => { if (event.target.id === "rulesModal") closeRules(); });
document.addEventListener("keydown", (event) => {
  const modal = visibleModal();
  if (!modal) return;
  if (event.key === "Escape" && openRulesGameId) closeRules();
  if (event.key !== "Tab") return;
  const focusable = [...modal.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")]
    .filter((element) => !element.disabled && element.getClientRects().length);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
window.addEventListener("hashchange", () => applyRoute().catch((error) => showToast(error.message)));
applyLanguage();
loadLobby().catch((error) => showToast(error.message));
