"""Mechanical adversarial pack: MUST pass in CI with a scripted LLM (no network).
The residual (negation, rumor) is measured live in bench/, not asserted here."""
import json, pathlib
import pytest
from killpass import Skeptic

FIX = json.loads((pathlib.Path(__file__).parent/"adversarial"/"fixtures.json").read_text())
MECH = [f for f in FIX if f.get("required_result")]

@pytest.mark.parametrize("fx", MECH, ids=[f["id"] for f in MECH])
def test_mechanical_pack(fx):
    v = Skeptic(lambda p, m=fx["model"]: json.dumps(m)).attack(fx["claim"], fx["sources"])
    assert v.result == fx["required_result"], f"{fx['id']}: {v.result} != {fx['required_result']}"
    if fx.get("required_downgrade_reason"):
        assert v.downgrade_reason == fx["required_downgrade_reason"], f"{fx['id']}: reason {v.downgrade_reason}"
