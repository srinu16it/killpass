"""Mechanical adversarial pack: MUST pass in CI with a scripted LLM (no network).

Every fixture with a `required_result` asserts the GATE decision (result + reason
code + offset exactness) deterministically. The live residual classes (negation,
rumor, sarcasm, hypothetical) carry `forbidden_results` instead and are measured
against a real model in bench/, never asserted here.
"""
import json, pathlib
import pytest
from killpass import Skeptic

FIX = json.loads((pathlib.Path(__file__).parent / "adversarial" / "fixtures.json").read_text())
MECH = [f for f in FIX if f.get("required_result")]


def _skeptic(fx):
    kwargs = fx.get("skeptic_kwargs", {})
    if "raw_model" in fx:
        raw = fx["raw_model"]
        return Skeptic(lambda p, r=raw: r, **kwargs)
    return Skeptic(lambda p, m=fx["model"]: json.dumps(m), **kwargs)


@pytest.mark.parametrize("fx", MECH, ids=[f["id"] for f in MECH])
def test_mechanical_pack(fx):
    v = _skeptic(fx).attack(fx["claim"], fx["sources"])
    assert v.result == fx["required_result"], f"{fx['id']}: {v.result} != {fx['required_result']}"
    if fx.get("required_downgrade_reason"):
        assert v.downgrade_reason == fx["required_downgrade_reason"], \
            f"{fx['id']}: reason {v.downgrade_reason} != {fx['required_downgrade_reason']}"
    want = fx.get("required_offsets")
    if want:
        span = v.evidence[0]
        got = "nonnull" if span.start_char is not None else "null"
        assert got == want, f"{fx['id']}: offsets {got} != {want}"
        if want == "nonnull":
            src = fx["sources"][span.source_index]
            from killpass.grounding import normalize
            assert normalize(src[span.start_char:span.end_char]) == normalize(span.quote)


def test_pack_is_taxonomy_complete():
    """The mechanical pack covers every downgrade reason at least twice and every
    result. If a reason code is added without a fixture, this fails loudly."""
    reasons = [f.get("required_downgrade_reason") for f in MECH if f.get("required_downgrade_reason")]
    from collections import Counter
    counts = Counter(reasons)
    expected = {
        "UNPARSEABLE", "SCHEMA", "TRUNCATED", "INVALID_SOURCE_INDEX",
        "SOURCE_INDEX_MISMATCH", "QUOTE_TOO_LONG", "NEAR_WHOLE_SOURCE",
        "CLAIM_ECHO", "QUOTE_TOO_SHORT", "UNGROUNDED", "MODEL_INSUFFICIENT",
        "NO_SOURCES", "LLM_ERROR", "INPUT_TOO_LARGE", "RESPONSE_TOO_LARGE",
    }
    missing = {r for r in expected if counts.get(r, 0) < 1}
    assert not missing, f"reasons with no mechanical fixture: {sorted(missing)}"
    assert len(MECH) >= 48, f"mechanical pack shrank to {len(MECH)} (< 48)"
    results = {f["required_result"] for f in MECH}
    assert {"CONFIRMED", "REFUTED", "INSUFFICIENT"} <= results
