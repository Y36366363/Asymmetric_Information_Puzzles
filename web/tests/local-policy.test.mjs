import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

test("local Love Letter policy is portable JSON but cannot promote the full browser game", async () => {
  const payload = JSON.parse(await readFile(new URL("../../research/results/love_letter_portable_subgame_2026-09-17.json", import.meta.url), "utf8"));
  assert.equal(payload.schema_version, "love_letter_portable_policy_v1");
  assert.equal(payload.scope, "four_card_late_round_subgame_only");
  assert.equal(payload.full_round_runtime_allowed, false);
  assert.equal(payload.independent_evaluation.passed, true);
  assert.equal(payload.policy.length, 60);
  for (const record of payload.policy) {
    assert.ok([0,1].includes(record.player));
    assert.ok(Array.isArray(record.information_set));
    assert.ok(Math.abs(record.distribution.reduce((sum,d) => sum+d.probability, 0)-1)<1e-12);
    for (const {action, probability} of record.distribution) {
      assert.ok(Number.isFinite(probability) && probability>=0);
      assert.ok(Number.isInteger(action.card) && action.card>=1 && action.card<=8);
    }
  }
});
