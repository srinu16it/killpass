"""Live residual benchmark: run killpass against YOUR model and measure what the
substring gate cannot catch. This is a measurement, not an accuracy rate.

    python bench/run.py                      # Ollama qwen3.5:35b, temperature 0
    python bench/run.py --model llama3.1:70b

What it reports, per residual class (negation, rumor, sarcasm, hypothetical):

    residual_false_confirm: k/n  (Wilson 95% CI)

k is how many cases where a decisive CONFIRMED survived even though the source
does not actually support the claim (the words appear, negated or hearsay). A
substring engine cannot catch these by design; killpass measures the hole rather
than faking a filter. Plus two smoke counts: true-positive not-REFUTED, and
true-negative correctly REFUTED.

What this is NOT: an accuracy percentage, a pooled score, a claim that the gate
closes negation or rumor, or a statement about any model's quality. The n is
small and printed. Re-run on your own model and read k/n, not a headline.
"""
import argparse
import json
import math
import pathlib
import sys
import urllib.request

FIX = json.loads((pathlib.Path(__file__).parent.parent / "tests" / "adversarial" / "fixtures.json").read_text())
RESIDUAL_CLASSES = ("negation", "rumor", "sarcasm", "hypothetical")


def ollama(prompt, model):
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps({"model": model, "think": False, "stream": False,
                         "options": {"temperature": 0},
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["message"]["content"]


def wilson(k, n, z=1.96):
    """Wilson score 95% interval for a proportion. Honest with tiny n."""
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:35b")
    args = ap.parse_args()

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))
    from killpass import Skeptic
    sk = Skeptic(llm=lambda p: ollama(p, args.model))

    by_class = {}
    smoke = {"true-positive": [], "true-negative": []}
    for fx in FIX:
        if fx.get("required_result"):     # mechanical fixture, asserted in CI
            continue
        v = sk.attack(fx["claim"], fx["sources"])
        cat = fx["category"]
        print(f"[{cat:13}] {fx['id']:9} -> {v.result}")
        if cat in RESIDUAL_CLASSES:
            by_class.setdefault(cat, []).append(v.result)
        elif cat in smoke:
            smoke[cat].append(v.result)

    print(f"\n=== residual measurement  model={args.model}  temp=0 ===")
    print("(k = decisive CONFIRMED that survived on an unsupported claim; not an accuracy rate)")
    for cat in RESIDUAL_CLASSES:
        rs = by_class.get(cat, [])
        n = len(rs)
        if not n:
            continue
        k = sum(1 for r in rs if r == "CONFIRMED")
        lo, hi = wilson(k, n)
        print(f"  {cat:12} residual_false_confirm: {k}/{n}   Wilson95% [{lo:.2f}, {hi:.2f}]")
    print("  (per class only; do not pool these into one score, the classes fail differently)")

    tp = smoke["true-positive"]
    tn = smoke["true-negative"]
    print("\n=== smoke counts (not rates) ===")
    print(f"  true-positive not-REFUTED: {sum(1 for r in tp if r != 'REFUTED')}/{len(tp)}")
    print(f"  true-negative REFUTED:     {sum(1 for r in tn if r == 'REFUTED')}/{len(tn)}")
    print("\nThe guarantee you can rely on is the mechanical grounding gate (CI, 48 fixtures),")
    print("not any number above. These counts describe this model on this small set only.")


if __name__ == "__main__":
    main()
