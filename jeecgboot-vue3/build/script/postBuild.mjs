import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const mode = process.env.NODE_ENV || "production";
const outputDir = resolve(root, "dist");
const outputFile = resolve(outputDir, "_app.config.js");

function readEnvFile(fileName) {
  const filePath = resolve(root, fileName);
  if (!existsSync(filePath)) return {};

  return readFileSync(filePath, "utf8").split(/\r?\n/).reduce((values, rawLine) => {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) return values;
    const separator = line.indexOf("=");
    if (separator < 1) return values;

    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    values[key] = value;
    return values;
  }, {});
}

const allEnv = {
  ...readEnvFile(".env"),
  ...readEnvFile(`.env.${mode}`),
};
const runtimeConfig = Object.fromEntries(
  Object.entries(allEnv).filter(([key]) => key.startsWith("VITE_GLOB_")),
);
const configName = `__PRODUCTION__${runtimeConfig.VITE_GLOB_APP_SHORT_NAME || "__APP"}__CONF__`
  .toUpperCase()
  .replace(/\s/g, "");
const content = `window.${configName}=${JSON.stringify(runtimeConfig)};Object.freeze(window.${configName});Object.defineProperty(window,"${configName}",{configurable:false,writable:false});`;

mkdirSync(outputDir, { recursive: true });
writeFileSync(outputFile, content, "utf8");
console.log(`Runtime configuration written to dist/_app.config.js for ${mode}.`);
