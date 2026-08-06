import assert from "node:assert/strict";
import test from "node:test";

const worker = (await import("../dist/server/index.js")).default;
const call = (path, init) => worker.fetch(new Request(`https://aip.test${path}`, init));

test("serves the bilingual lobby and all playable descriptors", async () => {
  const page = await call("/");
  assert.equal(page.status, 200);
  assert.match(await page.text(), /ASYMMETRIC INFORMATION PUZZLES/);
  const response = await call("/api/games");
  const { games } = await response.json();
  assert.equal(games.filter((game) => game.available).length, 10);
  assert.deepEqual(games.filter((game) => game.available).map((game) => game.id), ["cases", "blackjack", "restricted-rps", "mastermind", "battleship", "e-card", "pirates", "kuhn-poker", "liars-dice", "worm"]);
});

test("case game reaches a clear non-null final reveal", async () => {
  const created = await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"cases"})});
  let session = await created.json();
  const sessionId = session.sessionId;
  const act = async (action, payload={}) => {
    const response = await call(`/api/sessions/${sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action,payload})});
    assert.equal(response.status, 200, action);
    session.state = (await response.json()).state;
  };
  await act("choose_case", {caseId:1});
  for (let guard=0; session.state.phase !== "finished" && guard < 50; guard += 1) {
    if (session.state.phase === "opening") {
      const next = session.state.cases.find((item) => item.status === "closed");
      assert.ok(next, "opening phase must always expose a legal case");
      await act("open_case", {caseId:next.id});
    } else {
      if (session.state.isFinalOffer) assert.equal(session.state.prizeBoard.filter((item) => item.remaining).length, 1);
      await act("no_deal");
    }
  }
  assert.equal(session.state.phase, "finished");
  assert.equal(session.state.result.kind, "kept_case");
  assert.equal(typeof session.state.payout, "number");
  assert.equal(session.state.cases.find((item) => item.id === 1).value, session.state.payout);
});

test("creates a pirate session and completes a rational vote", async () => {
  const created = await call("/api/sessions", {
    method: "POST", headers: {"content-type":"application/json"},
    body: JSON.stringify({gameId:"pirates", options:{pirates:5,gold:100}}),
  });
  const session = await created.json();
  assert.equal(session.state.gameId, "pirates");
  const allocation = session.state.pirates.map((_, index) => index === 0 ? 98 : [2,4].includes(index) ? 1 : 0);
  const voted = await call(`/api/sessions/${session.sessionId}/actions`, {
    method:"POST", headers:{"content-type":"application/json"},
    body:JSON.stringify({action:"submit_proposal",payload:{allocation}}),
  });
  const result = await voted.json();
  assert.equal(result.state.passed, true);
  assert.equal(result.state.yesVotes, 3);
});

test("rejects malformed options and fractional pirate coins", async () => {
  const invalidWorm = await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"worm",options:{holes:"not-a-number"}})});
  assert.equal(invalidWorm.status, 400);
  const created = await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"pirates",options:{pirates:5,gold:100}})});
  const session = await created.json();
  const fractional = await call(`/api/sessions/${session.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"submit_proposal",payload:{allocation:[97.5,1.5,1,0,0]}})});
  assert.equal(fractional.status, 400);
  const worm = await (await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"worm",options:{holes:5}})})).json();
  const fractionalHole = await call(`/api/sessions/${worm.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"check_hole",payload:{holeId:2.5}})});
  assert.equal(fractionalHole.status, 400);
  const liar = await (await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"liars-dice",options:{dice:5}})})).json();
  const fractionalBid = await call(`/api/sessions/${liar.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"raise_bid",payload:{quantity:1.5,face:2}})});
  assert.equal(fractionalBid.status, 400);
  const mastermind = await (await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"mastermind"})})).json();
  const repeatedCode = await call(`/api/sessions/${mastermind.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"submit_guess",payload:{guess:[0,1,1,2]}})});
  assert.equal(repeatedCode.status, 400);
});

test("worm capture stays adversarial until the belief state is a singleton", async () => {
  const created = await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"worm"})});
  let session = await created.json();
  for (const holeId of session.state.strategy) {
    const response = await call(`/api/sessions/${session.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"check_hole",payload:{holeId}})});
    session.state = (await response.json()).state;
    if (session.state.phase === "finished") break;
  }
  assert.equal(session.state.phase, "finished");
});

