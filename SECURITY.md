# Security & honesty model

killpass is a small, zero-dependency harness with one job. This document
states plainly what it does, what it does **not**, and where it can be
fooled, because a tool that catches overclaims must not overclaim about
itself.

## The one guarantee

killpass verifies that a decisive verdict's evidence is a **real, verbatim,
non-trivial span of a single source you provided**. A CONFIRMED or REFUTED
verdict cannot carry a quote the model invented, a whole-source dump, a
mere echo of the claim, or a span stitched across two sources. If no quote
survives, the verdict is downgraded to INSUFFICIENT with a reason code.

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

## Reporting

Found a way to make a decisive verdict carry a worthless quote? That's a
bug in the one job, open an issue with a reproducing fixture
(claim + sources + the model JSON). Real, dated cases preferred.
