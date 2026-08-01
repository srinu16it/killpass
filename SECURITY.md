# Security & honesty model

killpass is a small, zero-dependency harness with one job. This document
states plainly what it does, what it does **not**, and where it can be
fooled, because a tool that catches overclaims must not overclaim about
itself.

## The one guarantee

killpass verifies that **every** quote on a decisive verdict is a **real,
verbatim, non-trivial span of the source the model cited**. A CONFIRMED or
REFUTED verdict cannot carry a quote the model invented, a whole-source dump,
a mere echo of the claim, a span stitched across two sources, or a quote
misattributed to a source that does not contain it. One fabricated companion
quote fails the whole verdict, even beside a real one. If any quote fails, the
verdict is downgraded to INSUFFICIENT with a reason code.

## What it does NOT guarantee (grounded ≠ supported)

A quote can **exist** in a source yet not **support** the claim:

- **Negation**, *"we deny that guidance was raised"* contains the span
  *"guidance was raised."*
- **Third-party rumor**, *"analysts said Acme raised guidance"* restates
  the claim without the company confirming it.
- **Sarcasm / hypotheticals**, *"as if guidance was raised"*.

A substring engine **cannot** detect these, by design. We do **not** ship a
half-measure negation heuristic (it would create false rejections without
closing the hole). Instead we **measure** the residual and publish the
number (see the benchmark). Treat CONFIRMED as *"grounded in a real span
under a refute-first skeptic,"* never as *"proven true."*

## Prompt injection via sources

Sources are untrusted input. killpass wraps each in
`<<<UNTRUSTED_SOURCE>>>` delimiters and instructs the model to treat their
content as data, not instructions. This is **defense-in-depth, not
immunity**, no pure-prompt library can be injection-proof. Mitigations:
use `dual_attack` and route ESCALATE to a human for high-stakes claims;
never treat a CONFIRMED as cryptographic proof.

One concrete residual: a source can embed the literal end-delimiter
(`<<<END_UNTRUSTED_SOURCE 0>>>`) followed by its own instructions, breaking
out of the data fence. A zero-dependency prompt library cannot fully seal
this. The honest mitigation is the same: dual_attack + human on ESCALATE,
and never trusting a lone CONFIRMED from adversarial documents.

## Sources reflect what you gave it

killpass judges the claim against the documents you pass in. If a source
document itself is false, the verdict faithfully cites the false document.
killpass verifies claim-vs-source, not source-vs-reality. Every verdict
quotes its span and names its `source_index` so the judgment is always
auditable.

## Fail-closed and robustness (v0.3)

The harness is built to fail closed, never open:

- **No decisive verdict without proof.** Every quote must ground against its
  cited source, or the verdict is INSUFFICIENT.
- **Operational failures are not verdicts.** A model that raises or returns an
  empty or non-text response yields `LLM_ERROR`, never a content verdict, and
  never escapes `attack()` as an exception.
- **One JSON object only.** A decoy object or trailing model output fails to
  `UNPARSEABLE` rather than being scanned for the first parseable object.
- **Bounds reject oversize runs.** Claim, source count, total source length,
  model response, and evidence-item count have generous hard caps
  (`INPUT_TOO_LARGE` / `RESPONSE_TOO_LARGE`).
- **Type misuse is loud.** A non-string claim or source raises `TypeError` at
  the boundary rather than degrading silently (a `None` source is skipped and a
  `None` claim becomes empty; those are data conditions, not misuse).

The frozen verdict contract is [SCHEMA.md](SCHEMA.md) (schema v3).

## Reporting

Found a way to make a decisive verdict carry a worthless quote? That's a
bug in the one job, open an issue with a reproducing fixture
(claim + sources + the model JSON). Real, dated cases preferred.


## Untrusted inputs (claim and sources)

Both the claim and the sources are wrapped in `<<<UNTRUSTED_...>>>` markers and
the model is told to treat them as data, not instructions. This is
defense-in-depth against prompt injection in either input, not immunity.

## URL loading (`from_url`)

`from_url` refuses private, loopback, link-local, and unresolvable hosts,
caps the download at 10 MB, and does not follow redirects, to limit SSRF and
denial-of-service risk when running inside a service. For anything broader,
fetch in your own retrieval layer and pass the text in. killpass judges; it
does not crawl.
