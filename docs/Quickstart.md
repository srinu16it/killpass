# Quickstart

Install (via `pip install killpass`):

```
pip install killpass
```

Use, three lines, any LLM:

```python
from killpass import Skeptic

def my_llm(prompt: str) -> str:
    return your_model_call(prompt)   # OpenAI, Anthropic, Ollama, anything

skeptic = Skeptic(llm=my_llm)
verdict = skeptic.attack(
    claim="Acme Corp raised its FY26 guidance",
    sources=[press_release_text, filing_text],
)
print(verdict.result)     # CONFIRMED | REFUTED | INSUFFICIENT
print(verdict.evidence)   # the exact quotes that decided it
print(verdict.rationale)  # one plain-language paragraph
```

That's the whole API. killpass is the harness, not the brain, you bring
the model, it brings the discipline.
