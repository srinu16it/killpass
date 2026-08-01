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

Ask an AI: *"Did this company raise its forecast?"* It reads a headline that
says "Company Raises Outlook!" and answers **yes**. But the actual document
says the forecast was *cut*. The AI repeated the headline instead of checking
the source.

Every team building AI products has this problem. It is the main reason
people don't trust AI answers.

## What killpass does

> It gives your AI a built-in **skeptic** — a second AI whose only job is to
> try to prove the first one wrong, before the answer reaches a human.

Like spell-check, but for AI claims.

## How it works — three steps

1. **Your AI makes a claim.** *"This company raised its forecast."*
2. **killpass sends the claim to a skeptic AI** with one instruction:
   *don't trust it — go to the original document and try to destroy this
   claim.* If it can't be proven from the source, it fails.
3. **Back comes a simple verdict:**
   - **CONFIRMED** — the claim survived the attack, with the exact quote
     that grounds the verdict
   - **REFUTED** — here is the sentence in the document that kills it

The default is skepticism: when the evidence is unclear, the claim fails.

## Why believe this works

This isn't a theory. killpass is extracted from verification patterns used in a real research
system. One example:

In one run, a system nominated four stocks because headlines said "raised
guidance." Each claim went through the skeptic. **All four died** — one press
release literally said "Updates," not "Raises"; another buried a forecast
*cut* inside the same document; a third funded its good news with a new loan
the headline never mentioned. The skeptic caught what the reader-AI missed,
four out of four, by reading the actual SEC filings.

## It works on any news, not just finance

The same three lines handle any domain. The clearest demo is one study, two
claims (run it yourself: `examples/any_news_demo.py`, tested with a free
local model at temperature 0):

| Claim | Verdict | The deciding quote |
|---|---|---|
| "A new study **proves** coffee **prevents** diabetes" | **REFUTED** | *"As an observational study, no causal conclusions can be drawn."* |
| "An observational study found coffee drinkers had a 12% lower incidence" | **CONFIRMED** | *"...showed a 12% lower incidence of type 2 diabetes..."* |

Same study. Same source. Opposite verdicts. The skeptic isn't anti-claim —
it's anti-**overclaim**. That's the whole product in one table.

(Honest limit: killpass verifies claims against the sources *you provide* —
it checks "does the document say this," it does not discover truth. If the
source lies, the verdict faithfully cites the lie. Every verdict is
auditable because it must quote its document.)

## Who needs this

Anyone whose AI answers questions from documents: legal tech, finance
tools, medical summaries, customer support, research assistants. They all
ship wrong answers today, and they all know it.

## The honest limit (read this)

