# Changelog

## 0.2.1 — 2026-07-31

Fixes from an independent code audit:
- Near-whole-source no longer short-circuits: a quote that is a dump of one source but a proper span of another now grounds correctly.
- Claim-echo detection strips punctuation, so "claim." is caught like "claim".
- SECURITY.md names the delimiter-breakout residual explicitly.

## 0.2.0 — 2026-07-31

Hardening release (multi-round adversarial review).

- **Grounding is now per-source** — quotes can no longer ground on a phantom span stitched across two sources.
- **Quote discipline** — reject whole-source dumps (near-whole-source), claim-echoes, and over-long/under-short spans; each with a reason code.
- **Truncation safety** — if a caller sets `max_source_chars` and a source is cut, a decisive verdict is forced to INSUFFICIENT/TRUNCATED. The harness never silently judges a partial read.
- **Schema gate** — `evidence` must be `list[{quote, source_index}]`; all five trap keys required. Frozen verdict schema v1 (see SCHEMA.md).
- **Reason codes** — every INSUFFICIENT carries a `downgrade_reason` (10 codes, severity-ordered).
- **Renamed the promise** — killpass checks *grounded in a verbatim span*, not *true/supported*. Negation and third-party rumor are documented residuals, measured not hidden (SECURITY.md, bench/).
- **Injection defense-in-depth** — sources wrapped in untrusted delimiters.
- **Unicode** — NFKC + casefold + smart-quote/dash folding.
- **String-aware JSON extraction** — braces inside quoted strings no longer mis-cut.
- Adversarial fixture pack (`tests/adversarial/`) runs in CI; live benchmark in `bench/`.

## 0.1.0 — 2026-07-31 — 2026-07-31

First release.

- `Skeptic.attack(claim, sources)` — refute-first verification with the
  five-trap checklist (title-vs-body, raise-inside-cut, borrowed good news,
  recycled news, stale claim)
- Grounding rule: CONFIRMED/REFUTED verdicts whose quotes do not appear in
  the sources are automatically downgraded to INSUFFICIENT
- `dual_attack` — two independent skeptics; disagreement returns ESCALATE
- Zero runtime dependencies; bring any LLM as a plain callable
- Source loaders: `load()` for .docx and web pages (stdlib-only) and PDFs
  via the optional `killpass[pdf]` extra; judging stays offline and pure
