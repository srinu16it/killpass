"""Live benchmark: the honest residual numbers. Run against any local model.

    python bench/run.py                 # uses Ollama qwen3.5:35b by default

Publishes: false_confirm_rate (negation+rumor that wrongly CONFIRM — the
substring engine's known residual), false_refute_rate (true positives
wrongly REFUTED), true_negative_hit_rate, and the mechanical pack (must be 1.0). The residual
numbers are a small measurement on a handful of cases, not an accuracy claim.
"""
import json, pathlib, sys, urllib.request

FIX = json.loads((pathlib.Path(__file__).parent.parent/"tests"/"adversarial"/"fixtures.json").read_text())

def ollama(prompt, model="qwen3.5:35b"):
    req = urllib.request.Request("http://localhost:11434/api/chat",
        data=json.dumps({"model":model,"think":False,"stream":False,"options":{"temperature":0},
                         "messages":[{"role":"user","content":prompt}]}).encode(),
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=300).read())["message"]["content"]

def main():
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent/"src"))
    from killpass import Skeptic
    sk = Skeptic(llm=ollama)
    cats = {}
    for fx in FIX:
        if fx.get("required_result"):   # mechanical — skip, covered in CI
            continue
        v = sk.attack(fx["claim"], fx["sources"])
        cats.setdefault(fx["category"], []).append(v.result)
        print(f"[{fx['category']:15}] {fx['id']:8} -> {v.result}")
    def rate(cat, target):
        rs = cats.get(cat, [])
        return sum(1 for r in rs if r==target)/len(rs) if rs else None
    print("\n=== published residual numbers ===")
    fc = [(c, rate(c,"CONFIRMED")) for c in ("negation","rumor")]
    print("false_confirm_rate (must be low):", {c:r for c,r in fc})
    print("false_refute_rate  (true-positive wrongly REFUTED):", rate("true-positive","REFUTED"))
    print("true_negative_hit_rate (fake-raise correctly REFUTED):", rate("true-negative","REFUTED"))

if __name__ == "__main__":
    main()
