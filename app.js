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
let openRulesGameId = null;
let actionPending = false;
let activeOperation = null;
let toastTimer = null;

const copy = {
  zh: {
    brandName: "非对称博弈实验室", localOnly: "浏览器临时会话",
    heroLine1: "把推理变成一场", heroLine2: "真正可以玩的博弈",
    heroCopy: "选择一个实验。你做决定，系统隐藏信息、扮演对手，并在关键时刻揭示概率与代价。",
    backLobby: "← 返回大厅", restart: "重新开始", restartCouncil: "重新召开议会", playNow: "开始游戏 →", comingSoon: "后续开放",
    caseEyebrow: "CASE 01 · 风险与谈判 · 入门", caseTitle: "命运之箱",
    wormEyebrow: "CASE 10 · 隐藏状态追踪 · 挑战", wormTitle: "移动虫穴",
    pirateEyebrow: "CASE 07 · 逆向归纳与联盟 · 中等", pirateTitle: "海盗议会",
    pokerEyebrow: "CASE 08 · 私有信息与诈唬 · 较难", pokerTitle: "库恩扑克",
    restartMatch: "重新开始比赛", handNumber: "当前牌局", yourScore: "你的净筹码",
    potSize: "底池", aiScore: "AI 净筹码", strategyAi: "策略型 AI", you: "你",
    yourInformationSet: "你的信息集", quickRules: "快速规则",
    pokerRules: "双方先各投入 1。下注为 1；跟注后比牌，弃牌则直接输。K 最大、J 最小。AI 会按概率诈唬，所以同一种动作不总代表同一张牌。",
    eCardEyebrow: "CASE 06 · 非对称收益与混合策略 · 中等", eCardTitle: "E-Card 皇帝牌",
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
    blackjackScope: "此建议针对六副牌、软 17 停牌、不可分牌/投降/保险且不计牌的动作集合。改变规则或利用牌靴构成后，最优动作可能改变。",
    liarEyebrow: "CASE 09 · 隐藏骰子与公开信号 · 较难", liarTitle: "骗子骰子", liarRound: "回合",
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
    battleshipEyebrow: "CASE 05 · 隐藏部署与概率搜索 · 中等", battleshipTitle: "海战棋",
    yourFleet: "你的舰队", enemyWaters: "敌方海域", randomizeFleet: "重新随机布阵", startBattle: "确认布阵，开始战斗",
    shipsRemaining: "剩余舰船", candidateWorlds: "候选部署", advisorShot: "概率建议", battleHistory: "交火记录",
    rulesEyebrow: "玩法说明", rulesTitle: "游戏规则", closeRules: "关闭",
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
    connectionFailed: "连接暂时失败，请检查网络后重试。", invalidResponse: "页面收到异常响应，请刷新后重试。",
    sessionExpired: "这局临时游戏已经过期，请重新开始。",
  },
  en: {
    brandName: "Asymmetric Games Lab", localOnly: "Browser session",
    heroLine1: "Turn reasoning into", heroLine2: "games you can actually play",
    heroCopy: "Choose an experiment. You decide; the system hides information, plays the opposition, and reveals probability and cost at decisive moments.",
    backLobby: "← Back to lobby", restart: "New game", restartCouncil: "New council", playNow: "Play now →", comingSoon: "Coming later",
    caseEyebrow: "CASE 01 · RISK & NEGOTIATION · BEGINNER", caseTitle: "Cases of Fate",
    wormEyebrow: "CASE 10 · HIDDEN-STATE TRACKING · CHALLENGE", wormTitle: "The Moving Worm",
    pirateEyebrow: "CASE 07 · BACKWARD INDUCTION & COALITIONS · MEDIUM", pirateTitle: "Pirate Council",
    pokerEyebrow: "CASE 08 · PRIVATE INFORMATION & BLUFFING · HARD", pokerTitle: "Kuhn Poker",
    restartMatch: "Restart match", handNumber: "Current hand", yourScore: "Your net chips",
    potSize: "Pot", aiScore: "AI net chips", strategyAi: "Strategy AI", you: "You",
    yourInformationSet: "Your information set", quickRules: "Quick rules",
    pokerRules: "Both players ante 1. A bet costs 1; a call leads to showdown, while a fold loses immediately. K is high and J is low. The AI bluffs probabilistically, so one action never reveals one card with certainty.",
    eCardEyebrow: "CASE 06 · ASYMMETRIC PAYOFFS & MIXED STRATEGY · MEDIUM", eCardTitle: "E-Card",
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
    blackjackScope: "This advice is scoped to six decks, dealer standing on soft 17, no split/surrender/insurance, and no card counting. Change the rules or use shoe composition and the optimal action may change.",
    liarEyebrow: "CASE 09 · HIDDEN DICE & PUBLIC SIGNALS · HARD", liarTitle: "Liar's Dice", liarRound: "Round",
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
    battleshipEyebrow: "CASE 05 · HIDDEN DEPLOYMENT & PROBABILITY SEARCH · MEDIUM", battleshipTitle: "Battleship",
    yourFleet: "Your fleet", enemyWaters: "Enemy waters", randomizeFleet: "Randomize fleet", startBattle: "Lock fleet and start",
    shipsRemaining: "Ships remaining", candidateWorlds: "Candidate placements", advisorShot: "Probability hint", battleHistory: "Battle log",
    rulesEyebrow: "HOW TO PLAY", rulesTitle: "Rules", closeRules: "Close",
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
    battleship: ["海战棋", "部署舰队，在未知海域中逐格搜索敌舰，对抗概率热力图 AI。", "单人 · 隐藏部署与概率搜索"],
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
    battleship: ["Battleship", "Deploy a fleet, search unknown waters cell by cell, and face a probability-density AI.", "Solo · Hidden deployment & search"],
    auction: ["100-Unit All-Pay Auction", "Fight for leadership through public prices, alliances, and defection.", "Local multiplayer · Coming soon"],
  },
};

