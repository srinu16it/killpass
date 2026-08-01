# killpass evaluation

Tests and clean code do not make a package matter. What matters is whether it
prevents a specific class of failures better than the cheap alternative. This
directory measures exactly that, and refuses to claim anything it has not run.

## The hypothesis under test

Not "killpass detects hallucinations" (too broad; the package cannot support it).
Instead, narrow and measurable, stated as a question to answer, not a result:

> **Does killpass's gate block decisive outputs that carry fabricated,
> misattributed, malformed, or unverifiable evidence — and does enforcing that
> lower what reaches users, at an acceptable cost?**

The first clause is a code property (Eval 1). The second is a claim about real
deployments (Eval 2/3) and is not established by the mechanical run.

## Four evaluations

| # | Question | What it needs | Status |
|---|---|---|---|
| 1 | Does the mechanical gate work? | code only, no LLM | **RUN** (below) |
| 2 | Does killpass beat a plain prompt? | ≥5 models, labeled claims, 3 reps | framework, **NOT RUN** |
| 3 | Is end-to-end decision quality good? | human-labeled claims | design only, **NOT RUN** |
| — | Is it worth the cost/latency? | measured alongside 2 | **NOT RUN** |

No placeholder numbers are presented as results anywhere in this directory.

---

## Evaluation 1 — mechanical contract validation (RUN)

`python evals/run_mechanical.py` — ~10,500 fixtures, canned model output, no LLM.
Writes `evals/reports/`. This validates what the Python code guarantees,
independent of any model's intelligence.

**Lead metric — Unsupported Evidence Escape Rate (UEER):**

```
UEER = decisive outputs carrying invalid evidence that PASSED the gate
       ------------------------------------------------------------------
       all cases whose model proposed a decisive verdict on invalid evidence
```

**Result (seed 20260801):**

> On 10,500 systematically generated invalid-evidence fixtures (taxonomy known by
> construction, canned model output), mechanical UEER was **0 / 8,500**. A
> classical rule-of-three 95% upper bound ≈ 3/n = **0.035%** applies only to this
> generated distribution of failure modes, not to live model traffic or residual
> classes the gate does not claim to catch.

All figures below are on **generated fixtures with canned model output** (no LLM);
"fixture target" is the bar for the gate's code, not an accuracy claim.

| metric (generated fixtures) | value | fixture target |
|---|---|---|
| invalid-evidence escape rate (UEER) | 0 / 8,500 | 0 |
| valid-evidence false-rejection rate | 0 / 2,000 | <0.5% |
| correct downgrade reason | 8,500 / 8,500 | >99% |
| incorrect non-null offsets | 0 / 1,250 | 0 |
| uncaught exceptions | 0 / 10,500 | 0 |

15 attack categories (fabricated, wrong-source-index, cross-source stitching,
claim echo, too-short, too-long, whole-source dump, multi-evidence one-invalid,
malformed schema, decoy JSON, unicode normalization, ambiguous offsets,
truncation, input/response bounds, valid controls).

**Honesty (read this).** Fixtures diversify quote content, length, position,
index permutations, unicode normalizations, alpha-ratio edges, and decoy
structure; every label is proved by construction plus a generator self-check that
uses an oracle independent of the gate — not a hand-audit of all 10,500 cases.
Canned output means this validates only the harness's mechanical gate. It says
nothing about whether a real model returns good evidence, nor about incremental
value over a plain prompt (Eval 2), nor about residual classes the gate does not
claim to catch such as negation or rumor (Eval 3). The generator is seeded and a
dataset sha256 is written, so the run reproduces exactly.

---

## Evaluation 2 — incremental value over a plain prompt (FRAMEWORK, NOT RUN)

`evals/incremental.py`. Three arms on the same claims, sources, and model:

- **A ordinary** — a plain "check the claim and cite evidence" prompt
- **B refute** — the killpass refute-first prompt, but **no** mechanical gate
- **C killpass** — refute-first prompt **plus** the gate

Primary endpoint: **invalid-evidence escape rate per arm.** One referee
(`killpass.grounding`) scores every arm identically, so C is 0 by construction
and A/B reveal what prompting alone lets through. The gap is the value.

The harness is runnable now (`python evals/incremental.py` smoke-tests the
wiring against a scripted model). It is **not a study.** A credible result needs:

- 1,000 claims × 5 model tiers (small local → strong hosted) × 3 conditions × 3
  repetitions ≈ 45,000 model executions;
- fixed seeds/versions recorded, raw outputs retained;
- results reported per model and per category, with confidence intervals;
- cost and latency measured alongside (median/P95 latency, tokens, $/1,000
  claims) so the safety gain is priced.

The strongest possible finding would be a small cheap model **plus** killpass
showing fewer evidence escapes than a premium model on a plain prompt. That is a
measurement to run, not a claim to make here.

---

## Evaluation 3 — end-to-end decision quality (DESIGN ONLY, NOT RUN)

This needs **human-labeled** claims — an LLM cannot be the only gold label and
then be called objective accuracy. Design:

- a public-benchmark subset (e.g. FEVER/FEVEROUS with gold evidence),
- a hand-built adversarial semantic set (negation, rumor, hypothetical, sarcasm,
  stale, entity/numeric mismatch — where "quote exists" ≠ "quote supports"),
- real-domain claims (finance filings first, since that is where the pattern
  originated), each labeled `SUPPORTED | REFUTED | INSUFFICIENT` by ≥2
  annotators with a third adjudicator, inter-annotator agreement reported.

Core metrics: **confirmation precision** (of all CONFIRMED, how many are truly
supported) reported **together with decisive coverage** (a gate that abstains on
everything has 0 false confirmations and 0 value), plus per-category
false-confirmation rate. Never a single pooled "accuracy" number.

---

## The decision rule

Market a performance claim only when all three hold:

1. **Integrity** — mechanical invalid-evidence escape rate is effectively zero.
   *(Eval 1: met on the generated distribution.)*
2. **Incremental lift** — killpass materially beats the same skeptic prompt
   without the gate. *(Eval 2: not yet run.)*
3. **Acceptable trade-off** — the reduction in escapes is worth the added
   latency, cost, and abstention. *(Eval 2/cost: not yet run.)*

Without #2, the package is a wrapper around a good prompt. Without #3, it may
work but not be worth adopting. Today, only #1 is measured.

## Where killpass sits

It is not another probabilistic score. RAG-faithfulness, NLI entailment,
self-consistency, and observability tools answer "how faithful / does this entail
/ does the model contradict itself / what happened." killpass answers one
narrower, deterministic question — **is every decisive evidence quotation real,
non-trivial, and correctly attributed** — and returns a policy decision (valid,
or failed the gate), not a number the caller must still threshold.
