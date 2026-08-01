# Dual Skeptic Mode

For high-stakes claims, run two independent skeptics:

```python
from killpass import Skeptic, dual_attack

out = dual_attack(Skeptic(llm=model_a), Skeptic(llm=model_b), claim, sources)
out["result"]   # CONFIRMED / REFUTED / INSUFFICIENT / ESCALATE
```

If the two skeptics disagree, the result is **ESCALATE**: a human should
look. Disagreement is the signal: it flags exactly the cases worth a human's
time. (This dual-grader pattern comes from the upstream research system
killpass was extracted from; treat any numbers from that system as context
for the idea, not as a benchmark of this package.)