const difficultyCopy = {
  zh: { cases: "入门", blackjack: "入门", "restricted-rps": "简单", mastermind: "简单", battleship: "中等", "e-card": "中等", pirates: "中等", "kuhn-poker": "较难", "liars-dice": "较难", worm: "挑战", auction: "未开放" },
  en: { cases: "Beginner", blackjack: "Beginner", "restricted-rps": "Easy", mastermind: "Easy", battleship: "Medium", "e-card": "Medium", pirates: "Medium", "kuhn-poker": "Hard", "liars-dice": "Hard", worm: "Challenge", auction: "Coming soon" },
};

const rulesCopy = {
  zh: {
    cases: ["目标：在 26 个箱子中尽可能拿到高奖金。", "先点击任意一个箱子作为你的保留箱；之后不要再打开它。", "按页面提示点击指定数量的其他箱子，打开后会显示金额。完成本轮后银行家报价。", "报价出现时点击“接受报价”立即结束并领取报价；点击“拒绝，继续开箱”则进入下一轮。", "坚持到最后会拿到保留箱里的金额；右侧的期望值、风险和建议只是辅助，不会替你操作。"],
    worm: ["目标：在虫子逃走前抓到它。五个洞按 1–5 排成一行。", "每回合点击一个洞进行检查；点击正确位置就立即成功。", "如果没抓到，虫子会移动到相邻洞，系统随后更新“仍可能的位置”。", "这是最坏情况模式，不靠随机运气；点击“保证抓捕序列”中下一个洞，才能保证最终抓到。"],
    pirates: ["目标：让你的提案获得足够票数，并让海盗 A 活下来。", "在每个海盗的金币输入框中填整数，所有分配之和必须正好等于 100。", "点击“提交提案并投票”。每名海盗会比较你的报价与否决后按逆向归纳得到的金币/生存结果。", "达到页面显示的赞成票数就通过；否则 A 被处决，系统展示实际结果和理论最优方案。"],
    "kuhn-poker": ["目标：赢得更多筹码。你和 AI 各拿一张 J、Q 或 K，并各投入 1 枚底注。", "轮到你时可点击“过牌”或“下注”；下注会额外投入 1 枚。", "若 AI 下注，你只能选择“跟注”或“弃牌”；弃牌立即输掉底注。", "跟注后双方亮牌，K > Q > J，牌大者赢得底池；下一局会交换先手。"],
    "e-card": ["目标：利用特殊牌的循环克制关系赢得高分。你和 AI 各有 1 张特殊牌与 4 张市民牌。", "点击手中的一张牌，双方会同时出牌，AI 的选择在揭示前保持隐藏。", "皇帝击败市民，市民击败奴隶，奴隶击败皇帝；奴隶获胜通常得到更高收益。", "市民对市民不会结束本轮，两张牌会被消耗后继续；特殊牌相遇则按克制关系结束本轮。"],
    "restricted-rps": ["目标：在有限库存耗尽前赢得更多回合。你和 AI 各有相同数量的石头、剪刀、布。", "点击一张仍有库存的手势牌；双方同时出牌，使用过的牌永久减少。", "石头胜剪刀，剪刀胜布，布胜石头；相同手势为平局。双方库存和历史都会公开。", "库存全部用完后比赛结束。页面显示均衡建议，以及 AI 是否根据你的历史偏好进行了有限度适应。"],
    blackjack: ["目标：让自己的点数尽量接近 21，但超过 21 就爆牌并立即输。", "A 可算 1 或 11；J/Q/K 算 10。开始时你会看到两张手牌和庄家的一张明牌。", "点击“要牌”再拿一张；点击“停牌”结束行动；首轮可点击“加倍”并只再拿一张。", "庄家随后按固定规则补牌（软 17 停牌），最后比较点数；黑杰克按页面规则结算。右侧可让 AI 执行基础策略建议。"],
    "liars-dice": ["目标：判断公开叫价是真实还是虚张声势，并在质疑中赢下本轮。", "你能看到自己的骰子，但看不到 AI 的骰子。叫价“数量 × 点数”表示全桌至少有这么多个该点数。", "点击“加注”提交更高的数量，或在数量相同时提交更高点数；1 点对 2–6 点是万能牌。", "如果你认为上一口不可信，点击“质疑”。系统揭示全部骰子并根据实际数量判定胜负。"],
    mastermind: ["目标：在 10 次尝试内破解 AI 隐藏的四位密码。密码从 0–9 中选择四个不同数字，共有 5,040 种可能。", "输入恰好四个不同数字，例如 0123；首位可以是 0。点击“提交猜测”后才能得到反馈。", "“位置正确”表示数字和位置都对；“数字正确但位置不同”表示数字存在但放错位置。反馈只给数量，不指出具体是哪一位。", "观察每轮排除的候选数并继续推理。你可以完全自己猜，也可以点击“采用 AI 建议”复制 minimax 建议，再提交。", "得到 4 个位置正确即获胜。连续完成多局后，页面会计算你的成功局平均步数与最佳成绩。"],
    battleship: ["目标：在概率 AI 击沉你的全部舰船之前，先找到并击沉它的舰队。", "布阵阶段先选择 10×10、12×12 或 15×15 海域；地图越大，双方舰船也越多。", "不同颜色表示不同舰船。点击舰船卡可旋转 90°，也可点击“重新随机布阵”；直线舰船翻转 180°占据的格子不变。", "满意后点击“确认布阵，开始战斗”。战斗阶段点击敌方未知格；淡点表示落空，红色表示命中，深红色表示击沉。", "你每开一炮，AI 会立即根据仍合法的水平与垂直部署还击。已经射击过的格子不能重复选择。", "候选部署表示目前仍符合反馈的舰船位置数量；概率建议给出覆盖合法部署最多的格子，但你可以选择别处。"],
  },
  en: {
    cases: ["Goal: maximize your payout from 26 cases.", "Click one case to keep; never open it afterward.", "Open the number of other cases shown on screen. The banker then makes an offer.", "Choose Deal to end for the offer, or No Deal to continue. If you reach the end, you receive the kept case's value."],
    worm: ["Goal: catch the worm. Five holes are arranged from 1 to 5.", "Check one hole per turn. A correct check catches it immediately.", "After a miss, the adversary moves to a neighboring hole and the possible-position panel updates.", "This is worst-case play, so follow the guaranteed sequence rather than relying on luck."],
    pirates: ["Goal: pass your proposal and keep pirate A alive.", "Enter integer gold allocations totaling exactly 100, then submit the proposal.", "Each pirate compares your offer with the continuation payoff after A's execution.", "If enough votes support the proposal it passes; otherwise A is executed and the benchmark is shown."],
    "kuhn-poker": ["Goal: win chips. Each player receives J, Q, or K and antes 1.", "When first, choose Check or Bet. Facing a bet, choose Call or Fold.", "A fold loses immediately; a call reaches showdown. K beats Q, which beats J.", "The next hand swaps first position."],
    "e-card": ["Goal: exploit the asymmetric special-card cycle. Each side holds one special card and four citizens.", "Click one card; both sides reveal simultaneously.", "Emperor beats Citizen, Citizen beats Slave, and Slave beats Emperor. Slave wins pay more.", "Citizen versus Citizen consumes both cards and continues the round."],
    "restricted-rps": ["Goal: win more rounds before your finite inventory runs out.", "Click an available Rock, Paper, or Scissors card; both choices are simultaneous and the card is consumed.", "Rock beats Scissors, Scissors beats Paper, and Paper beats Rock. Equal moves draw.", "The match ends when the inventory is exhausted; equilibrium and adaptation diagnostics remain visible."],
    blackjack: ["Goal: approach 21 without going over.", "A counts as 1 or 11; face cards count as 10. You see your hand and the dealer upcard.", "Choose Hit, Stand, or Double (first decision only). The dealer then follows the fixed soft-17 rule.", "Compare the final totals; the strategy panel can execute the basic-strategy recommendation."],
    "liars-dice": ["Goal: identify a bluff and win the round.", "You see your dice only. A bid Quantity × Face claims at least that many matching dice across both hands.", "Raise quantity, or raise face at equal quantity; ones are wild for faces 2–6.", "Challenge the current bid to reveal all dice and settle the round."],
    mastermind: ["Goal: crack a four-digit hidden code in ten attempts. It uses four distinct digits from 0–9, creating 5,040 possible worlds.", "Enter exactly four different digits, such as 0123. A leading zero is valid, then submit.", "Exact means right digit and position; misplaced means a right digit in the wrong position. Counts never identify the individual digits.", "Reason independently or copy the bounded-minimax AI suggestion. Each history row shows how many candidates that experiment removed.", "Four exact positions win. Across solved rounds, the page tracks your average and best attempt count."],
    battleship: ["Goal: sink the enemy fleet before the probability AI sinks yours.", "Choose a 10×10, 12×12, or 15×15 sea during deployment; larger boards add ships to preserve action density.", "Each ship has its own color. Click a ship card to rotate it 90°, or randomize the fleet. A 180° flip of a straight ship occupies the same cells.", "Lock the layout, then click unknown enemy cells. A pale dot is a miss, red is a hit, and dark red is a sunk ship.", "The AI returns fire from legal horizontal and vertical placements after every shot. Fired cells cannot be selected again.", "Candidate placements count ship positions consistent with observations; the hint marks a high-density cell without forcing it."],
  },
};

