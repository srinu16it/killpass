# killpass FAQ

House rule for this page: **undersell, never overclaim.** killpass does one
narrow thing well and has real limits; both are stated plainly. If a line
here reads like marketing, it's a bug, open an issue.

## What exactly does a CONFIRMED verdict mean?
It means: the skeptic model returned CONFIRMED **and** at least one of its
quoted spans passed the mechanical gate, a real, verbatim, non-trivial span
of exactly one source you provided (length 12–500 normalized chars, not a
near-whole-source dump, not a claim-echo, not stitched across sources). It
does **not** mean the claim is true, nor that the quote *supports* the claim.
**Grounded is not supported.** The polarity of the verdict (confirm vs
refute) is the model's judgment under a refute-first prompt; only the
*existence and shape* of the evidence is checked by code.

## Do I even need this? Isn't a good LLM enough?
A good LLM still repeats headlines it never verified. Ask "did the company
raise guidance?" and it answers from the title "Raises Outlook" while the
body says "unchanged." killpass makes a decisive answer cite a real span from
the source, or downgrade to INSUFFICIENT. If being wrong is cheap for you,
you may not need it, use chain-of-thought and move on. It earns its keep as
a claim-vs-source gate where a confident wrong answer is expensive. It is not
a substitute for domain review, counsel, or a compliance system, and its
residual failures (below) are exactly the expensive kind in those fields.

## Why not just chain-of-thought on the same model to check itself?
Two honest points. (1) Refute-first framing *may* reduce a model's tendency
to defend its own answer, but it is not independence and not a guaranteed
bias flip, the same weights can still confirm wrongly. (2) The real
difference from chain-of-thought is **not the prompt**, it's the mechanical
quote gate. Chain-of-thought is more model prose you must trust, and a model
can hallucinate a quote inside its own reasoning. killpass refuses any
decisive verdict whose quote is not actually in the source. Prompting alone
cannot prove a quote is in the document; a post-hoc deterministic membership
check can. killpass is one small, honest instance of that pattern.

## Does it need a second, different model?
No. The skeptic can be the same model that made the claim, one skeptic call,
adversarially framed, plus the code check. `dual_attack` runs two skeptics; a
disagreement returns ESCALATE (a dict with both verdicts, a human should
look). Caution: two copies of the *same* model share failure modes, so
agreement is **not** confidence, both can confirm the same wrong answer.

## Doesn't cost go up with extra LLM calls?
Yes. Default path: one skeptic LLM call per claim; `dual_attack` is two. The
harness adds no retries, those are yours if a weak model returns
UNPARSEABLE/SCHEMA. The grounding check itself costs **zero tokens** (pure
code), but the skeptic call is a full structured generation (result, quotes,
traps, rationale), not "just a quote lookup." You can try a smaller, cheaper
skeptic, but measure it: small models miss refutations and fail the JSON
schema more often. Where stakes are low, skip killpass and use
chain-of-thought.

## Is the grounding just string matching? Isn't that brittle?
Yes, it is deterministic substring matching after a fixed normalize (NFKC + a
smart-quote/dash/zero-width fold + casefold + whitespace collapse). That is a
feature: a decisive verdict can never rest on a **fabricated** quote, and
every verdict is auditable, you see the exact span and its source index. The
brittleness is one-directional and deliberate: a legitimately *reworded*
quote gets rejected (safe), a fabricated one is not accepted (safe). What it
does **not** do: prove the real span actually supports the claim. There is no
stemming, OCR repair, or table reconstruction, the judge sees exactly the
text you pass in.

## Are the five "traps" (title-vs-body, etc.) enforced by the code?
No, be clear on this. The traps are instructions in the skeptic prompt and
appear in the verdict's `checks` field, but the **harness does not gate the
result on them**. A model can mark every trap "no" and still return a grounded
CONFIRMED. The traps sharpen the skeptic's attention; the only mechanical
guarantee is the quote gate.

