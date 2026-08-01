# Evaluation 1 — mechanical contract validation

- cases: **10500**  (seed 20260801; dataset sha256 `f23afe627d447dee…`)
- canned model output; no LLM was called. This measures the gate, not a model.

## Headline

**Mechanical UEER (generated fixtures, canned output, no LLM): 0 escapes out of 8500 invalid-evidence cases.**
Rule-of-three 95% upper bound ≈ 0.035% **on this generated distribution only** (not a claim about real-model deployments or residual classes the gate does not target).

## Metrics

All figures are on generated fixtures with canned model output (no LLM); "fixture target" is the bar for the gate's code, not an accuracy claim.

| metric (generated fixtures) | value | fixture target |
|---|---|---|
| invalid-evidence escape rate (UEER) | 0/8500 | 0 |
| valid-evidence false-rejection rate | 0/2000 | <0.5% |
| correct downgrade reason | 8500/8500 | >99% |
| incorrect non-null offsets | 0/1250 | 0 |
| uncaught exceptions | 0/10500 | 0 |

## Per-category (failures should be 0)

| category | n | failures |
|---|---|---|
| ambiguous_offsets | 500 | 0 |
| claim_echo | 750 | 0 |
| cross_source_stitch | 750 | 0 |
| decoy_json | 500 | 0 |
| fabricated | 1000 | 0 |
| input_response_bounds | 500 | 0 |
| malformed_schema | 1000 | 0 |
| multi_one_invalid | 1000 | 0 |
| too_long | 500 | 0 |
| too_short | 500 | 0 |
| truncation | 500 | 0 |
| unicode_valid | 750 | 0 |
| valid_control | 750 | 0 |
| whole_source_dump | 500 | 0 |
| wrong_source_index | 1000 | 0 |


## Scope and honesty

This validates the harness's mechanical guarantee ONLY. It says nothing about whether a real model returns good evidence, nor about incremental value over a plain prompt — those are Evaluation 2 (incremental lift) and Evaluation 3 (end-to-end decision quality with human labels), which are NOT yet run. Fixtures are systematically generated and self-checked by construction, not hand-audited.