const ruleDetails = {
  zh: {
    cases: { role: "你是一名电视游戏参赛者。26 个箱子里分别装着从极小到一百万不等的奖金，但你看不到每个箱子的金额。你要一边排除金额，一边决定是否接受银行家的现金报价。", example: "例：你保留了 7 号箱，本轮打开 3 号箱并发现里面是 1 元。1 元从奖金池消失，说明你的保留箱更不可能是低额。完成规定开箱数后，银行家可能报价 80,000 元；接受就拿 80,000 元离场，拒绝就继续冒险。", finish: "接受任意一次银行家报价时立即结束；若一直拒绝，就在最后打开保留箱并获得其中金额。这里没有唯一正确答案——保守玩家可能早接受，愿意冒险的玩家可能继续。", terms: "保留箱＝你最初选中、暂时不打开的箱子；剩余期望值＝所有未揭晓金额的平均数；报价/期望值越高，银行家的条件通常越有吸引力。" },
    worm: { role: "你是搜捕者，虫子是会主动躲避你的对手。你看不到它在哪个洞，只能根据它每次必须移动到相邻洞的规则推理。", example: "例：你检查 2 号洞但没抓到。虫子此前若在 1 号，只能移到 2 号；若在 3 号，可移到 2 或 4。系统会把仍然可能的洞显示出来。", finish: "当你检查的洞覆盖虫子所有仍合法的可能位置时，保证抓捕成功。乱点可能永远抓不到；从第一步严格执行页面给出的 2→3→4→2→3→4，可以在五洞规则下保证成功。", terms: "可能位置＝根据所有历史记录，虫子现在仍可能所在的洞；保证策略＝无论虫子怎样选择合法移动都能成功的检查顺序。" },
    pirates: { role: "你扮演最资深海盗 A。规则是：A 提出如何分 100 枚金币，所有海盗投票；若票数不足，A 被处决，下一位海盗重新提案。每个人都知道之后会发生什么。", example: "例：如果海盗 C 在 A 死后能得到 1 枚金币，那么给 C 仍然只有 1 枚通常买不到他的票；给 2 枚才比他的后续结果更好。也可以收买那些 A 死后会一无所有的人。", finish: "分配总和恰好为 100 后提交。赞成票达到页面要求，A 存活并按提案分金币；票数不足则 A 死亡，页面展示后续结果。你的核心任务是用尽量少的金币买到足够票数。", terms: "逆向归纳＝先算只剩最后几名海盗时会怎样，再一步步倒推到现在；延续收益＝否决当前提案后，该海盗预计能否存活以及能拿多少金币。" },
    "kuhn-poker": { role: "这是把扑克压缩到三张牌的练习。你只知道自己的牌，不知道 AI 的牌；下注既可能代表强牌，也可能是拿弱牌诈唬。", example: "例：你拿 Q，AI 下注。AI 可能拿 K 认真下注，也可能拿 J 诈唬。跟注要再投入 1 枚并亮牌；弃牌会损失已投入的底注，但避免继续亏损。", finish: "一方弃牌或双方完成过牌/跟注后，本局结束并结算筹码。连续多局比较净筹码；同一个 AI 动作不一定对应同一张牌。", terms: "过牌＝不加钱，把行动交给对方；下注＝额外投入 1；跟注＝支付同样金额并要求亮牌；诈唬＝弱牌下注，希望对手弃牌。" },
    "e-card": { role: "你和 AI 轮流扮演皇帝方与奴隶方。皇帝通常强，但奴隶能击败皇帝且回报更高，因此双方都要猜特殊牌会在哪一次出现。", example: "例：你是奴隶方，前两次先出市民试探。若 AI 也出市民，两张市民消耗后继续。你第三次出奴隶，若 AI 此时出皇帝，你将以弱胜强获得高分；若 AI 出市民，你会输。", finish: "出现非市民平局的胜负关系时，本轮结束并计分，然后双方交换阵营开始下一轮。重点不是只看单张强弱，而是推测对方何时使用唯一的特殊牌。", terms: "皇帝＞市民、 市民＞奴隶、奴隶＞皇帝；特殊牌＝皇帝或奴隶；市民相撞＝平局并消耗双方各一张市民。" },
    "restricted-rps": { role: "这是有库存的猜拳。普通猜拳每轮都能随便出，但这里每种手势只有有限张；你刚才用掉什么，会改变后面还能怎么出。", example: "例：你只剩 1 石头、0 剪刀、2 布，AI 能看到这个库存，所以知道你不可能出剪刀。你仍需在石头和布之间随机选择，避免行为过于容易预测。", finish: "双方所有手势卡用完后结束，胜局多的一方获胜。每轮后可以看公开库存、均衡建议和 AI 对你历史偏好的分析。", terms: "库存＝每种手势还可使用几次；均衡建议＝即使对手知道你的概率，也难以稳定利用你的随机方案；适应＝AI 根据你过去偏爱哪种手势调整。" },
    blackjack: { role: "你是玩家，与按固定规则行动的庄家比较点数。你看得到庄家一张明牌，但看不到他的底牌，因此每次要牌都在不完全信息下承担爆牌风险。", example: "例：你有 10+6=16 点，庄家明牌是 10。停牌很可能输给庄家较高点数；要牌可能改善手牌，也可能抽到 6 以上直接爆牌。页面的基础策略会告诉你在长期统计下哪种动作损失更小。", finish: "你爆牌时立即输；你停牌或加倍后庄家自动补牌，最后不爆牌且更接近 21 的一方获胜，同点为和局。每局结束后点击下一局。", terms: "要牌＝再抽一张；停牌＝不再抽；加倍＝赌注翻倍且只抽一张；软牌＝有 A 暂时按 11 计算的手牌；爆牌＝超过 21。" },
    "liars-dice": { role: "你和 AI 各有五颗隐藏骰子。双方看不到对方点数，只能通过越来越高的公开叫价传递信息或诈唬。", example: "例：你手里有两个 4 和一个 1。因为 1 是万能牌，你已知道全桌至少有三个可算作 4。叫“3×4”很安全；AI 若叫到“7×4”，你需要判断它真的有很多 4，还是在虚张声势。", finish: "当任一方质疑时揭开所有骰子。实际匹配数量达到叫价，质疑者输；数量不足，最后叫价者输。赢一轮得 1 分，可继续开始下一轮。", terms: "叫价 3×4＝声称全桌至少有三个 4（包括可作万能牌的 1）；加注＝提高数量，或数量不变时提高点数；质疑＝认为当前叫价不成立。" },
    mastermind: { role: "这是经典 Bulls and Cows（几A几B）数字推理。AI 从 0–9 中秘密选择四个不重复数字，包括 0123 这样的前导零密码。你看到的不是答案，而是逐轮反馈形成的信息集。", example: "例：答案假设为 0-3-5-6，你猜 0-2-6-4。数字 0 的位置也正确，因此位置正确为 1；数字 6 存在但位置错误，因此错位正确为 1；2 和 4 不在密码中。", finish: "十次之内得到 4 个位置正确即获胜；十次仍未破解则答案揭晓。建议策略最小化下一轮最大的反馈分组，再比较平均剩余候选；它是强而快速的单步 minimax 启发式，不是已经证明的全局最少平均步数策略。", terms: "候选数量＝与全部历史反馈一致的密码数；信息集＝你当前无法区分的所有候选；最坏剩余＝采用该建议后，无论收到哪种反馈，最大反馈分组的大小。" },
    battleship: { role: "你和 AI 在相互隔离的海域秘密部署舰队。标准、扩展和大型地图分别为 10×10、12×12、15×15；你只能看到自己的彩色舰船，敌舰通过命中反馈逐步暴露。", example: "例：你把蓝色长度 4 舰旋转为垂直方向，然后向敌方 B7 开火并命中。下一炮打 B8：若再次命中，可沿同一方向搜索；若落空，就要考虑舰船可能纵向延伸。", finish: "一艘船的所有格子都被命中时即被击沉；任一方全部舰船沉没时比赛结束。结束后敌方完整彩色舰队会揭晓，便于复盘。", terms: "旋转 90°＝在水平与垂直之间切换；180°翻转对没有首尾差异的直线舰船不产生新布局；候选部署＝与命中、落空和击沉反馈相容的水平或垂直位置总数。" },
  },
  en: {
    cases: { role: "You are a TV-game contestant. Twenty-six cases hide prizes from tiny amounts to one million. You eliminate prizes and decide whether to accept the banker's cash offer.", example: "Example: you keep case 7 and open case 3, revealing $1. That prize leaves the board. After the required openings, an $80,000 offer means you can leave with $80,000 or reject it and keep risking your hidden case.", finish: "The game ends when you accept an offer, or when you reject every offer and receive the value in your kept case. There is no single correct risk preference.", terms: "Kept case: your unopened original choice. Expected value: the average of unrevealed prizes. A higher offer-to-EV ratio is usually more attractive." },
    worm: { role: "You are the searcher; the worm actively avoids capture. You cannot see it and must reason from the rule that every miss forces it to move to a neighboring hole.", example: "Example: after you miss at hole 2, a worm formerly at 1 can only move to 2, while one at 3 may move to 2 or 4. The possible-position display updates these paths.", finish: "Capture is guaranteed only when your check covers every remaining legal location. For five holes, following 2→3→4→2→3→4 from the start guarantees success.", terms: "Possible positions are locations consistent with all history. A guaranteed strategy succeeds against every legal movement choice." },
    pirates: { role: "You are senior pirate A. You propose how to split 100 coins. If the vote fails, A dies and the next pirate proposes, so everyone compares the present offer with that future outcome.", example: "Example: if C expects 1 coin after A dies, offering C 1 is normally insufficient; 2 is better than C's continuation payoff and can buy the vote.", finish: "Submit allocations totaling exactly 100. Enough yes votes pass the plan and keep A alive; otherwise A dies. Your challenge is buying enough votes as cheaply as possible.", terms: "Backward induction solves later councils first and works back. Continuation payoff is a pirate's expected survival and gold after rejection." },
    "kuhn-poker": { role: "This is poker reduced to J, Q, and K. You know your card but not the AI's; a bet can signal strength or be a bluff with a weak card.", example: "Example: you hold Q and the AI bets. It may hold K for value or J as a bluff. Calling pays 1 more to reveal; folding loses the ante but avoids further loss.", finish: "A fold or completed check/call sequence ends the hand and settles chips. Play repeated hands and track net chips.", terms: "Check passes without paying. Bet adds 1. Call matches the bet and shows cards. Bluff means betting weak to induce a fold." },
    "e-card": { role: "You and the AI alternate Emperor and Slave sides. Emperor is usually strong, but Slave beats Emperor for a larger reward, so timing the unique special card is the central decision.", example: "Example: as Slave, you spend citizens on early probes. If you play Slave exactly when the AI commits Emperor, you score the upset; against Citizen, Slave loses.", finish: "A decisive non-citizen tie outcome ends and scores the round, then roles swap. Track which cards were consumed and infer when the AI will commit its special card.", terms: "Emperor beats Citizen; Citizen beats Slave; Slave beats Emperor. Citizen versus Citizen consumes both and continues." },
    "restricted-rps": { role: "This is Rock-Paper-Scissors with limited cards. Every move you spend changes what remains possible later, and both inventories are public.", example: "Example: with 1 Rock, 0 Scissors, and 2 Paper left, the AI knows Scissors is impossible. Randomizing between Rock and Paper keeps your choice less predictable.", finish: "The match ends when all cards are used; more round wins takes the match. Review inventory, equilibrium guidance, and AI adaptation after each reveal.", terms: "Inventory is remaining uses. Equilibrium guidance is a mixture that is hard to exploit. Adaptation is the AI reacting to your historical bias." },
    blackjack: { role: "You compare your hand with a fixed-rule dealer. You see one dealer card but not the hole card, so Hit and Stand decisions trade improvement against bust risk.", example: "Example: you have 16 against a dealer 10. Standing often loses to a stronger dealer total; hitting may improve the hand or bust. Basic strategy identifies the better long-run action.", finish: "Bust loses immediately. After you stand or double, the dealer draws automatically; the higher non-bust total wins and equal totals push.", terms: "Hit: draw. Stand: stop. Double: double the stake and draw once. Soft hand: an Ace currently counted as 11. Bust: exceed 21." },
    "liars-dice": { role: "You and the AI each hold five hidden dice. Public bids rise while private dice stay secret, so every bid can be information or a bluff.", example: "Example: two 4s and one wild 1 give you three known matches for face 4. A bid of 3×4 is safe; after the AI raises to 7×4, decide whether its private hand supports that claim.", finish: "A challenge reveals all dice. If the bid's quantity exists, the challenger loses; otherwise the last bidder loses. The winner scores one point.", terms: "3×4 claims at least three 4-matches across both hands. Raise increases quantity or face. Challenge says the current claim is false." },
    mastermind: { role: "This is classic Bulls and Cows. The AI secretly chooses four distinct digits from 0–9, including leading-zero codes such as 0123. Public feedback transforms the set of hidden worlds after every guess.", example: "If the code is 0-3-5-6 and you guess 0-2-6-4, digit 0 gives one exact match and digit 6 gives one misplaced match; 2 and 4 are absent.", finish: "Four exact matches within ten guesses wins; otherwise the code is revealed. The adviser minimizes the largest next feedback bucket, then expected survivors. It is a strong, responsive one-step minimax heuristic, not a proof of globally minimal average guesses.", terms: "Candidate count is the number of codes consistent with every clue. The information set is the candidates you cannot yet distinguish. Worst-case remaining is the largest possible feedback bucket after the suggested guess." },
    battleship: { role: "You and the AI deploy private fleets on separate 10×10, 12×12, or 15×15 seas. You see your individually colored ships only; enemy ships emerge through hit feedback.", example: "Example: rotate the blue length-4 ship vertically, then hit B7. Firing at B8 tests a horizontal extension; a miss makes a vertical ship more plausible.", finish: "A ship sinks when every cell is hit. The match ends when either fleet is gone, then the complete colored enemy fleet is revealed for review.", terms: "Rotate 90° switches horizontal and vertical. A 180° flip creates no new layout for an undirected straight ship. Candidate placements count legal horizontal and vertical positions consistent with feedback." },
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
    const gameId = { gameView: "cases", wormView: "worm", pirateView: "pirates", pokerView: "kuhn-poker", eCardView: "e-card", rpsView: "restricted-rps", liarView: "liars-dice", blackjackView: "blackjack", mastermindView: "mastermind", battleshipView: "battleship" }[view?.id];
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
}

function closeRules() { openRulesGameId = null; $("#rulesModal").classList.add("hidden"); }

function tr(key) { return copy[language][key] ?? key; }

function applyLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.title = language === "zh" ? "AIP · 非对称博弈实验室" : "AIP · Asymmetric Games Lab";
  $("#homeButton").setAttribute("aria-label", language === "zh" ? "返回游戏大厅" : "Return to game lobby");
  $("#rulesClose").setAttribute("aria-label", tr("closeRules"));
  money = new Intl.NumberFormat(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: 2 });
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = tr(element.dataset.i18n);
  });
  installRulesButtons();
  document.querySelectorAll(".rules-button").forEach((button) => { button.textContent = tr("rulesTitle"); });
  $("#languageZh").classList.toggle("active", language === "zh");
  $("#languageEn").classList.toggle("active", language === "en");
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
    button.addEventListener("click", () => startGame(button.dataset.game));
  });
}

