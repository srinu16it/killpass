# Changelog

## 1.2.0 — 2026-08-01

Additive provenance. **Schema bumps to v4** (one optional field; forward-compatible).

- **`run_metadata`.** `Skeptic(run_metadata={...})` echoes a caller-supplied dict
  (model name, prompt version, run id, ...) verbatim into every verdict's
  `run_metadata`. killpass never reads or fills it (the `llm` is an opaque
  callable) and it never touches the gate, exactly like `SourceDocument.id`/`uri`.
  It is `null` when not supplied.
- **Trap framing clarified (docs).** The five prompt traps are documented as a
  finance-flavored, non-gating scaffold from the source research system, not a
  domain product; killpass ships no domain "profiles" or configurable checklist.

Three other items from the external review's P1 set were considered and
deliberately **not** built into killpass: `outcome_kind` (derivable from
`downgrade_reason`, a second encoding), richer `dual_attack` agreement grades
(a new adjudication axis; belongs in a wrapper), and a caller-configurable trap
profile (frames a domain). The doctrine is why.

## 1.1.0 — 2026-08-01

Hardening release (additive; no API or schema change).

- **Loader denial-of-service limits.** `from_docx` reads `word/document.xml`
  through a bounded stream, so a zip bomb is refused before it is decompressed.
  `from_pdf` rejects oversize files and page counts. `from_url` rejects a
  non-text `Content-Type` instead of stripping a binary blob. These loaders run
  before the judge; they are a convenience, not a hardened crawler (SECURITY.md).
- **Per-run nonce prompt delimiters.** The claim and each source are fenced with
  a random per-call token chosen not to appear in the inputs, so a source cannot
  forge the data fence with a fixed end-marker. Defense-in-depth, not immunity.
- **Continuous integration hardened.** Adds a ruff lint gate, a build job that
  installs the built wheel into a clean environment and smoke-imports it, and
  Python 3.13 to the matrix.

## 1.0.1 — 2026-08-01

Correctness patch from an external review. No API or schema change: these fixes
make the gate enforce the contract it already documented. A response that was
wrongly accepted before now correctly fails.

- **Offset uniqueness is overlapping-aware.** `locate_span` used a non-overlapping
  count, so a repeated run like `"aaaa..."` with a shorter substring quote looked
  unique and emitted an offset. It now returns null unless the match is truly the
  only locus, honoring the exact-or-null guarantee.
- **Strict evidence types.** A non-string `quote` (e.g. a number) was `str()`-cast
  and could ground. Quotes must now be strings and `result` must be a string, or
  the response fails as `SCHEMA` instead of being coerced.
- **Evidence structure is validated for every result.** A malformed evidence item
  on an `INSUFFICIENT` response skipped validation and passed as
  `MODEL_INSUFFICIENT`; it is now a `SCHEMA` failure like any other malformed
  response.
- **Constructor limits are validated.** Negative, zero, boolean, or non-integer
  bounds raise `ValueError` at construction instead of producing strange behavior
  later.
- Package maturity classifier corrected to Beta (stable API, early adoption).

## 1.0.0 — 2026-08-01

Stability release. No behavior change from 0.5.0.

- **The public API and verdict schema v3 are frozen.** 1.x releases will not
  break `Skeptic.attack`, `dual_attack`, `Verdict`, `EvidenceSpan`,
  `SourceDocument`, `load`/`load_all`, or the documented schema. SCHEMA.md is the
  contract.
- **What 1.0 means:** the one job (return a grounded CONFIRMED/REFUTED with a
  verbatim audit trail, or fail closed to INSUFFICIENT) is complete and hardened
  across multiple rounds of adversarial review. The interface is stable.
- **What it does not mean:** not a claim of large-scale production use. killpass
  is early in adoption. `grounded != supported` still holds, and the residual is
  measured, not filtered.
- **Scope, by doctrine.** Three milestones from the enhancement plan are
  deliberately not in killpass: semantic support-judgment (needs an NLI,
  embedding, or second-LLM step the library refuses), observability metrics
  (would re-encode the verdict), and CLIs / framework adapters (community leaves
  under their own names). killpass stays one small thing.

## 0.5.0 — 2026-08-01

Evaluation layer. No library code change: the grounding gate, schema, and public
API are untouched. This release is about honest measurement.

- **Mechanical adversarial pack expanded to 48 cases**, taxonomy-complete: every
  downgrade reason at least twice, every result, plus composition (strict-all,
  severity ordering, decoy JSON) and offset exact-vs-null cases. Deterministic,
  canned model output, runs in CI. A completeness test fails loudly if a reason
  code ever lacks a fixture.
- **Live residual harness rewritten** (`bench/run.py`). It reports, per residual
  class (negation, rumor, sarcasm, hypothetical), `residual_false_confirm: k/n`
  with a Wilson 95% interval and the model id, plus true-positive / true-negative
  smoke counts. It never reports an accuracy percentage or a pooled score.
- **The semantic-support milestone was cut by design.** Judging whether a
  grounded span *supports* a claim needs an NLI model, embeddings, or a second
  LLM, all of which killpass promises not to do. killpass measures the residual;
  it does not fake the filter. Support-judgment, if wanted, belongs in a separate
  tool under its own name.

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
