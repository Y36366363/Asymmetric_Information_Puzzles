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
  assert.equal(games.filter((game) => game.available).length, 8);
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
  for (const gameId of ["cases", "kuhn-poker", "e-card", "restricted-rps", "blackjack", "liars-dice"]) {
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