async function startGame(gameId = "cases", options = {}) {
  if (actionPending) return;
  const controller = new AbortController();
  activeOperation = controller;
  actionPending = true;
  document.querySelector("main").setAttribute("aria-busy", "true");
  try {
    const gameOptions = gameId === "cases"
      ? { riskTolerance: 100000, ...options }
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
    if (gameId === "pirates") pirateDraft = currentState.pirates.map(() => 0);
    $("#lobbyView").classList.add("hidden");
    $("#gameView").classList.toggle("hidden", gameId !== "cases");
    $("#wormView").classList.toggle("hidden", gameId !== "worm");
    $("#pirateView").classList.toggle("hidden", gameId !== "pirates");
    $("#pokerView").classList.toggle("hidden", gameId !== "kuhn-poker");
    $("#eCardView").classList.toggle("hidden", gameId !== "e-card");
    $("#rpsView").classList.toggle("hidden", gameId !== "restricted-rps");
    $("#liarView").classList.toggle("hidden", gameId !== "liars-dice");
    $("#mastermindView").classList.toggle("hidden", gameId !== "mastermind");
    $("#battleshipView").classList.toggle("hidden", gameId !== "battleship");
    $("#blackjackView").classList.toggle("hidden", gameId !== "blackjack");
    window.scrollTo(0, 0);
    render();
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
      actionPending = false;
      document.querySelector("main").removeAttribute("aria-busy");
    }
  }
}

