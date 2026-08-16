import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const staticRoot = resolve(root, "src/aip/ui/static");
const runtime = await readFile(resolve(here, "worker-runtime.js"), "utf8");
const goofspielPolicy = await readFile(resolve(here, "goofspiel-policy.json"), "utf8");
const [html, css, app] = await Promise.all([
  readFile(resolve(staticRoot, "index.html"), "utf8"),
  readFile(resolve(staticRoot, "styles.css"), "utf8"),
  readFile(resolve(staticRoot, "app.js"), "utf8"),
]);

const output = [
  `const GOOFSPIEL_POLICY = ${goofspielPolicy.trim()};`,
  `const INDEX_HTML = ${JSON.stringify(html)};`,
  `const STYLES_CSS = ${JSON.stringify(css)};`,
  `const APP_JS = ${JSON.stringify(app)};`,
  runtime,
].join("\n");

await mkdir(resolve(here, "dist/server"), { recursive: true });
await writeFile(resolve(here, "dist/server/index.js"), output);
console.log("Built dist/server/index.js");
