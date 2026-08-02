const $ = (selector) => document.querySelector(selector);
const money = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });
let sessionId = null;
let currentState = null;
let currentGameId = null;

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "操作失败");
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
  $("#gameGrid").innerHTML = games.map((game, index) => `
    <button class="game-card" data-game="${game.id}" ${game.available ? "" : "disabled"}>
      <span class="game-index">0${index + 1}</span>
      <h2>${game.title}</h2>
      <p>${game.summary}</p>
      <span class="game-mode">${game.playerMode}</span>
    </button>
  `).join("");
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
    $("#lobbyView").classList.add("hidden");
    $("#gameView").classList.toggle("hidden", gameId !== "cases");
    $("#wormView").classList.toggle("hidden", gameId !== "worm");
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
  if (currentState.gameId === "worm") {
    renderWorm();
    return;
  }
  const state = currentState;
  $("#roundNumber").textContent = state.phase === "choose" ? "—" : state.round;
  $("#remainingCount").textContent = state.prizeBoard.filter((prize) => prize.remaining).length;
  const instructions = {
    choose: "请选择一个属于你的密封箱",
    opening: `再打开 ${state.opensRemaining} 个箱子，银行家随后报价`,
    offer: "银行家正在等待你的决定",
    finished: `本局结束 · 你获得 ${formatMoney(state.payout)}`,
  };
  $("#instruction").textContent = instructions[state.phase];
  $("#chosenStrip").textContent = state.chosenCase
    ? `你的密封箱：${state.chosenCase} 号${state.phase === "finished" ? ` · ${formatMoney(findCase(state.chosenCase).value)}` : ""}`
    : "你的箱子尚未选择";

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
    $("#offerContext").textContent = `剩余 ${state.prizeBoard.filter((prize) => prize.remaining).length} 个可能金额。模型保留价为 ${formatMoney(state.metrics.certaintyEquivalent)}。`;
  }
}

function renderWorm() {
  const state = currentState;
  $("#wormMode").textContent = state.mode === "adversarial" ? "对抗" : "随机";
  $("#wormModeAdversarial").classList.toggle("active", state.mode === "adversarial");
  $("#wormModeRandom").classList.toggle("active", state.mode === "random");
  $("#wormTurn").textContent = state.turn;
  $("#possibleHoles").textContent = state.possiblePositions.join(" · ") || "已锁定";
  $("#wormHint").textContent = state.phase === "finished"
    ? "已成功抓捕"
    : state.suggestedHole
      ? `检查 ${state.suggestedHole} 号洞`
      : state.followedStrategy ? "序列已完成" : "已偏离保证序列";
  $("#wormHeadline").textContent = state.phase === "finished"
    ? `抓到了！第 ${state.turn} 次检查成功`
    : "虫子仍在移动";
  $("#wormInstruction").textContent = state.phase === "finished"
    ? "重新开始可以更换虫子的初始位置。"
    : state.mode === "adversarial"
      ? "系统会选择所有合法轨迹中最难抓的一条；只能靠保证策略取胜。"
      : "虫子从一个随机位置出发，每次失手后随机移动到相邻洞。";

  $("#holeRow").innerHTML = state.holes.map((hole) => `
    <button class="hole ${hole.possible ? "" : "impossible"} ${hole.worm ? "worm-found" : ""}"
      data-hole="${hole.id}" ${state.phase === "finished" ? "disabled" : ""}
      aria-label="检查 ${hole.id} 号洞">${hole.worm ? "●" : hole.id}</button>
  `).join("");
  document.querySelectorAll(".hole:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => act("check_hole", { holeId: Number(button.dataset.hole) }));
  });

  $("#strategySequence").innerHTML = state.strategy.map((hole, index) => {
    const status = index < state.turn ? "done" : index === state.turn && state.followedStrategy ? "next" : "";
    return `<span class="strategy-step ${status}">${hole}</span>`;
  }).join("");
  $("#wormHistory").innerHTML = state.history.slice().reverse().map((item) =>
    `<li>第 ${item.turn} 次检查 ${item.holeId} 号洞：${item.result === "caught"
      ? item.guaranteed ? "所有轨迹均被封锁，保证抓到" : "成功抓到"
      : state.mode === "adversarial" ? "对手仍有逃脱轨迹" : "没有，虫子已移动"}</li>`
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
  $("#metrics").innerHTML = `
    <div class="metric"><span>剩余期望值</span><strong>${formatMoney(metrics.expectedValue)}</strong></div>
    <div class="metric"><span>确定性等价</span><strong>${formatMoney(metrics.certaintyEquivalent)}</strong></div>
    <div class="metric"><span>报价 / 期望值</span><strong>${(metrics.offerRatio * 100).toFixed(1)}%</strong></div>
    <div class="metric"><span>箱内金额超过报价</span><strong>${(metrics.chanceToBeatOffer * 100).toFixed(1)}%</strong></div>
    <div class="metric"><span>剩余波动</span><strong>${formatMoney(metrics.standardDeviation)}</strong></div>
    <div class="recommendation">模型建议：${metrics.reservationRecommendation === "deal" ? "接受报价" : "继续开箱"}</div>
  `;
}

function renderHistory(history) {
  const labels = {
    choose: (item) => `选择 ${item.caseId} 号作为自己的箱子`,
    reveal: (item) => `打开 ${item.caseId} 号：${formatMoney(item.value)}`,
    offer: (item) => `第 ${item.round} 轮报价：${formatMoney(item.value)}`,
    deal: (item) => `接受报价：${formatMoney(item.value)}`,
    no_deal: (item) => `第 ${item.round} 轮拒绝报价`,
    case_payout: (item) => `坚持到底：箱内为 ${formatMoney(item.value)}`,
  };
  $("#historyList").innerHTML = history.slice().reverse().map((item) =>
    `<li>${labels[item.kind](item)}</li>`
  ).join("");
}

function formatMoney(value) {
  return `¥${money.format(value ?? 0)}`;
}

function findCase(caseId) {
  return currentState.cases.find((item) => item.id === caseId);
}

function showLobby() {
  $("#offerModal").classList.add("hidden");
  $("#gameView").classList.add("hidden");
  $("#wormView").classList.add("hidden");
  $("#lobbyView").classList.remove("hidden");
}

$("#homeButton").addEventListener("click", showLobby);
$("#backButton").addEventListener("click", showLobby);
document.querySelectorAll(".back-to-lobby").forEach((button) => button.addEventListener("click", showLobby));
$("#newGameButton").addEventListener("click", () => startGame("cases"));
$("#newWormButton").addEventListener("click", () => startGame("worm", { mode: currentState?.mode || "adversarial" }));
$("#wormModeAdversarial").addEventListener("click", () => startGame("worm", { mode: "adversarial" }));
$("#wormModeRandom").addEventListener("click", () => startGame("worm", { mode: "random" }));
$("#dealButton").addEventListener("click", () => act("deal"));
$("#noDealButton").addEventListener("click", () => act("no_deal"));
loadLobby().catch((error) => showToast(error.message));