async function act(action, payload = {}) {
  if (actionPending) return;
  const controller = new AbortController();
  activeOperation = controller;
  actionPending = true;
  document.querySelector("main").setAttribute("aria-busy", "true");
  try {
    const result = await request(`/api/sessions/${sessionId}/actions`, {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({ action, payload }),
    });
    if (controller.signal.aborted) return;
    currentState = result.state;
    render();
    if (currentState.gameId === "mastermind" && ["submit_guess", "new_game"].includes(action)) {
      $("#mastermindInput").value = "";
    }
  } catch (error) {
    if (error.name !== "AbortError") showToast(error.message);
  } finally {
    if (activeOperation === controller) {
      activeOperation = null;
      actionPending = false;
      document.querySelector("main").removeAttribute("aria-busy");
    }
  }
}

function render() {
  if (currentState.gameId === "battleship") {
    renderBattleship();
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
  const instructions = language === "zh" ? {
    choose: "第一步：点击一个箱子作为你的保留箱",
    opening: `本轮请再打开 ${state.opensRemaining} 个箱子，完成后银行家会报价`,
    offer: state.isFinalOffer ? "最终阶段：只剩你的保留箱，请决定接受最终报价还是直接揭晓" : "银行家正在等待：接受报价，或拒绝并继续开箱",
    finished: state.result?.kind === "deal" ? `本局结束 · 你接受了 ${finalPayout}` : `最终揭晓 · 你的保留箱奖金为 ${finalPayout}`,
  } : {
    choose: "First: click one case to keep",
    opening: `Open ${state.opensRemaining} more case(s); the banker will then make an offer`,
    offer: state.isFinalOffer ? "Final stage: only your kept case remains. Take the final offer or reveal it" : "The banker is waiting: take the offer or reject it and keep opening",
    finished: state.result?.kind === "deal" ? `Game over · You accepted ${finalPayout}` : `Final reveal · Your kept case pays ${finalPayout}`,
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
    $("#offerContext").textContent = state.isFinalOffer
      ? (language === "zh" ? `这是最终报价。接受可立即获得 ${formatMoney(state.offer)}；拒绝后会直接打开 ${state.chosenCase} 号保留箱并领取其中金额。` : `This is the final offer. Take ${formatMoney(state.offer)} now, or reject it to reveal and receive kept case No. ${state.chosenCase}.`)
      : (language === "zh" ? `还有 ${remaining} 个可能金额。接受就立即结束；拒绝则继续开箱。模型保留价为 ${formatMoney(state.metrics.certaintyEquivalent)}。` : `${remaining} prize values remain. Deal ends the game; No Deal continues. Model reservation value: ${formatMoney(state.metrics.certaintyEquivalent)}.`);
    $("#dealButton").textContent = state.isFinalOffer ? (language === "zh" ? "接受最终报价" : "Take final offer") : tr("acceptOffer");
    $("#noDealButton").textContent = state.isFinalOffer ? (language === "zh" ? "拒绝并揭晓保留箱" : "Reject and reveal my case") : tr("rejectOffer");
  }
}

function renderBlackjack() {
  const state = currentState;
  const actionNames = language === "zh"
    ? { hit: "要牌", stand: "停牌", double: "加倍", new_round: "下一局" }
    : { hit: "Hit", stand: "Stand", double: "Double", new_round: "Next hand" };
  $("#blackjackRound").textContent = state.roundNumber;
  $("#blackjackBankroll").textContent = signed(state.bankroll);
  $("#blackjackRecord").textContent = `${state.wins} / ${state.losses} / ${state.pushes}`;
  $("#blackjackAccuracy").textContent = state.strategyAccuracy == null ? "—" : `${(state.strategyAccuracy * 100).toFixed(0)}%`;
  $("#shoeRemaining").textContent = `${state.shoeRemaining} ${language === "zh" ? "张剩余" : "CARDS LEFT"}`;
  $("#playerTotal").textContent = `${state.playerSoft ? (language === "zh" ? "软 " : "Soft ") : ""}${state.playerTotal}`;
  $("#dealerTotal").textContent = state.dealerTotal == null ? (language === "zh" ? "明牌" : "Upcard") : state.dealerTotal;
  $("#playerCards").innerHTML = state.playerHand.map(renderBlackjackCard).join("");
  $("#dealerCards").innerHTML = state.dealerHand.map(renderBlackjackCard).join("") + (state.dealerHoleHidden ? '<div class="blackjack-card hidden-card">?</div>' : "");
  $("#blackjackActions").innerHTML = state.legalActions.map((action) => `<button data-blackjack-action="${action}">${actionNames[action]}</button>`).join("");
  document.querySelectorAll("[data-blackjack-action]").forEach((button) => button.addEventListener("click", () => act(button.dataset.blackjackAction)));
  $("#blackjackRecommendation").textContent = state.recommendation
    ? actionNames[state.recommendation]
    : (language === "zh" ? "本局已结算" : "Hand settled");
  $("#blackjackAiPlay").disabled = state.phase !== "player_turn";
  $("#blackjackHeadline").textContent = state.phase === "player_turn"
    ? (language === "zh" ? "根据手牌与庄家明牌做决定" : "Decide from your hand and the dealer upcard")
    : (language === "zh" ? "庄家底牌与最终结果已经揭晓" : "The dealer hole card and result are revealed");
  $("#blackjackHistory").innerHTML = state.history.length ? state.history.map((item) => {
    if (item.actor === "dealer") return `<div><b>${language === "zh" ? "庄家" : "Dealer"}</b><span>${language === "zh" ? "要牌" : "hits"} ${item.card} → ${item.total}</span></div>`;
    return `<div><b>${item.actor === "ai" ? "AI" : (language === "zh" ? "你" : "You")}</b><span>${actionNames[item.action]} · ${item.matched ? (language === "zh" ? "符合基础策略" : "matched basic strategy") : `${language === "zh" ? "建议" : "advice"}: ${actionNames[item.recommended]}`}</span></div>`;
  }).join("") : `<p>${language === "zh" ? "尚无决策记录。" : "No decisions yet."}</p>`;
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
  if (state.phase === "finished") {
    $("#rpsCards").innerHTML += `<button class="rps-new-match" data-rps-new>${language === "zh" ? "重新洗牌" : "New match"}</button>`;
    $("[data-rps-new]").addEventListener("click", () => act("new_match"));
  }
}

function probabilityBars(distribution, labels) {
  return Object.entries(distribution).map(([move, probability]) => `<div class="probability-row"><span>${labels[move]}</span><i><b style="width:${(probability * 100).toFixed(1)}%"></b></i><strong>${(probability * 100).toFixed(1)}%</strong></div>`).join("");
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
    $("#liarQuantity").min = state.minimumBid.quantity;
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

function renderBattleGrid(selector, cells, isEnemy, state) {
  const suggested = state.suggestedShot?.join(",");
  $(selector).style.gridTemplateColumns = `repeat(${state.boardSize}, 1fr)`;
  $(selector).style.minWidth = `${state.boardSize * 30 + (state.boardSize - 1) * 2}px`;
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
  $("#battleTurn").textContent = state.turn;
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
    ? "选择海域规模；每种颜色是一艘舰船。点击下方舰船卡旋转 90°，也可以整体随机布阵。"
    : "Choose a sea size; every color is one ship. Rotate individual ship cards 90°, or randomize the full fleet.";
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
      : (language === "zh" ? `第 ${state.turn + 1} 回合：选择攻击坐标` : `Turn ${state.turn + 1}: choose a target`);
  $("#battleInstruction").textContent = state.phase === "placement"
    ? (language === "zh" ? "查看自己的舰船位置；点击确认后布阵将锁定。" : "Review your ship positions. Locking the fleet makes the layout final.")
    : state.phase === "finished"
      ? (language === "zh" ? "敌方完整布阵已经揭示，可以对照交火记录复盘。" : "The complete enemy fleet is now revealed for review.")
      : (language === "zh" ? "点击敌方未知格开火；AI 会依据概率热力图立即还击。" : "Fire at an unknown enemy cell; the probability AI immediately returns fire.");

  const info = state.informationSet;
  $("#battleInformation").textContent = language === "zh"
    ? `敌方仍有 ${info.remainingShipLengths.length} 艘船；${info.unresolvedHits.length} 个命中尚未归入已击沉舰船。当前枚举到 ${info.candidatePlacementCount} 个合法单舰部署。`
    : `${info.remainingShipLengths.length} enemy ships remain; ${info.unresolvedHits.length} hits are unresolved. The model counts ${info.candidatePlacementCount} legal single-ship placements.`;
  $("#battleAiAnalysis").textContent = state.lastAiAnalysis
    ? (language === "zh"
      ? `AI 上一炮选择 ${battleCoordinate(state.lastAiAnalysis.chosenCell)}：该格被 ${state.lastAiAnalysis.peakDensity} 个候选部署覆盖，并列最佳格共有 ${state.lastAiAnalysis.tiedBestCells} 个。`
      : `The AI chose ${battleCoordinate(state.lastAiAnalysis.chosenCell)}: ${state.lastAiAnalysis.peakDensity} candidate placements covered it, with ${state.lastAiAnalysis.tiedBestCells} cells tied for best.`)
    : (language === "zh" ? "开战后，这里会解释 AI 为什么选择上一炮。" : "After battle starts, this panel explains the AI's previous shot.");

  $("#battleHistory").innerHTML = state.history.length ? state.history.slice().reverse().map((item) => {
    const player = item.playerShot;
    const ai = item.aiShot;
    const resultLabel = (shot) => shot.sunk ? (language === "zh" ? `击沉长度 ${shot.sunkLength}` : `sank length ${shot.sunkLength}`) : shot.hit ? (language === "zh" ? "命中" : "hit") : (language === "zh" ? "落空" : "miss");
    return `<div><strong>${language === "zh" ? `回合 ${item.turn}` : `Turn ${item.turn}`}</strong><span>${language === "zh" ? "你" : "You"} ${battleCoordinate(player.cell)} · ${resultLabel(player)}</span>${ai ? `<span>AI ${battleCoordinate(ai.cell)} · ${resultLabel(ai)}</span>` : ""}</div>`;
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
  if (activeOperation) activeOperation.abort();
  activeOperation = null;
  actionPending = false;
  document.querySelector("main").removeAttribute("aria-busy");
  if (openRulesGameId) closeRules();
  $("#offerModal").classList.add("hidden");
  $("#gameView").classList.add("hidden");
  $("#wormView").classList.add("hidden");
  $("#pirateView").classList.add("hidden");
  $("#pokerView").classList.add("hidden");
  $("#eCardView").classList.add("hidden");
  $("#rpsView").classList.add("hidden");
  $("#liarView").classList.add("hidden");
  $("#mastermindView").classList.add("hidden");
  $("#battleshipView").classList.add("hidden");
  $("#blackjackView").classList.add("hidden");
  $("#lobbyView").classList.remove("hidden");
  window.scrollTo(0, 0);
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
$("#newRpsMatch").addEventListener("click", () => startGame("restricted-rps"));
$("#newLiarMatch").addEventListener("click", () => startGame("liars-dice"));
$("#newBlackjackMatch").addEventListener("click", () => startGame("blackjack"));
$("#newBattleshipMatch").addEventListener("click", () => startGame("battleship"));
$("#battleRandomize").addEventListener("click", () => act("randomize_fleet"));
$("#battleStart").addEventListener("click", () => act("start_battle"));
$("#battleBoardSize").addEventListener("change", (event) => act("set_board_size", { boardSize: Number(event.target.value) }));
$("#blackjackAiPlay").addEventListener("click", () => act("ai_play"));
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
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && openRulesGameId) closeRules(); });
applyLanguage();
loadLobby().catch((error) => showToast(error.message));
