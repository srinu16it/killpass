# killpass, design notes (plain words first, then details)

## The one rule everything follows

**A claim is guilty until proven innocent.** Most AI pipelines do the
opposite, they generate an answer and look for support. killpass inverts
it: the skeptic's job is destruction, and only claims that survive
destruction reach the user.

## The verdict object

Every attack returns:

| Field | What it is |
|---|---|
| `result` | CONFIRMED / REFUTED / INSUFFICIENT |
| `evidence` | exact quote(s) from the sources that decided it |
| `rationale` | one human-readable paragraph |
| `checks` | structured trap checklist (see below) |

## The trap checklist (learned from documented example kills)

Real failure patterns the skeptic tests by name, because generic prompting
misses them:

1. **Title vs body**, headline says "Raises," body says "Updates/Reaffirms"
2. **Raise inside a cut**, one number goes up while another goes down in
   the same document
3. **Borrowed good news**, the positive event is funded by new debt or
   one-time items disclosed elsewhere in the document
4. **Recycled news**, the "new" contract is a consolidation or extension of
   things already owned
5. **Stale claim**, the source predates the claim's timeframe

Each check returns yes/no with evidence, even when the overall verdict is
CONFIRMED, so users see *what was tested*, not just the answer.

## Dual-skeptic mode (optional)

Run two independent skeptics on the same claim; report agreement. In
production this pattern ran at ~90% agreement (Cohen's kappa ~0.9) across
91 graded events, disagreement is a signal to escalate to a human.

## What killpass is NOT

- Not a RAG framework, bring your own retrieval; killpass judges
- Not a hallucination detector for style, it verifies factual claims
  against provided sources only
- Not an agent framework, it is one small harness with one job

## Shipped

All of the below are in the released package: the `Skeptic.attack()` core,
the five-trap prompt, the frozen verdict schema, dual-skeptic mode, an
adversarial fixture pack, and the mechanical grounding gate.
