# Changelog

## 0.4.0 — 2026-08-01

Provenance and audit layer, adversarially reviewed before and after
implementation. **Schema bumps to v3** (purely additive; see SCHEMA.md). The
grounding gate is byte-identical to v0.3.

- **Evidence offsets.** `EvidenceSpan` gains optional `start_char`/`end_char`
  pointing into the original cited source, so an auditor can highlight the exact
  span. They are exact-or-null: emitted only when the span maps to one location
  and re-normalizing that slice reproduces the quote, `null` otherwise. Offsets
  never affect a verdict.
- **Source fingerprints.** Each judged source gets a SHA-256 of exactly the bytes
  the model saw (after truncation). It appears on the span (`source_sha256`) and
  in a new top-level `source_manifest`.
- **`SourceDocument` input.** `attack` now accepts `str`, `SourceDocument`, or
  `None` sources. `SourceDocument(content, id=None, uri=None)` carries caller
  metadata into the manifest. killpass judges `content` only and never fetches
  `uri` (retrieval stays in your loader, out of the judge).

## 0.3.0 — 2026-08-01

Correctness hardening (P0 kernel fixes, adversarially reviewed before and
after implementation). **Schema bumps to v2** — see SCHEMA.md for the
v1 -> v2 migration. Same `result` tri-state; new `downgrade_reason` codes.

- **Every evidence quote must ground, not just one.** A decisive verdict that
  pairs a real quote with a fabricated companion now fails instead of passing
  on the survivor. Malformed evidence items fail as `SCHEMA` rather than being
  silently dropped.
- **`source_index` is validated, not rewritten.** A quote must be a verbatim
  span of the source the model *cited*, not merely of some source. Grounded
  elsewhere is not grounded as cited (`SOURCE_INDEX_MISMATCH`); a missing,
  non-integer, or out-of-range index is `INVALID_SOURCE_INDEX`.
- **Whole-response JSON parsing.** The response must be exactly one JSON object
  (one optional markdown fence allowed). A decoy object or trailing model output
  fails closed to `UNPARSEABLE` instead of being scanned for the first object.
- **Operational failures are separated from content.** A model that raises or
  returns an empty/non-text response reports `LLM_ERROR`, never a content
  verdict, and never escapes `attack()` as an exception.
- **Input and response bounds.** Oversize claim, source count, total source
  length, model response, or evidence-item count are rejected with
  `INPUT_TOO_LARGE` / `RESPONSE_TOO_LARGE`. Defaults are generous and set per
  `Skeptic(...)`.

## 0.2.3 — 2026-08-01

Security hardening (external review) + docs.
- The claim is now wrapped as untrusted data too (was interpolated raw): defense-in-depth against prompt injection carried in the claim.
- `from_url` refuses private/loopback/link-local/unresolvable hosts, caps downloads at 10 MB, and does not follow redirects (SSRF/DoS mitigation). For broader fetching, use your own retrieval and pass the text in.
- README rewritten in plain prose (no em-dashes); no code/API change from that part.

## 0.2.2, 2026-08-01

- Remove a stale project-metadata link that pointed at a now-private repo
  (fixes the dead link shown on the PyPI page). No code changes.

## 0.2.1, 2026-07-31

Fixes from an independent code audit:
- Near-whole-source no longer short-circuits: a quote that is a dump of one source but a proper span of another now grounds correctly.
- Claim-echo detection strips punctuation, so "claim." is caught like "claim".
- SECURITY.md names the delimiter-breakout residual explicitly.

## 0.2.0, 2026-07-31

Hardening release (multi-round adversarial review).

- **Grounding is now per-source**, quotes can no longer ground on a phantom span stitched across two sources.
- **Quote discipline**, reject whole-source dumps (near-whole-source), claim-echoes, and over-long/under-short spans; each with a reason code.
- **Truncation safety**, if a caller sets `max_source_chars` and a source is cut, a decisive verdict is forced to INSUFFICIENT/TRUNCATED. The harness never silently judges a partial read.
- **Schema gate**, `evidence` must be `list[{quote, source_index}]`; all five trap keys required. Frozen verdict schema v1 (see SCHEMA.md).
- **Reason codes**, every INSUFFICIENT carries a `downgrade_reason` (10 codes, severity-ordered).
- **Renamed the promise**, killpass checks *grounded in a verbatim span*, not *true/supported*. Negation and third-party rumor are documented residuals, measured not hidden (SECURITY.md, bench/).
- **Injection defense-in-depth**, sources wrapped in untrusted delimiters.
- **Unicode**, NFKC + casefold + smart-quote/dash folding.
- **String-aware JSON extraction**, braces inside quoted strings no longer mis-cut.
- Adversarial fixture pack (`tests/adversarial/`) runs in CI; live benchmark in `bench/`.

## 0.1.0, 2026-07-31, 2026-07-31

First release.

- `Skeptic.attack(claim, sources)`, refute-first verification with the
  five-trap checklist (title-vs-body, raise-inside-cut, borrowed good news,
  recycled news, stale claim)
- Grounding rule: CONFIRMED/REFUTED verdicts whose quotes do not appear in
  the sources are automatically downgraded to INSUFFICIENT
- `dual_attack`, two independent skeptics; disagreement returns ESCALATE
- Zero runtime dependencies; bring any LLM as a plain callable
- Source loaders: `load()` for .docx and web pages (stdlib-only) and PDFs
  via the optional `killpass[pdf]` extra; judging stays offline and pure
