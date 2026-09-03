import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { scaffoldStatus } from "../src/popup.js";

test("manifest and module are usable", () => {
  const manifest = JSON.parse(fs.readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
  assert.equal(manifest.manifest_version, 3);
  assert.equal(manifest.action.default_popup, "popup.html");
  assert.equal(scaffoldStatus(), "browser extension scaffold ready");
});
