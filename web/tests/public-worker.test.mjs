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
  assert.equal(games.filter((game) => game.available).length, 15);
  assert.deepEqual(games.filter((game) => game.available).map((game) => game.id), ["cases", "blackjack", "restricted-rps", "mastermind", "guess-who", "hidden-pursuit", "battleship", "e-card", "pirates", "love-letter", "investment", "kuhn-poker", "liars-dice", "goofspiel", "worm"]);
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
  const twoHoleWorm = await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"worm",options:{holes:2}})});
  assert.equal(twoHoleWorm.status, 201);
  assert.deepEqual((await twoHoleWorm.json()).state.strategy, [1,1]);
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

test("temporary session storage stays bounded and expires the oldest game", async () => {
  const first = await (await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"worm"})})).json();
  let refreshed;
  for (let index=0; index<256; index+=1) {
    const response = await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"worm"})});
    assert.equal(response.status, 201);
    const created = await response.json();
    if (index===0) refreshed=created;
  }
  const expired = await call(`/api/sessions/${first.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"check_hole",payload:{holeId:2}})});
  assert.equal(expired.status, 400);
  assert.match((await expired.json()).error, /expired/);
  const keepActive = await call(`/api/sessions/${refreshed.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"check_hole",payload:{holeId:2}})});
  assert.equal(keepActive.status, 200);
  await call("/api/sessions", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({gameId:"worm"})});
  const stillActive = await call(`/api/sessions/${refreshed.sessionId}/actions`, {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:"check_hole",payload:{holeId:3}})});
  assert.equal(stillActive.status, 200);
});

test("every public game creates a playable state", async () => {
  const listed = await (await call("/api/games")).json();
  for (const gameId of listed.games.filter((game) => game.available).map((game) => game.id)) {
    const response = await call("/api/sessions", {
      method:"POST", headers:{"content-type":"application/json"},
      body:JSON.stringify({gameId}),
    });
    assert.equal(response.status, 201, gameId);
    const created = await response.json();
    assert.equal(created.state.gameId, gameId);
    assert.equal(typeof created.state.phase, "string");
    assert.ok(Array.isArray(created.state.legalActions));
    assert.equal(new Set(created.state.legalActions).size, created.state.legalActions.length);
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

  const guessWho = await create("guess-who");
  assert.equal(guessWho.state.informationSet.possibleCount, 24);
  assert.equal(guessWho.state.characters.some((character) => character.secret), false);
  assert.deepEqual([guessWho.state.suggestion.yesCount, guessWho.state.suggestion.noCount], [12,12]);
  while (guessWho.state.phase === "playing") {
    if (guessWho.state.suggestion.type === "question") {
      await act(guessWho, "ask_question", {questionId:guessWho.state.suggestion.questionId});
    } else {
      await act(guessWho, "guess_character", {name:guessWho.state.suggestion.character});
    }
  }
  assert.equal(guessWho.state.result.won, true);
  assert.ok(guessWho.state.turnsUsed <= 6);
  assert.equal(guessWho.state.informationSet.possibleCount, 1);

  const ecard = await create("e-card");
  while (ecard.state.phase === "playing") await act(ecard, "play_card", {card:ecard.state.playerHand[0].card});
  assert.ok(ecard.state.result);

  const poker = await create("kuhn-poker");
  assert.equal(poker.state.strategyScope, "exact_three_card_kuhn_equilibrium_alpha_one_third");
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

  const pursuit = await create("hidden-pursuit");
  assert.equal(pursuit.state.fugitivePosition, null);
  assert.equal(pursuit.state.belief.length, 16);
  while (pursuit.state.phase !== "finished") {
    await act(pursuit, "move_detective", {node:pursuit.state.legalMoves[0]});
  }
  assert.ok(["detectives", "fugitive"].includes(pursuit.state.winner));
  assert.ok(Number.isInteger(pursuit.state.fugitivePosition));

  const love = await create("love-letter");
  assert.equal(love.state.opponentHand, null);
  assert.equal(love.state.informationSet.knownOpponentCard, null);
  for (let guard=0; love.state.phase !== "match_finished" && guard < 100; guard += 1) {
    if (love.state.phase === "round_finished") await act(love, "next_round");
    else await act(love, "play_card", love.state.suggestedPlay);
  }
  assert.equal(love.state.phase, "match_finished");
  assert.ok([love.state.scores.player, love.state.scores.ai].includes(4));
  assert.ok(Array.isArray(love.state.opponentHand));

  const investment = await create("investment");
  while (investment.state.phase === "decision") {
    await act(investment, "invest", {offerId:investment.state.suggestion.offerId,fraction:.25});
  }
  assert.ok(investment.state.winner || !investment.state.rankings.find((item) => item.id === "player").alive);
  assert.ok(investment.state.rankings.some((item) => !item.alive));

  const goofspiel = await create("goofspiel");
  assert.equal(goofspiel.state.strategyScope, "exact four-card shuffled-prize zero-sum equilibrium");
  assert.equal(goofspiel.state.informationSet.aiCurrentBidHidden, true);
  while (goofspiel.state.phase === "bidding") {
    const totalProbability = goofspiel.state.advisorDistribution.reduce((sum, item) => sum + item.probability, 0);
    assert.ok(Math.abs(totalProbability - 1) < 1e-9);
    await act(goofspiel, "bid", {card:goofspiel.state.recommendedBid});
  }
  assert.equal(goofspiel.state.history.length, 4);
  assert.equal(goofspiel.state.playerCards.length, 0);
  assert.ok(["player", "ai", "tie"].includes(goofspiel.state.winner));

  const expanded = await create("battleship");
  await act(expanded, "set_board_size", {boardSize:12});
  assert.equal(expanded.state.playerBoard.length, 144);
  assert.equal(expanded.state.fleet.length, 6);
  const orientation = expanded.state.fleet[0].orientation;
  await act(expanded, "rotate_ship", {shipId:0});
  assert.notEqual(expanded.state.fleet[0].orientation, orientation);

  const grand = await create("battleship");
  await act(grand, "set_board_size", {boardSize:15});
  await act(grand, "start_battle");
  while (grand.state.phase === "player_turn") {
    const [row, column] = grand.state.suggestedShot;
    await act(grand, "fire", {row,column});
  }
  assert.ok(["player","ai"].includes(grand.state.winner));
  assert.ok(grand.state.turn <= 225);
});
