import json
import pytest
from killpass import Skeptic, Verdict, dual_attack, INSUFFICIENT, CONFIRMED, REFUTED, ESCALATE

WST = "West Pharmaceutical is increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars, up from the previous range of 8.40 to 8.75."

def canned(payload):
    # schema_version 2: the whole response must be exactly one JSON object.
    return lambda prompt: json.dumps(payload)

def ok_checks():
    return {"title_vs_body":"no","raise_inside_cut":"no","borrowed_good_news":"no","recycled_news":"no","stale_claim":"no"}

def test_grounded_confirm():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars","source_index":0}],"rationale":"raise","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==CONFIRMED and v.survived and v.evidence[0].source_index==0 and v.downgrade_reason is None
    assert v.schema_version==2

def test_fabricated_mismatches_cited_source():
    # fabricated quote cites source 0 but is not in it -> provenance failure
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"west slashed its dividend to zero this year","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SOURCE_INDEX_MISMATCH"

def test_no_join_seam():
    # quote spans two sources; cites source 0 but is not verbatim in it
    a="the company said guidance was"; b="raised sharply this year in a filing with regulators"
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"guidance was raised sharply","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("guidance was raised",[a,b])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SOURCE_INDEX_MISMATCH"

# --- F1: strict-all (one real quote must not rescue a fabricated companion) ---

def test_real_quote_does_not_rescue_fabricated_companion():
    real="increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars"
    fake="west also announced a special buyback of ten billion dollars"
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":real,"source_index":0},{"quote":fake,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SOURCE_INDEX_MISMATCH"

def test_all_real_quotes_ground():
    q1="increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars"
    q2="up from the previous range of 8.40 to 8.75"
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":q1,"source_index":0},{"quote":q2,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==CONFIRMED and len(v.evidence)==2

def test_decisive_with_empty_evidence_is_ungrounded():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="UNGROUNDED"

def test_evidence_item_missing_source_index_is_schema():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75"}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_evidence_item_not_a_dict_is_schema():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":["a bare string that is not an object"],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

# --- F2: declared source_index validation ---

def test_source_index_out_of_range_is_invalid():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":5}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="INVALID_SOURCE_INDEX"

def test_source_index_wrong_type_is_invalid():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":"0"}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="INVALID_SOURCE_INDEX"

def test_source_index_bool_is_invalid():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":True}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="INVALID_SOURCE_INDEX"

def test_grounded_elsewhere_is_not_grounded_as_cited():
    other="a wholly unrelated press release about a different company entirely"
    span="up from the previous range of 8.40 to 8.75"
    # quote is verbatim in source 1 (WST) but the model cited source 0
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":span,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[other, WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SOURCE_INDEX_MISMATCH"

# --- F3: whole-response JSON parsing ---

