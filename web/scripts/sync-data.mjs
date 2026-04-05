import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const src = join(root, "data", "prompts.json");
const destDir = join(fileURLToPath(new URL(".", import.meta.url)), "..", "public");
const dest = join(destDir, "prompts.json");

mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log("Synced data/prompts.json -> web/public/prompts.json");