test("every public game creates a playable state", async () => {
  for (const gameId of ["cases", "kuhn-poker", "e-card", "restricted-rps", "blackjack", "liars-dice", "mastermind", "battleship"]) {
    const response = await call("/api/sessions", {
      method:"POST", headers:{"content-type":"application/json"},
      body:JSON.stringify({gameId}),
    });
    assert.equal(response.status, 201, gameId);
    const created = await response.json();
    assert.equal(created.state.gameId, gameId);
    assert.ok(created.sessionId);
  }
});

test("single-player games survive complete decision loops", async () => {
  const create = async (gameId) => (await (await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId})})).json());
  const act = async (session, action, payload={}) => {
    const response = await call(`/api/sessions/${session.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action,payload})});
    assert.equal(response.status, 200, `${session.state.gameId}:${action}`);
    session.state = (await response.json()).state;
  };

  const blackjack = await create("blackjack");
  if (blackjack.state.phase === "player_turn") await act(blackjack, "stand");
  assert.equal(blackjack.state.phase, "finished");

  const rps = await create("restricted-rps");
  while (rps.state.phase === "playing") {
    const move = Object.keys(rps.state.playerInventory).find((key) => rps.state.playerInventory[key] > 0);
    await act(rps, "play_move", {move});
  }
  assert.equal(rps.state.roundNumber, rps.state.roundsTotal);

  const mastermind = await create("mastermind");
  assert.equal(mastermind.state.candidateCount, 5040);
  assert.deepEqual(mastermind.state.suggestedGuess, [0,1,2,3]);
  while (mastermind.state.phase === "playing") await act(mastermind, "submit_guess", {guess:mastermind.state.suggestedGuess});
  assert.equal(mastermind.state.result.won, true);
  assert.ok(mastermind.state.attempts.every((item) => item.beforeCandidates-item.afterCandidates===item.eliminated));
  const solvedAttempts = mastermind.state.result.attempts;
  await act(mastermind, "new_game");
  assert.equal(mastermind.state.candidateCount, 5040);
  assert.equal(mastermind.state.sessionStats.averageSolvedAttempts, solvedAttempts);

  const ecard = await create("e-card");
  while (ecard.state.phase === "playing") await act(ecard, "play_card", {card:ecard.state.playerHand[0].card});
  assert.ok(ecard.state.result);

  const poker = await create("kuhn-poker");
  for (let guard=0; poker.state.phase === "playing" && guard < 4; guard += 1) {
    const action = poker.state.legalActions.includes("check") ? "check" : poker.state.legalActions.includes("call") ? "call" : poker.state.legalActions[0];
    await act(poker, action);
  }
  assert.equal(poker.state.phase, "finished");

  const liar = await create("liars-dice");
  await act(liar, "raise_bid", {quantity:1,face:1});
  if (liar.state.phase === "bidding") await act(liar, "challenge");
  assert.equal(liar.state.phase, "finished");

  const battleship = await create("battleship");
  assert.equal(battleship.state.enemyBoard.some((cell) => cell.ship), false);
  await act(battleship, "start_battle");
  while (battleship.state.phase === "player_turn") {
    const [row, column] = battleship.state.suggestedShot;
    await act(battleship, "fire", {row, column});
  }
  assert.ok(["player", "ai"].includes(battleship.state.winner));
  assert.ok(battleship.state.enemyBoard.some((cell) => cell.ship));

  const expanded = await create("battleship");
  await act(expanded, "set_board_size", {boardSize:12});
  assert.equal(expanded.state.playerBoard.length, 144);
  assert.equal(expanded.state.fleet.length, 6);
  const orientation = expanded.state.fleet[0].orientation;
  await act(expanded, "rotate_ship", {shipId:0});
  assert.notEqual(expanded.state.fleet[0].orientation, orientation);
});
