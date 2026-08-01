# Verdict schema v2

`schema_version = 2`. Fields an integrator may pin:

| field | type | notes |
|---|---|---|
| `result` | `"CONFIRMED" \| "REFUTED" \| "INSUFFICIENT"` | `dual_attack` adds `"ESCALATE"`; `attack` never does |
| `downgrade_reason` | str or null | null iff result is decisive; else a reason code below |
| `evidence` | `list[EvidenceSpan]` | `EvidenceSpan = {quote: str, source_index: int}`; every span grounds; >=1 on decisive |
| `rationale` | str | one plain paragraph |
| `checks` | dict | exactly the five trap keys -> `yes`/`no`/`n/a` |
| `schema_version` | int | `2` |
| `killpass_version` | str | package version |

## Downgrade reasons

Severity high -> low. When several quotes fail on the decisive path, the
highest-severity reason is reported.

**Operational / bound** (the harness could not obtain a judgeable verdict; not
a content verdict):

- `NO_SOURCES` — no usable source was provided.
- `LLM_ERROR` — the model callable raised, or returned an empty or non-text response.
- `INPUT_TOO_LARGE` — claim, source count, or total source length over budget (rejected before the model is called).
- `RESPONSE_TOO_LARGE` — the model response, or its evidence-item count, over budget.

**Content** (the model answered; the answer failed a gate):

- `UNPARSEABLE` — the response was not exactly one JSON object.
- `SCHEMA` — the object was missing required fields, had the wrong types, or carried a malformed evidence item.
- `TRUNCATED` — a source was truncated to the caller's budget, so a decisive verdict is withheld.
- `INVALID_SOURCE_INDEX` — an evidence item's `source_index` was missing-as-value, non-integer, or out of range.
- `SOURCE_INDEX_MISMATCH` — the quote is not a verbatim span of the source the model cited (grounded elsewhere is not grounded as cited).
- `QUOTE_TOO_LONG` — a quote exceeded the max span length.
- `NEAR_WHOLE_SOURCE` — a quote covered too much of its cited source (a dump, not a pointer).
- `CLAIM_ECHO` — a quote added no information beyond the claim itself.
- `QUOTE_TOO_SHORT` — a quote was below the minimum span length.
- `UNGROUNDED` — a decisive verdict carried no evidence to ground.
- `MODEL_INSUFFICIENT` — the model itself declined to reach a decisive verdict.

**Frozen mechanical constants:** min quote 12 chars, max 500, near-whole alpha
0.5 (sources >=500 chars) / 0.9 (shorter), claim-echo = quote is a substring
of the claim or its token set is a subset of the claim's.

## Migration: v1 -> v2

`schema_version=2` keeps the same `result` tri-state. Every v1 reason code
keeps its exact meaning. What changed:

- **Every** evidence quote must ground, not just one. A decisive verdict with a
  single fabricated companion quote now fails.
- `source_index` is validated against the source the model declared, no longer
  rewritten to the first source that happens to contain the quote. New codes
  `INVALID_SOURCE_INDEX` and `SOURCE_INDEX_MISMATCH` report the two ways that
  fails.
- The whole response must be exactly one JSON object. A decoy object or trailing
  prose now fails to `UNPARSEABLE` instead of being scanned for the first object.
- Model crashes and empty responses report `LLM_ERROR`, separated from content
  failures.
- Oversize inputs and responses report `INPUT_TOO_LARGE` / `RESPONSE_TOO_LARGE`.

`downgrade_reason` is an **open set** of documented codes. A consumer that
hard-codes the v1 list must treat an unknown code as a generic content failure,
not crash. No fields were added or removed in v2; new optional fields, if any
ever land, will default to null or absent for forward-compatibility.
