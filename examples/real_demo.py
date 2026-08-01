"""Real-world test: the documented ULTA fake-raise vs the WST real raise."""
import json, urllib.request
from killpass import Skeptic

def ollama(prompt: str) -> str:
    req = urllib.request.Request("http://localhost:11434/api/chat",
        data=json.dumps({"model": "qwen3.5:35b", "think": False, "stream": False,
                         "options": {"temperature": 0},
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["message"]["content"]

skeptic = Skeptic(llm=ollama)

ULTA = """Ulta Beauty Announces First Quarter Fiscal 2026 Results and Updates Fiscal 2026 Guidance
June 2, 2026 — Q1 net sales increased 11.1%; comparable sales increased 5.3%; gross margin expanded 100 basis points.
Fiscal 2026 outlook: net sales growth of 6% to 7% (unchanged). Comparable sales growth of 2.5% to 3.5% (unchanged).
Operating income growth of 6.5% to 9%. Diluted EPS of $28.36 to $28.80, compared to prior guidance of $28.05 to $28.55.
For the second quarter, the company expects comparable sales growth of 1.5% to 2.0%."""

WST = """West Pharmaceutical Services Reports Second-Quarter 2026 Results
July 23, 2026 — Q2 net sales of $872.3 million grew 15.2%; adjusted-diluted EPS of $2.37.
The company is increasing its full-year 2026 adjusted-diluted EPS guidance range to $8.85 to $9.05,
up from the previous range of $8.40 to $8.75, and raising full-year 2026 net sales guidance
to a range of $3.345 billion to $3.380 billion. Growth was led by high-value product components,
including ongoing growth in GLP-1 elastomers."""

for name, claim, src in [
    ("ULTA (the documented fake-raise)", "Ulta Beauty raised its fiscal 2026 guidance", ULTA),
    ("WST (a genuine raise)", "West Pharmaceutical raised its full-year 2026 EPS guidance", WST),
    ("Grounding-rule test (claim not in sources)", "Ulta Beauty announced a $2 billion acquisition of a rival", ULTA),
]:
    v = skeptic.attack(claim, [src])
    print(f"\n=== {name}")
    print(f"CLAIM:    {claim}")
    print(f"VERDICT:  {v.result}")
    print(f"EVIDENCE: {v.evidence[:2]}")
    print(f"WHY:      {v.rationale[:220]}")
    flags = {k: x for k, x in v.checks.items() if x == 'yes'}
    print(f"TRAPS FIRED: {flags or 'none'}")
