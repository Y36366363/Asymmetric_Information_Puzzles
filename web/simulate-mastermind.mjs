import { performance } from "node:perf_hooks";

const worker = (await import("./dist/server/index.js")).default;
const sampleSize = Math.max(1, Number.parseInt(process.argv[2] || "200", 10));
const distribution = new Map();
let totalAttempts = 0;
let failures = 0;
const started = performance.now();

for (let index = 0; index < sampleSize; index += 1) {
  const createResponse = await worker.fetch(new Request("https://aip.test/api/sessions", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ gameId: "mastermind" }),
  }));
  let session = await createResponse.json();
  while (session.state.phase === "playing") {
    const response = await worker.fetch(new Request(
      `https://aip.test/api/sessions/${session.sessionId}/actions`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "submit_guess",
          payload: { guess: session.state.suggestedGuess },
        }),
      },
    ));
    session.state = (await response.json()).state;
  }
  const attempts = session.state.result.attempts;
  totalAttempts += attempts;
  distribution.set(attempts, (distribution.get(attempts) || 0) + 1);
  if (!session.state.result.won) failures += 1;
}

console.log(JSON.stringify({
  sampleSize,
  averageAttempts: totalAttempts / sampleSize,
  failures,
  maximumAttempts: Math.max(...distribution.keys()),
  distribution: Object.fromEntries([...distribution].sort(([a], [b]) => a - b)),
  elapsedSeconds: (performance.now() - started) / 1000,
}, null, 2));
