"""killpass is domain-agnostic: health news, local politics, anything.

Run with a local Ollama model (or swap in any LLM callable).
The middle case is the point: same study, honest claim vs overclaim,
opposite verdicts.
"""
import json, urllib.request
from killpass import Skeptic

def ollama(prompt: str) -> str:
    req = urllib.request.Request("http://localhost:11434/api/chat",
        data=json.dumps({"model": "qwen3.5:35b", "think": False, "stream": False,
                         "options": {"temperature": 0},
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["message"]["content"]

ABSTRACT = """Journal of Nutrition Research — Abstract, July 2026.
In this observational cohort study of 12,400 adults followed for 8 years, participants
who reported drinking 3 or more cups of coffee daily showed a 12% lower incidence of
type 2 diabetes compared with non-drinkers (hazard ratio 0.88, 95% CI 0.79-0.98).
The association was attenuated after adjustment for exercise and BMI. As an
observational study, no causal conclusions can be drawn. Randomized trials are needed."""

CITY_PR = """City of Riverdale press release, July 14, 2026.
The City Council approved a $45 million budget for the new Riverdale Community Center,
with construction scheduled to begin in March 2027. The center will include a public
library branch and a 200-seat auditorium. Funding comes from the approved municipal
bond measure; no property tax increase is included in this plan."""

skeptic = Skeptic(llm=ollama)

CASES = [
    ("Health news exaggeration",
     "A new study proves that drinking coffee prevents diabetes", ABSTRACT),
    ("Same study, honest claim",
     "An observational study found coffee drinkers had a 12% lower incidence of type 2 diabetes", ABSTRACT),
    ("Local politics rumor",
     "Riverdale is raising property taxes to pay for the new community center", CITY_PR),
]

for name, claim, source in CASES:
    v = skeptic.attack(claim, [source])
    print(f"\n=== {name}\nCLAIM:    {claim}\nVERDICT:  {v.result}\nEVIDENCE: {v.evidence[:1]}\nWHY:      {v.rationale[:200]}")
