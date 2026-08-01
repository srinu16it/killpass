import json
from killpass import Skeptic, Verdict, dual_attack, INSUFFICIENT, CONFIRMED, REFUTED, ESCALATE

WST = "West Pharmaceutical is increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars, up from the previous range of 8.40 to 8.75."

def canned(payload):
    return lambda prompt: "noise " + json.dumps(payload) + " noise"

def ok_checks():
    return {"title_vs_body":"no","raise_inside_cut":"no","borrowed_good_news":"no","recycled_news":"no","stale_claim":"no"}

def test_grounded_confirm():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars","source_index":0}],"rationale":"raise","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==CONFIRMED and v.survived and v.evidence[0].source_index==0 and v.downgrade_reason is None

def test_fabricated_downgraded():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"west slashed its dividend to zero this year","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="UNGROUNDED"

def test_no_join_seam():
    # quote spans two sources; must NOT ground on the join
    a="the company said guidance was"; b="raised sharply this year in a filing with regulators"
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"guidance was raised sharply","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("guidance was raised",[a,b])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="UNGROUNDED"

def test_evidence_as_string_is_schema_fail():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":"a big long string of evidence here","rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_missing_trap_keys_is_schema_fail():
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range","source_index":0}],"rationale":"x","checks":{"title_vs_body":"no"}})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_brace_in_quote_parses():
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":"the previous range of 8.40 to 8.75","source_index":0}],"rationale":"has a } brace {ok}","checks":ok_checks()})).attack("c",[WST])
    assert v.result==REFUTED

def test_truncation_blocks_decisive():
    sk = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars","source_index":0}],"rationale":"x","checks":ok_checks()}), max_source_chars=20)
    v = sk.attack("West raised EPS guidance",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="TRUNCATED"

def test_no_sources():
    assert Skeptic(canned({})).attack("c",[]).downgrade_reason=="NO_SOURCES"

def test_unparseable():
    assert Skeptic(lambda p:"just prose, no json").attack("c",[WST]).downgrade_reason=="UNPARSEABLE"

def test_model_insufficient():
    v=Skeptic(canned({"result":"INSUFFICIENT","evidence":[],"rationale":"silent","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="MODEL_INSUFFICIENT"

def test_dual_escalates():
    a=Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range","source_index":0}],"rationale":"x","checks":ok_checks()}))
    b=Skeptic(canned({"result":"INSUFFICIENT","evidence":[],"rationale":"x","checks":ok_checks()}))
    assert dual_attack(a,b,"c",[WST])["result"]==ESCALATE

def test_unicode_smart_quotes_ground():
    src="West's outlook was “raised to record levels” in the filing this quarter reported."
    v=Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"raised to record levels","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("West raised outlook",[src])
    assert v.result==CONFIRMED


def test_near_whole_still_grounds_on_other_source():
    """quote is whole of source[0] but a proper span of source[1]."""
    span = "increasing its full-year 2026 adjusted-diluted EPS guidance range to record levels"
    long_doc = "The board convened on Tuesday. " + span + ". The analyst day follows next month for review."
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":span,"source_index":1}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[span, long_doc])
    assert v.result==CONFIRMED and v.evidence[0].source_index==1

def test_claim_echo_with_trailing_punctuation():
    """'claim.' must still be caught as echo."""
    src = "Analysts wrote: Acme raised its FY26 guidance. The filing itself showed no change and the outlook stayed flat."
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"Acme raised its FY26 guidance.","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("Acme raised its FY26 guidance",[src])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="CLAIM_ECHO"
