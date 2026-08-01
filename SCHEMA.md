# Verdict schema v1 (frozen)

`schema_version = 1`. Fields an integrator may pin:

| field | type | notes |
|---|---|---|
| `result` | `"CONFIRMED" \| "REFUTED" \| "INSUFFICIENT"` | `dual_attack` adds `"ESCALATE"`; `attack` never does |
| `downgrade_reason` | str or null | null iff result is decisive; else a reason code below |
| `evidence` | `list[EvidenceSpan]` | `EvidenceSpan = {quote: str, source_index: int}`; >=1 on decisive |
| `rationale` | str | one plain paragraph |
| `checks` | dict | exactly the five trap keys -> `yes`/`no`/`n/a` |
| `schema_version` | int | `1` |
| `killpass_version` | str | package version |

**Downgrade reasons, severity high->low:** `NO_SOURCES`, `UNPARSEABLE`,
`SCHEMA`, `TRUNCATED`, `QUOTE_TOO_LONG`, `NEAR_WHOLE_SOURCE`, `CLAIM_ECHO`,
`QUOTE_TOO_SHORT`, `UNGROUNDED`, `MODEL_INSUFFICIENT`. When several quotes
fail, the highest-severity reason is reported.

**Frozen mechanical constants:** min quote 12 chars, max 500, near-whole
alpha 0.5 (sources >=500 chars) / 0.9 (shorter), claim-echo = quote is a
substring of the claim or its token set is a subset of the claim's.
