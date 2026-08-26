import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const source = resolve(root, "src/aip/ui/static");
const output = resolve(root, "docs");

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });

const [runtime, app, styles] = await Promise.all([
  readFile(resolve(here, "worker-runtime.js"), "utf8"),
  readFile(resolve(source, "app.js"), "utf8"),
  readFile(resolve(source, "styles.css"), "utf8"),
]);
const goofspielPolicy = await readFile(resolve(here, "goofspiel-policy.json"), "utf8");
const version = createHash("sha256")
  .update(runtime)
  .update(app)
  .update(styles)
  .digest("hex")
  .slice(0, 12);
const apiBoundary = runtime.indexOf("async function api(request, url)");
if (apiBoundary < 0) throw new Error("Unable to locate the shared game engine boundary");

const browserAdapter = `
const networkFetch = globalThis.fetch.bind(globalThis);

globalThis.fetch = async (input, init = {}) => {
  const target = new URL(typeof input === "string" ? input : input.url, globalThis.location.href);
  if (!target.pathname.startsWith("/api/")) return networkFetch(input, init);

  try {
    const method = String(init.method || (typeof input === "string" ? "GET" : input.method) || "GET").toUpperCase();
    if (method === "GET" && target.pathname === "/api/health") {
      return json({ status: "ok", service: "aip-static-browser", apiVersion: 2 });
    }
    if (method === "GET" && target.pathname === "/api/games") return json({ games: GAMES });
    if (method === "POST" && target.pathname === "/api/sessions") {
      const body = JSON.parse(String(init.body || "{}"));
      const session = createSession(body.gameId, body.options || {});
      const sessionId = crypto.randomUUID();
      const state = validateState(session.snapshot(), body.gameId);
      storeSession(sessionId, session);
      return json({ sessionId, state }, 201);
    }
    const match = target.pathname.match(/^\\/api\\/sessions\\/([^/]+)\\/actions$/);
    if (method === "POST" && match) {
      const session = sessions.get(match[1]);
      if (!session) throw new Error("unknown or expired session; restart the game");
      sessions.delete(match[1]);
      sessions.set(match[1], session);
      const body = JSON.parse(String(init.body || "{}"));
      requireLegalAction(session, body.action);
      session.act(body.action, body.payload || {});
      return json({ state: validateState(session.snapshot(), session.gameId) });
    }
    return json({ error: "not found" }, 404);
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : "operation failed" }, 400);
  }
};
`;

const index = (await readFile(resolve(source, "index.html"), "utf8"))
  .replace('href="styles.css"', `href="styles.css?v=${version}"`)
  .replace('<script src="app.js"></script>', `<script type="module" src="bootstrap.js?v=${version}"></script>`);

await Promise.all([
  writeFile(resolve(output, "index.html"), index),
  writeFile(resolve(output, "styles.css"), styles),
  writeFile(resolve(output, "app.js"), app),
  writeFile(resolve(output, "game-engine.js"), `const GOOFSPIEL_POLICY = ${goofspielPolicy.trim()};\n` + runtime.slice(0, apiBoundary) + browserAdapter),
  writeFile(resolve(output, "bootstrap.js"), `import "./game-engine.js?v=${version}";\nimport "./app.js?v=${version}";\n`),
  writeFile(resolve(output, ".nojekyll"), ""),
]);

console.log(`Built the zero-backend static lobby in docs/ (${version})`);
