import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const publicRoot = new URL("../../docs/", import.meta.url);

test("static lobby boots the browser engine before the UI", async () => {
  const html = await readFile(new URL("index.html", publicRoot), "utf8");
  const bootstrap = await readFile(new URL("bootstrap.js", publicRoot), "utf8");
  assert.match(html, /type="module" src="bootstrap\.js\?v=[a-f0-9]{12}"/);
  assert.match(html, /styles\.css\?v=[a-f0-9]{12}/);
  assert.doesNotMatch(html, /<script src="app\.js"><\/script>/);
  assert.ok(bootstrap.indexOf("game-engine.js") < bootstrap.indexOf("app.js"));
  assert.match(bootstrap, /game-engine\.js\?v=[a-f0-9]{12}/);
  assert.match(bootstrap, /app\.js\?v=[a-f0-9]{12}/);
  assert.match(html, /id="rulesModal"/);
  const app = await readFile(new URL("app.js", publicRoot), "utf8");
  assert.match(app, /installRulesButtons/);
  assert.match(app, /Mastermind/);
  assert.match(app, /先弄懂：你在做什么/);
  assert.match(app, /看一个具体例子/);
  assert.match(app, /页面上的词是什么意思/);
  assert.match(app, /padStart\(2, "0"\)/);
  assert.match(app, /openRulesGameId/);
  assert.match(app, /submitMastermindGuess/);
  assert.match(app, /mastermindUseSuggestion/);
  assert.match(app, /5,040/);
  assert.match(html, /id="mastermindCandidatePreview"/);
  assert.match(app, /event\.key === "Enter"/);
  assert.match(app, /aip-rules-seen-/);
  assert.match(app, /playNow/);
  assert.match(app, /renderBattleship/);
  assert.match(app, /renderHiddenPursuit/);
  assert.match(app, /function renderGuessWho\(\)/);
  assert.match(app, /function renderGoofspiel\(\)/);
  assert.match(html, /id="goofspielView"/);
  assert.match(app, /精确均衡建议/);
  assert.match(app, /不能每次固定选择它/);
  assert.match(app, /highest equilibrium frequency/);
  assert.match(app, /function renderFirstTurnGuide/);
  assert.match(app, /15×15 大海域提示/);
  assert.match(app, /Post-match strategy review/);
  assert.match(html, /id="rpsPostMatch"/);
  assert.match(html, /id="goofPostMatch"/);
  assert.match(app, /aiTarget\.disabled = state\.protected\.ai/);
  assert.match(app, /loveTarget\.value = "player"/);
  assert.match(app, /A wrong guess costs one turn/);
  assert.match(app, /aip-rules-seen-/);
  assert.match(app, /actionPending/);
  assert.match(app, /setOperationPending/);
  assert.match(html, /id="operationStatus"[^>]*aria-live="polite"/);
  assert.match(app, /new AbortController/);
  assert.match(app, /readPreference/);
  assert.match(app, /clearTimeout\(toastTimer\)/);
  assert.match(app, /connectionFailed/);
  assert.match(app, /activeOperation/);
  assert.match(app, /window\.addEventListener\("hashchange"/);
  assert.match(app, /window\.history\.replaceState\(null, "", "#lobby"\)/);
  assert.match(app, /requestAnimationFrame\(\(\) => \$\("#rulesClose"\)\.focus\(\)\)/);
  assert.match(app, /event\.key !== "Tab"/);
  assert.match(html, /id="battleEnemyBoard"/);
  assert.match(html, /id="battleBoardSize"/);
  assert.match(html, /id="pursuitMap"/);
  assert.match(app, /rotate_ship/);
  assert.match(app, /ship-\$\{cell\.shipId\}/);
  assert.match(app, /Submit unlocks when this reaches zero/);
  assert.match(app, /Math\.max\(minimumQuantity/);
  const styles = await readFile(new URL("styles.css", publicRoot), "utf8");
  assert.match(styles, /\.blackjack-actions \{ flex-wrap: wrap; \}/);
  assert.match(styles, /\.game-heading \.back-to-lobby, \.game-heading #backButton \{ min-height: 44px; \}/);
  assert.match(styles, /select:focus-visible/);
  assert.match(styles, /\.first-turn-guide/);
  assert.match(styles, /\.strategy-review-grid/);
});

test("browser engine intercepts API calls without a backend", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.location = new URL("https://example.test/Asymmetric_Information_Puzzles/");
  await import(`../../docs/game-engine.js?test=${Date.now()}`);
  try {
    const games = await (await fetch("/api/games")).json();
    assert.equal(games.games.filter((game) => game.available).length, 15);
    const created = await (await fetch("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ gameId: "pirates", options: { pirates: 5, gold: 100 } }),
    })).json();
    assert.equal(created.state.gameId, "pirates");
    assert.ok(created.sessionId);
    const liar = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "liars-dice" }) })).json();
    assert.equal(liar.state.gameId, "liars-dice");
    assert.deepEqual(liar.state.playerDice.length, 5);
    const mastermind = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "mastermind" }) })).json();
    assert.equal(mastermind.state.gameId, "mastermind");
    assert.equal(mastermind.state.candidateCount, 5040);
    assert.deepEqual(mastermind.state.suggestedGuess, [0, 1, 2, 3]);
    const battleship = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "battleship" }) })).json();
    assert.equal(battleship.state.gameId, "battleship");
    assert.equal(battleship.state.enemyBoard.some((cell) => cell.ship), false);
    const pursuit = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "hidden-pursuit" }) })).json();
    assert.equal(pursuit.state.gameId, "hidden-pursuit");
    assert.equal(pursuit.state.fugitivePosition, null);
    assert.equal(pursuit.state.belief.length, 16);
    const goofspiel = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "goofspiel" }) })).json();
    assert.equal(goofspiel.state.gameId, "goofspiel");
    assert.equal(goofspiel.state.informationSet.aiCurrentBidHidden, true);
    assert.equal(goofspiel.state.advisorDistribution.reduce((sum, item) => sum + item.probability, 0), 1);
    const guessWho = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "guess-who" }) })).json();
    assert.equal(guessWho.state.gameId, "guess-who");
    assert.equal(guessWho.state.informationSet.possibleCount, 24);
    assert.equal(guessWho.state.characters.some((character) => character.secret), false);
    const firstTemporary = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "worm" }) })).json();
    for (let index = 0; index < 256; index += 1) {
      const response = await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "worm" }) });
      assert.equal(response.status, 201);
    }
    const expired = await fetch(`/api/sessions/${firstTemporary.sessionId}/actions`, { method: "POST", body: JSON.stringify({ action: "check_hole", payload: { holeId: 2 } }) });
    assert.equal(expired.status, 400);
  } finally {
    globalThis.fetch = originalFetch;
    delete globalThis.location;
  }
});
