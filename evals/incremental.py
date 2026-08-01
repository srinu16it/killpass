"""Evaluation 2 — incremental value over simpler alternatives.

The question a developer actually asks: "why not just tell the LLM to cite its
source?" This compares three arms on the SAME claims, sources, and model:

  A  ordinary   a plain "check the claim and cite evidence" prompt
  B  refute     the killpass refute-first prompt, but NO mechanical gate
  C  killpass   the refute-first prompt PLUS the mechanical grounding gate

Primary endpoint: invalid-evidence escape rate per arm. An arm's decisive output
"escapes" if it names evidence that FAILS the same mechanical grounding check
(fabricated / misattributed / stitched across sources / claim echo / whole
dump / too short / too long). One referee — killpass.grounding — scores every
arm identically, so C is 0 by construction and A/B expose what prompting alone
lets through. The gap between them is the value killpass adds.

STATUS: framework only, NOT YET RUN as a study. A credible result needs the plan
in evals/README.md (>=5 models, >=1000 labeled claims, 3 repetitions ~ 45k model
calls). This module IS runnable against any model callable so the harness can be
smoke-tested and then scaled:

    from evals.incremental import run_study
    report = run_study(cases, my_llm, reps=1)   # cases: see incremental_seed.jsonl

No numbers are reported here until a real study is run. Do not publish the seed
smoke output as a result.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from killpass import CONFIRMED, INSUFFICIENT, REFUTED, Skeptic  # noqa: E402
from killpass.core import _parse_response  # noqa: E402
from killpass.grounding import check_quote, normalize  # noqa: E402
from killpass.prompts import build_attack_prompt  # noqa: E402

DECISIVE = {CONFIRMED, REFUTED}
_ORDINARY = """Check whether the CLAIM is supported by the SOURCES. Use only the sources.
CLAIM: {claim}
SOURCES:
{sources}
Respond with ONLY this JSON: {{"result": "CONFIRMED|REFUTED|INSUFFICIENT", "evidence": [{{"quote": "verbatim span from a source", "source_index": 0}}]}}"""


def _norm_verdict(obj):
    """Pull a (result, evidence) pair out of an arm's raw model JSON, tolerantly."""
    if not isinstance(obj, dict):
        return INSUFFICIENT, []
    r = str(obj.get("result", "")).upper()
    r = r if r in (CONFIRMED, REFUTED, INSUFFICIENT) else INSUFFICIENT
    ev = obj.get("evidence")
    ev = ev if isinstance(ev, list) else []
    return r, ev


def _evidence_is_valid(result, evidence, claim, sources):
    """The shared referee: does this decisive output rest only on evidence that
    passes the mechanical grounding gate? Applied identically to every arm."""
    if result not in DECISIVE:
        return None                      # abstained: not an escape either way
    if not evidence:
        return False                     # decisive with no evidence
    norm_sources = [normalize(s) for s in sources]
    norm_claim = normalize(claim)
    for e in evidence:
        if not isinstance(e, dict) or not isinstance(e.get("quote"), str) or "source_index" not in e:
            return False
        idx, reason = check_quote(e["quote"], norm_sources, norm_claim, e.get("source_index"))
        if idx is None:
            return False
    return True


def arm_ordinary(llm, claim, sources):
    prompt = _ORDINARY.format(claim=claim, sources="\n".join(f"[{i}] {s}" for i, s in enumerate(sources)))
    result, ev = _norm_verdict(_parse_response(llm(prompt)))
    return result, ev


def arm_refute(llm, claim, sources):
    # same skeptic prompt as killpass, but the model's proposal is taken raw (no gate)
    result, ev = _norm_verdict(_parse_response(llm(build_attack_prompt(claim, sources))))
    return result, ev


def arm_killpass(llm, claim, sources):
    v = Skeptic(llm).attack(claim, sources)
    return v.result, [{"quote": s.quote, "source_index": s.source_index} for s in v.evidence]


ARMS = {"ordinary": arm_ordinary, "refute": arm_refute, "killpass": arm_killpass}


def run_study(cases, llm, reps=1):
    """cases: list of {claim, sources, gold?}. Returns per-arm metrics. Scores
    every arm with the same mechanical referee. No model quality is inferred —
    this measures evidence-integrity escapes, coverage, and (if gold present)
    confirmation precision."""
    stats = {a: {"decisive": 0, "escapes": 0, "total": 0, "confirmed": 0, "confirmed_correct": 0}
             for a in ARMS}
    for case in cases:
        claim, sources = case["claim"], case["sources"]
        gold = case.get("gold")            # optional: SUPPORTED|REFUTED|INSUFFICIENT
        for _ in range(reps):
            for name, fn in ARMS.items():
                st = stats[name]
                st["total"] += 1
                try:
                    result, ev = fn(llm, claim, sources)
                except Exception:          # noqa: BLE001 — an arm crashing counts as no decisive
                    continue
                valid = _evidence_is_valid(result, ev, claim, sources)
                if result in DECISIVE:
                    st["decisive"] += 1
                    if valid is False:
                        st["escapes"] += 1
                    if result == CONFIRMED:
                        st["confirmed"] += 1
                        if gold == "SUPPORTED":
                            st["confirmed_correct"] += 1
    out = {}
    for name, st in stats.items():
        t, d = st["total"], st["decisive"]
        out[name] = {
            "invalid_evidence_escape_rate": (st["escapes"] / d) if d else 0.0,
            "escapes": st["escapes"],
            "decisive_coverage": (d / t) if t else 0.0,
            "confirmation_precision": (st["confirmed_correct"] / st["confirmed"]) if st["confirmed"] else None,
            "n": t,
        }
    return out


def _seed_cases():
    p = ROOT / "evals" / "datasets" / "incremental_seed.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


if __name__ == "__main__":
    # Smoke-test the harness against a scripted model (NOT a study, NOT a result).
    # Demonstrates the referee: a "sloppy prompt-only" model that fabricates a
    # quote escapes arms A/B but is caught by the killpass gate (arm C).
    cases = _seed_cases()
    good = cases[0]
    span = good["sources"][0].split(". ")[1]
    fabricated = json.dumps({"result": "CONFIRMED",
                             "evidence": [{"quote": "a fabricated line not in any source at all",
                                           "source_index": 0}]})

    def sloppy_llm(_prompt):
        return fabricated       # every arm sees a fabricated decisive proposal

    res = run_study([good], sloppy_llm, reps=1)
    print("HARNESS SMOKE (scripted fabricating model; NOT a study):")
    for arm, m in res.items():
        print(f"  {arm:9} escapes={m['escapes']}  escape_rate={m['invalid_evidence_escape_rate']:.2f}  "
              f"coverage={m['decisive_coverage']:.2f}")
    print("Expected shape: ordinary/refute escape (>0), killpass escapes=0 (gate). "
          "This is a wiring check, not evidence of value.")