## What can still fool it?
By design, a substring engine cannot catch: **negation** ("we deny that
guidance was raised" contains the words "guidance was raised"), **third-party
rumor** ("analysts said…") when the sentence adds enough other words to escape
the claim-echo check, and **sarcasm/hypotheticals**. Also real residuals:
wrong-polarity REFUTED on a real quote (REFUTED is exactly as untrusted-on-
support as CONFIRMED); prompt-injection where a source fakes the end of the
instruction fence (SECURITY.md); text-extraction damage before the judge
(bad PDF/table parsing = grounded garbage); and provider-side prompt
truncation you don't know about (see long documents). killpass documents and
measures these rather than pretending to filter them.

## Can I trust the "0% residual" number I saw?
Treat it as a **smoke measurement, not a rate.** The live residual fixtures
are a handful of hand-written cases (as of now: one negation, one rumor, one
true-positive, one true-negative in `tests/adversarial/fixtures.json`), run
against one local model (`qwen3.5:35b`, temperature 0) via `bench/run.py`. "No
false confirms on n≈2" is not an accuracy figure. CI enforces the *mechanical*
fixtures (with canned model output); it does **not** run the live LLM
benchmark. Re-run `bench/run.py` on your own model, the guarantee you can
rely on is the mechanical grounding, not any number.

## How is this different from a guardrails library?
Format/PII/toxicity filters check output shape or safety. killpass only gates
a factual verdict against caller-supplied sources via quote membership. Some
citation-verification tools overlap with it; its scope is narrower than
"safety" and it composes with those tools rather than replacing them.

## Is this RAG?
No. Bring your own retrieval. The judge (`Skeptic.attack`) never fetches,
ranks, or searches, it only reads the sources you pass. There is an optional
`load()` helper that can fetch/parse a URL, PDF, or docx, but that runs
**before** you call `attack`, as your retrieval step, outside the verdict
loop. Fetching and judging are separated so verdicts stay reproducible.

## Which models work?
Any callable `str → str`. In practice, *useful* skeptics reliably emit the
required JSON (a result, a list of `{quote, source_index}`, and the five trap
keys with `yes|no|n/a` values). Weak or high-temperature models fail the
schema and return INSUFFICIENT(SCHEMA/UNPARSEABLE), measure that rate before
production. "Any model runs; not every model is useful."

## What about long documents and context limits?
killpass does not guess your model's context window. If you set
`max_source_chars` and truncation fires, a decisive verdict is forced to
INSUFFICIENT/TRUNCATED, it never silently judges a partial read **when you
set the budget.** The default is no cap. Important: if your *provider*
truncates the prompt without telling you and you left `max_source_chars`
unset, killpass cannot detect that, set the budget yourself. Chunking long
documents and deciding how multi-chunk verdicts compose is your job; a small
library should not own retrieval.

## Is it production-ready? Who uses it?
It is a small, zero-dependency library at v0.3.x with 52 tests and a
mechanical adversarial pack in CI. The verification *patterns* come from one
research stack (from a real research system); the library itself
is early, and there is no multi-customer production claim, if you adopt it,
you may be among the first. Treat it as a tested building block, not a
compliance-certified product. For high-stakes decisions use `dual_attack` and
route ESCALATE to a human, and page your ops on a spike in UNPARSEABLE/SCHEMA
(harness/model trouble) versus MODEL_INSUFFICIENT (weak sources).

## Does it record which model / temperature produced a verdict?
No. The `Verdict` carries `killpass_version`, `schema_version`, the reason
code, the grounded spans, and the raw model text, not a model id or
temperature. Recording those for reproducibility is your wrapper's job.

## Why the name?
From "kill-pass", the adversarial review stage in the system it came from,
where claims are attacked and most die. Surviving the kill-pass means the
claim passed *this harness* (grounded, non-junk evidence under a refute-first
skeptic), not that the claim is true.

---
*One-line summary: killpass is a quote-membership harness around a
refute-first LLM call. Decisive verdicts must cite a real, non-junk span from
one source you provided. It does not prove support, truth, or safety.
Residuals are documented; the numbers are small measurements, not the
product promise.*
