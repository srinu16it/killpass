# Architecture & the Expansion Doctrine

killpass has one job: given a claim, sources, and any LLM callable, return
`CONFIRMED` / `REFUTED` / `INSUFFICIENT` where a decisive verdict's evidence
must be a real verbatim span of a source (the mechanical grounding gate).

This document exists so the tool stays that one thing under pressure. The
rule below governs what may and may not be added: **expand reach, never
scope.**

## The Expansion Doctrine

**killpass expands REACH, never SCOPE.**

A path (a CLI, an adapter, a plugin, a decorator, even a docs pattern) is
admissible **only if** it cannot:

1. **Assemble or mutate the sources or the claim**, no globbing, no
   collecting multiple files into the core input, no merging, truncation,
   encoding "repair," or claim-extraction. Assembly is a laundering seam
   *wherever it lives*: it can make a span ground against text the human
   never treated as the grounding set. Transporting a *single, already-formed*
   core payload is not assembly; **constructing** that payload is.
2. **Create a second encoding of the verdict**, no exit-code-as-verdict, no
   threshold or rate, no pass/fail scalar the core never defined. The verdict
   lives **only** in the frozen JSON. A process may signal *ran* vs
   *operational error*, never *confirmed* vs *not*.
3. **Frame a domain as a supported job**, no persona pages, no "killpass for
   \<field\>," no job-shaped example that reads as intended use. Official
   examples are read as warranties whether or not one is written.

## Corollaries

- **The callable API is the integration surface.** `Skeptic(llm=...).attack(
  claim, sources)` already runs anywhere Python runs. Official width (CLI,
  framework adapters, batch service) is presumed **unnecessary**.
- **Breadth is a property, not a product.** The core is domain-agnostic; that
  is shown *neutrally* (raw claim + raw sources + verdict + "grounded ≠
  supported"), never by selecting domains to picture.
- **Community leaves are welcome, under other names.** Want a LangChain
  adapter, a shell CLI, a pytest plugin? Build it, at your own risk, in your
  own repo. killpass does not own or bless its assembly/policy contract,
  because that contract can reopen the loopholes the core closed.

## Why this is the artifact

Most small tools die by accretion: a CLI here, an adapter there, each
reasonable, together a framework nobody trusts. This doctrine is the
governance that prevents that. It is how a one-job tool stays one-job, and
stating it is more valuable than any feature it forbids.

_See the FAQ for what the tool does and does not
guarantee._
