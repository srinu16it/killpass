"""Neutral API demonstration — the core is domain-agnostic by construction.

No domain, no persona, no recommended thresholds: just the same call over
abstract documents, showing all three verdicts and the one rule that matters.
The tool works the same whether the source is a filing, a study, a memo, or
this placeholder — because it only asks "does the source contain this span."
"""
from killpass import Skeptic

# Swap this stub for any real model callable (prompt -> text).
def my_llm(prompt: str) -> str:
    raise NotImplementedError("wire your model here; see the Quickstart")

skeptic = Skeptic(llm=my_llm)

SOURCE = "The record states that the value increased to 42 from 30 in the prior period."

# 1. A claim the source supports with a real span -> CONFIRMED (with the span).
# 2. A claim the source contradicts -> REFUTED (with the contradicting span).
# 3. A claim the source is silent on -> INSUFFICIENT (no span to stand on).
for claim in [
    "The value increased to 42",
    "The value was unchanged",
    "The value will increase again next period",
]:
    verdict = skeptic.attack(claim, [SOURCE])
    print(claim, "->", verdict.result, "/", verdict.downgrade_reason)
    for span in verdict.evidence:
        print("   grounded on:", repr(span.quote), "in source", span.source_index)

# The one rule this whole library exists to enforce:
#   CONFIRMED means the verdict is grounded in a real span of YOUR source.
#   It does NOT mean the claim is true. Grounded is not supported.