killpass checks that a verdict is **grounded in a real, verbatim source
span** — not that the claim is *true*. A quote can exist in a document yet
be negated (*"we deny guidance was raised"*) or a third-party rumor. A
substring engine cannot catch those, so we **measure** the residual instead
of faking a filter. On a small shipped benchmark (a handful of hand-written cases, one local
model at temperature 0), negation and rumor did not false-confirm — a smoke
check, not an accuracy rate. Full model:
[SECURITY.md](https://github.com/srinu16it/killpass/blob/main/SECURITY.md) · frozen contract: [SCHEMA.md](https://github.com/srinu16it/killpass/blob/main/SCHEMA.md).

## For engineers (30 seconds)

```python
from killpass import Skeptic

skeptic = Skeptic(llm=my_llm)  # my_llm: prompt -> text, any model

verdict = skeptic.attack(
    claim="Acme Corp raised its FY26 guidance",
    sources=[acme_press_release, acme_10q],
)

print(verdict.result)     # CONFIRMED | REFUTED | INSUFFICIENT
print(verdict.evidence)   # the grounded span(s), each with its source index
print(verdict.rationale)  # one paragraph, human-readable
```

Design principles (full detail in [DESIGN.md](https://github.com/srinu16it/killpass/blob/main/DESIGN.md)):
- **Refute-first prompting** — the skeptic is rewarded for killing claims,
  not confirming them
- **Evidence or it didn't happen** — every verdict must quote its source
- **Unclear = failed** — ambiguity never passes
- **Model-agnostic** — bring any LLM; killpass is the harness, not the brain

## Bring any source — PDF, Word, web page, text

The judge only ever sees text; small loaders turn real-world documents into
text first (so what was judged is always inspectable):

```python
from killpass import Skeptic, load

sources = [
    load("acme_press_release.pdf"),          # PDF (pip install killpass[pdf])
    load("board_minutes.docx"),               # Word — no extra install
    load("https://ir.acme.com/news/q2.html"), # web page — no extra install
    open("notes.txt").read(),                 # plain text always works
]
verdict = Skeptic(llm=my_llm).attack("Acme raised its guidance", sources)
```

Fetching stays separate from judging on purpose: `load()` runs before the
skeptic, never during — verdicts remain reproducible and nothing browses
the web mid-judgment.

## Status

**v0.2.1 — published and hardened.** `pip install killpass`. 22 tests plus an
adversarial fixture pack in CI; the design was hardened through multiple rounds of adversarial review.
The verification patterns were extracted from a real research system.

## Limitations

**killpass does one job:** given a claim, sources, and any LLM callable, it returns
`CONFIRMED`, `REFUTED`, or `INSUFFICIENT` with an audit trail. A decisive verdict
must quote real text; the library then checks every quote is a verbatim span from
exactly one source (not invented, not pasted across sources, not a dump of the
source, not a copy of the claim, not from text the model never fully saw if you
capped length). If no quote passes, you get `INSUFFICIENT`—not a soft “maybe yes.”

**Grounded is not the same as true.** Pass means: the model’s decisive answer is
tied to a real, checked quote from your sources. It does **not** mean the claim
is true in the world, that the source is honest, complete, or current, or that
the model reasoned correctly about meaning.

**What killpass does not do**

- It does not retrieve documents, browse the web, or keep an agent loop.
- It does not use NLI models, embeddings, or a second LLM to re-check the first.
- It does not detect sarcasm, irony, or “someone said…” rumor as falsehood.
- It does not fully solve negation (a denial can still contain the words of the
  claim) or every prompt-injection / fence-breakout where a source fakes the
  end of the model’s instructions.
- It does not replace human judgment on high-stakes decisions.

**What you can count on**

The **guarantee** is mechanical quote grounding for decisive verdicts—not a
accuracy percentage. On the small shipped benchmark, the residual classes above did not
false-confirm — a measurement on a handful of cases, not the product promise. Use `dual_attack` when you
want two independent skeptics; disagreement returns `ESCALATE`. Prefer
`INSUFFICIENT` over a pretty answer you cannot show the quote for.

## Questions?

The hard ones — *why not chain-of-thought? doesn't cost go up? grounded vs true? which models? is it production-ready?* — are answered honestly in the [FAQ](https://github.com/srinu16it/killpass/blob/main/FAQ.md).

## Extending killpass

killpass deliberately stays one small thing. Its expansion is governed by a written doctrine — *reach, never scope*: no path may assemble the sources, re-encode the verdict, or frame a domain as a supported job. Want a CLI or a framework adapter? Build it as a community leaf under your own name. See [ARCHITECTURE.md](https://github.com/srinu16it/killpass/blob/main/ARCHITECTURE.md).

## Hardening

The grounding gate and verdict schema were hardened through multiple rounds of adversarial review, then frozen. What the tool guarantees and where it can still be fooled are stated plainly in [SECURITY.md](https://github.com/srinu16it/killpass/blob/main/SECURITY.md); the frozen verdict contract is in [SCHEMA.md](https://github.com/srinu16it/killpass/blob/main/SCHEMA.md).

## License

Apache 2.0.
