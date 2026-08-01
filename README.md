# killpass

**AI that double-checks itself before it speaks.**

[![PyPI](https://img.shields.io/pypi/v/killpass.svg)](https://pypi.org/project/killpass/) [![Python](https://img.shields.io/pypi/pyversions/killpass.svg)](https://pypi.org/project/killpass/) [![License](https://img.shields.io/pypi/l/killpass.svg)](https://github.com/srinu16it/killpass/blob/main/LICENSE) [![CI](https://github.com/srinu16it/killpass/actions/workflows/ci.yml/badge.svg)](https://github.com/srinu16it/killpass/actions/workflows/ci.yml)

```bash
pip install killpass
```

📦 **[pypi.org/project/killpass](https://pypi.org/project/killpass/)**

![How killpass works](https://raw.githubusercontent.com/srinu16it/killpass/main/assets/how-it-works.svg)

## The problem

AI assistants believe things too easily.

Ask an AI *"Did this company raise its forecast?"* It reads a headline that says "Company Raises Outlook" and answers **yes**. The actual document says the forecast was cut. The AI trusted the headline instead of the source.

Every team building AI products hits this. It is the main reason people distrust AI answers.

## What killpass does

It gives your AI a built-in skeptic: a second AI whose only job is to prove the first one wrong before the answer reaches a human. Spell-check, but for AI claims.

## How it works, in three steps

1. **Your AI makes a claim.** *"This company raised its forecast."*
2. **killpass sends the claim to a skeptic AI** with one instruction: go to the source document and try to destroy this claim. A claim you cannot prove from the source fails.
3. **You get a verdict:**
   - **CONFIRMED**: the claim survived, with the exact quote from the source.
   - **REFUTED**: the sentence in the document that kills it.
   - **INSUFFICIENT**: the source does not settle it, so the claim fails safe rather than guessing.

## Why believe this works

killpass comes from verification patterns used in a real research system.

In one run, a system nominated four stocks because headlines said "raised guidance." Each claim went through the skeptic. **All four died.** One press release said "Updates," not "Raises." Another buried a forecast cut inside the same document. A third funded its good news with a new loan the headline never mentioned. The skeptic read the actual SEC filings and caught what the reader-AI missed, four times out of four.

## It works on any news, not just finance

The same three lines handle any domain. The clearest demo is one study, two claims (run `examples/any_news_demo.py` yourself, tested with a free local model at temperature 0):

| Claim | Verdict | The deciding quote |
|---|---|---|
| "A new study **proves** coffee **prevents** diabetes" | **REFUTED** | *"As an observational study, no causal conclusions can be drawn."* |
| "An observational study found coffee drinkers had a 12% lower incidence" | **CONFIRMED** | *"...showed a 12% lower incidence of type 2 diabetes..."* |

Same study. Same source. Opposite verdicts. killpass passes the honest claim and kills the overclaim.

One honest limit: killpass verifies claims against the sources you provide. It checks whether the document says something. It does not discover truth. If the source lies, the verdict faithfully cites the lie, and it names the quote so you can check.

## Who needs this

Any team whose AI answers questions from documents: legal tech, finance tools, medical summaries, customer support, research assistants. They ship wrong answers today, and they know it.

## The honest limit (read this)

killpass checks that a verdict is grounded in a real, verbatim source span. It does not check that the claim is true. A quote can exist in a document yet be negated (*"we deny guidance was raised"*) or come from a third-party rumor. A substring engine cannot catch those, so killpass measures the residual instead of faking a filter. The benchmark has two halves: a 48-case mechanical pack (deterministic, canned model output, in CI) that pins every gate reason code, and a live residual harness (`bench/run.py`) you run on your own model that reports false-confirm counts per class (negation, rumor, sarcasm, hypothetical) as `k/n` with a Wilson interval. It reports counts, never an accuracy rate. Full model: [SECURITY.md](https://github.com/srinu16it/killpass/blob/main/SECURITY.md). Frozen contract: [SCHEMA.md](https://github.com/srinu16it/killpass/blob/main/SCHEMA.md).

## For engineers (30 seconds)

```python
from killpass import Skeptic

skeptic = Skeptic(llm=my_llm)  # my_llm: prompt -> text, any model

verdict = skeptic.attack(
    claim="Acme Corp raised its FY26 guidance",
    sources=[acme_press_release, acme_10q],
)

print(verdict.result)             # CONFIRMED | REFUTED | INSUFFICIENT
print(verdict.downgrade_reason)   # why, if INSUFFICIENT (documented codes, SCHEMA.md)
for span in verdict.evidence:     # each: a verbatim quote + which source
    print(span.quote, "-> source", span.source_index,
          "@", (span.start_char, span.end_char))  # exact offsets, or None
for ref in verdict.source_manifest:  # audit trail: sha256 of each judged source
    print(ref.index, ref.sha256)
```

Design principles (full detail in [DESIGN.md](https://github.com/srinu16it/killpass/blob/main/DESIGN.md)):
- **Refute-first prompting.** The skeptic gets rewarded for killing claims, not confirming them.
- **Evidence or it did not happen.** Every verdict must quote its source.
- **Unclear fails.** Ambiguity never passes.
- **Model-agnostic.** Bring any LLM. killpass is the harness, not the brain.

## Bring any source: PDF, Word, web page, text

The judge only ever sees text. Small loaders turn real-world documents into text first, so what got judged stays inspectable:

```python
from killpass import Skeptic, load

sources = [
    load("acme_press_release.pdf"),          # PDF (pip install killpass[pdf])
    load("board_minutes.docx"),               # Word, no extra install
    load("https://ir.acme.com/news/q2.html"), # web page, no extra install
    open("notes.txt").read(),                 # plain text always works
]
verdict = Skeptic(llm=my_llm).attack("Acme raised its guidance", sources)
```

Fetching stays separate from judging on purpose. `load()` runs before the skeptic, never during, so verdicts stay reproducible and nothing browses the web mid-judgment.

## Status

**v0.5.0, published and hardened.** `pip install killpass`. 107 tests including a 48-case mechanical adversarial pack in CI. The verdict contract is frozen at schema v3 ([SCHEMA.md](https://github.com/srinu16it/killpass/blob/main/SCHEMA.md)). Multiple rounds of adversarial review hardened the design, before and after each change. The verification patterns were extracted from a real research system.

## Limitations

**killpass does one job.** Given a claim, sources, and any LLM callable, it returns `CONFIRMED`, `REFUTED`, or `INSUFFICIENT` with an audit trail. A decisive verdict must quote real text. The library then checks every quote is a verbatim span from exactly one source: not invented, not pasted across sources, not a dump of the source, not a copy of the claim, not from text the model never fully saw if you capped length. If no quote passes, you get `INSUFFICIENT`, not a soft maybe.

**Grounded is not the same as true.** A pass means the model's decisive answer ties to a real, checked quote from your sources. It does not mean the claim is true in the world, that the source is honest, complete, or current, or that the model reasoned correctly about meaning.

**What killpass does not do:**

- It does not retrieve documents, browse the web, or run an agent loop.
- It does not use NLI models, embeddings, or a second LLM to re-check the first.
- It does not detect sarcasm, irony, or "someone said" rumor as falsehood.
- It does not fully solve negation (a denial can still contain the words of the claim) or every prompt injection where a source fakes the end of the model's instructions.
- It does not replace human judgment on high-stakes decisions.

**What you can count on.** The guarantee is mechanical quote grounding for decisive verdicts, not an accuracy percentage. The 48-case mechanical pack pins that guarantee in CI. The live residual harness reports how often each residual class false-confirms on your model as `k/n` with a confidence interval, not a rate. Use `dual_attack` when you want two independent skeptics; disagreement returns `ESCALATE`. Prefer `INSUFFICIENT` over a pretty answer you cannot show the quote for.

## Questions?

The hard ones (why not chain-of-thought, does cost go up, grounded vs true, which models, is it production-ready) get honest answers in the [FAQ](https://github.com/srinu16it/killpass/blob/main/FAQ.md).

## Extending killpass

killpass stays one small thing on purpose. A written doctrine governs its growth, *reach, never scope*: no path may assemble the sources, re-encode the verdict, or frame a domain as a supported job. Want a CLI or a framework adapter? Build it as a community leaf under your own name. See [ARCHITECTURE.md](https://github.com/srinu16it/killpass/blob/main/ARCHITECTURE.md).

## Hardening

Multiple rounds of adversarial review hardened the grounding gate and the verdict schema, then froze them. What the tool guarantees, and where it can still be fooled, live in plain language in [SECURITY.md](https://github.com/srinu16it/killpass/blob/main/SECURITY.md). The frozen verdict contract is in [SCHEMA.md](https://github.com/srinu16it/killpass/blob/main/SCHEMA.md).

## License

Apache 2.0.
