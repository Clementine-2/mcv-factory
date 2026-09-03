import fs from "node:fs";
const manifest = JSON.parse(fs.readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
if (manifest.manifest_version !== 3 || !manifest.action?.default_popup) process.exit(2);
console.log("manifest ok");
