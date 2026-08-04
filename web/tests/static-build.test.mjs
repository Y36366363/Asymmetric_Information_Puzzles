import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const publicRoot = new URL("../../docs/", import.meta.url);

test("static lobby boots the browser engine before the UI", async () => {
  const html = await readFile(new URL("index.html", publicRoot), "utf8");
  const bootstrap = await readFile(new URL("bootstrap.js", publicRoot), "utf8");
  assert.match(html, /type="module" src="bootstrap\.js"/);
  assert.doesNotMatch(html, /<script src="app\.js"><\/script>/);
  assert.ok(bootstrap.indexOf("game-engine.js") < bootstrap.indexOf("app.js"));
});

test("browser engine intercepts API calls without a backend", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.location = new URL("https://example.test/Asymmetric_Information_Puzzles/");
  await import(`../../docs/game-engine.js?test=${Date.now()}`);
  try {
    const games = await (await fetch("/api/games")).json();
    assert.equal(games.games.filter((game) => game.available).length, 8);
    const created = await (await fetch("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ gameId: "pirates", options: { pirates: 5, gold: 100 } }),
    })).json();
    assert.equal(created.state.gameId, "pirates");
    assert.ok(created.sessionId);
    const liar = await (await fetch("/api/sessions", { method: "POST", body: JSON.stringify({ gameId: "liars-dice" }) })).json();
    assert.equal(liar.state.gameId, "liars-dice");
    assert.deepEqual(liar.state.playerDice.length, 5);
  } finally {
    globalThis.fetch = originalFetch;
    delete globalThis.location;
  }
});
