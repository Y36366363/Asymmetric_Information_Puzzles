import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const source = resolve(root, "src/aip/ui/static");
const output = resolve(root, "docs");

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });

const runtime = await readFile(resolve(here, "worker-runtime.js"), "utf8");
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
      return json({ status: "ok", service: "aip-static-browser" });
    }
    if (method === "GET" && target.pathname === "/api/games") return json({ games: GAMES });
    if (method === "POST" && target.pathname === "/api/sessions") {
      const body = JSON.parse(String(init.body || "{}"));
      const session = createSession(body.gameId, body.options || {});
      const sessionId = crypto.randomUUID();
      sessions.set(sessionId, session);
      return json({ sessionId, state: session.snapshot() }, 201);
    }
    const match = target.pathname.match(/^\\/api\\/sessions\\/([^/]+)\\/actions$/);
    if (method === "POST" && match) {
      const session = sessions.get(match[1]);
      if (!session) throw new Error("unknown or expired session; restart the game");
      const body = JSON.parse(String(init.body || "{}"));
      session.act(body.action, body.payload || {});
      return json({ state: session.snapshot() });
    }
    return json({ error: "not found" }, 404);
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : "operation failed" }, 400);
  }
};
`;

const index = (await readFile(resolve(source, "index.html"), "utf8"))
  .replace('<script src="app.js"></script>', '<script type="module" src="bootstrap.js"></script>');

await Promise.all([
  writeFile(resolve(output, "index.html"), index),
  copyFile(resolve(source, "styles.css"), resolve(output, "styles.css")),
  copyFile(resolve(source, "app.js"), resolve(output, "app.js")),
  writeFile(resolve(output, "game-engine.js"), runtime.slice(0, apiBoundary) + browserAdapter),
  writeFile(resolve(output, "bootstrap.js"), 'import "./game-engine.js";\nimport "./app.js";\n'),
  writeFile(resolve(output, ".nojekyll"), ""),
]);

console.log("Built the zero-backend static lobby in docs/");
