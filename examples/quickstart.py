"""Quickstart: plug in ANY LLM as a plain function.

Shown with a stub; swap `my_llm` for a real call (OpenAI, Anthropic, Ollama...).
"""
from killpass import Skeptic

def my_llm(prompt: str) -> str:
    # return openai_or_anthropic_call(prompt)
    raise NotImplementedError("wire your model here")

skeptic = Skeptic(llm=my_llm)
verdict = skeptic.attack(
    claim="Acme Corp raised its FY26 guidance",
    sources=[open("acme_press_release.txt").read()],
)
print(verdict.result, verdict.evidence, verdict.rationale)