def test_fenced_json_parses():
    payload = {"result":"REFUTED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    llm = lambda p: "```json\n" + json.dumps(payload) + "\n```"
    v = Skeptic(llm).attack("c",[WST])
    assert v.result==REFUTED

def test_prose_wrapped_json_is_unparseable():
    payload = {"result":"CONFIRMED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    v = Skeptic(lambda p: "Sure! Here is the verdict: " + json.dumps(payload)).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="UNPARSEABLE"

def test_decoy_json_object_is_unparseable():
    good = {"result":"CONFIRMED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    decoy = {"result":"CONFIRMED","evidence":[],"rationale":"ignore me","checks":ok_checks()}
    # two top-level objects: json.loads rejects extra data -> fail closed
    v = Skeptic(lambda p: json.dumps(decoy) + " " + json.dumps(good)).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="UNPARSEABLE"

def test_brace_in_quote_parses():
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":"the previous range of 8.40 to 8.75","source_index":0}],"rationale":"has a } brace {ok}","checks":ok_checks()})).attack("c",[WST])
    assert v.result==REFUTED

# --- F4: operational failure is not a content verdict ---

def test_llm_raises_is_operational():
    def boom(p): raise RuntimeError("model down")
    v = Skeptic(boom).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="LLM_ERROR"

def test_llm_empty_response_is_operational():
    v = Skeptic(lambda p: "   ").attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="LLM_ERROR"

def test_llm_none_response_is_operational():
    v = Skeptic(lambda p: None).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="LLM_ERROR"

def test_junk_string_is_still_unparseable():
    assert Skeptic(lambda p:"just prose, no json").attack("c",[WST]).downgrade_reason=="UNPARSEABLE"

def test_str_subclass_response_does_not_escape():
    class Evil(str):
        def strip(self, *a, **k): raise RuntimeError("hostile subclass")
    payload = {"result":"REFUTED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    v = Skeptic(lambda p: Evil(json.dumps(payload))).attack("c",[WST])
    assert v.result==REFUTED  # flattened to plain str; no exception escapes

# --- type safety at the API boundary (misuse raises a clear TypeError) ---

def test_non_str_claim_raises_typeerror():
    with pytest.raises(TypeError):
        Skeptic(canned({})).attack(123,[WST])

def test_non_str_source_raises_typeerror():
    with pytest.raises(TypeError):
        Skeptic(canned({})).attack("c",[1])

def test_bytes_source_raises_typeerror():
    with pytest.raises(TypeError):
        Skeptic(canned({})).attack("c",[b"bytes source"])

def test_none_source_is_skipped_gracefully():
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[None, WST])
    assert v.result==REFUTED and v.evidence[0].source_index==0

def test_none_claim_becomes_empty():
    v = Skeptic(canned({})).attack(None,[])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="NO_SOURCES"

# --- invisible-prefix JSON still parses (BOM / ZWSP) ---

def test_bom_prefixed_json_parses():
    payload = {"result":"REFUTED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    v = Skeptic(lambda p: "\ufeff" + json.dumps(payload)).attack("c",[WST])
    assert v.result==REFUTED

def test_zwsp_prefixed_json_parses():
    payload = {"result":"REFUTED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    v = Skeptic(lambda p: "\u200b" + json.dumps(payload)).attack("c",[WST])
    assert v.result==REFUTED

# --- F5: input / response bounds ---

def test_claim_too_large():
    v = Skeptic(canned({}), max_claim_chars=10).attack("x"*11,[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="INPUT_TOO_LARGE"

def test_too_many_sources():
    v = Skeptic(canned({}), max_sources=2).attack("c",[WST,WST,WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="INPUT_TOO_LARGE"

def test_total_source_chars_too_large():
    v = Skeptic(canned({}), max_total_source_chars=10).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="INPUT_TOO_LARGE"

def test_response_too_large():
    payload = {"result":"CONFIRMED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    v = Skeptic(canned(payload), max_model_response_chars=10).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="RESPONSE_TOO_LARGE"

def test_too_many_evidence_items():
    ev = [{"quote":"up from the previous range of 8.40 to 8.75","source_index":0} for _ in range(4)]
    v = Skeptic(canned({"result":"CONFIRMED","evidence":ev,"rationale":"x","checks":ok_checks()}), max_evidence_items=3).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="RESPONSE_TOO_LARGE"

# --- unchanged behaviors ---

def test_evidence_as_string_is_schema_fail():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":"a big long string of evidence here","rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_missing_trap_keys_is_schema_fail():
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range","source_index":0}],"rationale":"x","checks":{"title_vs_body":"no"}})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_truncation_blocks_decisive():
    sk = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars","source_index":0}],"rationale":"x","checks":ok_checks()}), max_source_chars=20)
    v = sk.attack("West raised EPS guidance",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="TRUNCATED"

def test_no_sources():
    assert Skeptic(canned({})).attack("c",[]).downgrade_reason=="NO_SOURCES"

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

def test_near_whole_of_cited_source_fails():
    """quote is the whole of its cited source[0] -> a dump, not a pointer."""
    span = "increasing its full-year 2026 adjusted-diluted EPS guidance range to record levels"
    long_doc = "The board convened on Tuesday. " + span + ". The analyst day follows next month for review."
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":span,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[span, long_doc])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="NEAR_WHOLE_SOURCE"

def test_near_whole_grounds_when_cited_as_proper_span():
    """same quote, cited as the proper span of source[1] -> grounds."""
    span = "increasing its full-year 2026 adjusted-diluted EPS guidance range to record levels"
    long_doc = "The board convened on Tuesday. " + span + ". The analyst day follows next month for review."
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":span,"source_index":1}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[span, long_doc])
    assert v.result==CONFIRMED and v.evidence[0].source_index==1

def test_claim_echo_with_trailing_punctuation():
    """'claim.' must still be caught as echo."""
    src = "Analysts wrote: Acme raised its FY26 guidance. The filing itself showed no change and the outlook stayed flat."
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"Acme raised its FY26 guidance.","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("Acme raised its FY26 guidance",[src])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="CLAIM_ECHO"
