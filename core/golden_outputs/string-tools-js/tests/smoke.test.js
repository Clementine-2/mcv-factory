import test from "node:test";
import assert from "node:assert/strict";
import { VERSION, scaffoldStatus } from "../src/index.js";

test("library imports", () => {
  assert.equal(VERSION, "0.1.0");
  assert.equal(scaffoldStatus(), "node library scaffold ready");
});
