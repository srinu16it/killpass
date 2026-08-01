import hashlib
import json

import pytest

from killpass import CONFIRMED, ESCALATE, INSUFFICIENT, REFUTED, Skeptic, SourceDocument, dual_attack

WST = "West Pharmaceutical is increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars, up from the previous range of 8.40 to 8.75."

def canned(payload):
    # schema_version 2: the whole response must be exactly one JSON object.
    return lambda prompt: json.dumps(payload)

def ok_checks():
    return {"title_vs_body":"no","raise_inside_cut":"no","borrowed_good_news":"no","recycled_news":"no","stale_claim":"no"}

def test_grounded_confirm():
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"increasing its full-year 2026 adjusted-diluted EPS guidance range to 8.85 to 9.05 dollars","source_index":0}],"rationale":"raise","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==CONFIRMED and v.survived and v.evidence[0].source_index==0 and v.downgrade_reason is None
    assert v.schema_version==4

def test_fabricated_mismatches_cited_source():
    # fabricated quote cites source 0 but is not in it -> provenance failure
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":"west slashed its dividend to zero this year","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("West raised EPS guidance",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SOURCE_INDEX_MISMATCH"

def test_no_join_seam():
    # quote spans two sources; cites source 0 but is not verbatim in it
    a="the company said guidance was"
    b="raised sharply this year in a filing with regulators"
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
    def llm(p): return "```json\n" + json.dumps(payload) + "\n```"
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

# --- v1.0.1: correctness patch (external review) ---

def test_offsets_null_for_overlapping_matches():
    """str.count is non-overlapping; 'aaa...' with a shorter 'aa...' quote is NOT
    a unique locus and must yield null offsets, not the first position."""
    from killpass.grounding import locate_span, normalize
    src = "a" * 23
    assert locate_span(src, normalize("a" * 12)) is None

def test_numeric_quote_is_schema_not_grounded():
    """A non-string quote must fail as SCHEMA, never be str()-coerced into a
    span that could ground (e.g. a numeric code that appears in the source)."""
    src = "The report reference code is 123456789012 in the filing appendix here now today."
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":123456789012,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[src])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_malformed_evidence_on_insufficient_is_schema():
    """Evidence structure is validated before branching on result: a malformed
    item cannot ride through on the INSUFFICIENT path as MODEL_INSUFFICIENT."""
    v = Skeptic(canned({"result":"INSUFFICIENT","evidence":[123, None, {"wrong":"shape"}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_wellformed_evidence_on_insufficient_still_model_insufficient():
    """A well-formed evidence item on INSUFFICIENT is fine (validation does not
    over-reject); it stays MODEL_INSUFFICIENT."""
    v = Skeptic(canned({"result":"INSUFFICIENT","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="MODEL_INSUFFICIENT"

def test_non_str_result_is_schema():
    v = Skeptic(canned({"result":123,"evidence":[],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.result==INSUFFICIENT and v.downgrade_reason=="SCHEMA"

def test_constructor_rejects_bad_limits():
    for bad in ({"max_sources":-1}, {"max_sources":0}, {"max_evidence_items":True},
                {"max_claim_chars":"5"}, {"max_source_chars":0}, {"max_source_chars":-3}):
        with pytest.raises(ValueError):
            Skeptic(canned({}), **bad)
    # None is allowed only for max_source_chars (the truncation budget)
    Skeptic(canned({}), max_source_chars=None)
    with pytest.raises(ValueError):
        Skeptic(canned({}), max_sources=None)

# --- v0.4: provenance / audit (schema v3) ---

def _sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()

def test_schema_version_is_4():
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.schema_version==4

# --- v1.2.0: run_metadata (echo-only provenance, schema v4) ---

def test_run_metadata_echoed_into_verdict():
    sk = Skeptic(canned({"result":"INSUFFICIENT","evidence":[],"rationale":"x","checks":ok_checks()}),
                 run_metadata={"model":"qwen3.5:35b","run_id":"r-42"})
    v = sk.attack("c",[WST])
    assert v.run_metadata == {"model":"qwen3.5:35b","run_id":"r-42"}

def test_run_metadata_defaults_none():
    v = Skeptic(canned({"result":"INSUFFICIENT","evidence":[],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.run_metadata is None

def test_run_metadata_is_copied_not_shared():
    md = {"model":"m", "tags":["a"]}   # includes a nested mutable
    sk = Skeptic(canned({"result":"INSUFFICIENT","evidence":[],"rationale":"x","checks":ok_checks()}), run_metadata=md)
    v = sk.attack("c",[WST])
    md["model"] = "mutated"
    md["tags"].append("b")             # nested mutation must not reach the verdict
    assert v.run_metadata == {"model":"m", "tags":["a"]}   # deep snapshot

def test_run_metadata_never_influences_verdict():
    # decisive verdict is unchanged whether or not run_metadata is present
    payload = {"result":"REFUTED","evidence":[{"quote":"up from the previous range of 8.40 to 8.75","source_index":0}],"rationale":"x","checks":ok_checks()}
    a = Skeptic(canned(payload)).attack("c",[WST])
    b = Skeptic(canned(payload), run_metadata={"model":"m"}).attack("c",[WST])
    assert a.result==b.result==REFUTED and a.downgrade_reason==b.downgrade_reason

def test_run_metadata_bad_type_raises():
    with pytest.raises(TypeError):
        Skeptic(canned({}), run_metadata=["not","a","dict"])
    with pytest.raises(TypeError):
        Skeptic(canned({}), run_metadata={1:"non-string-key"})

def test_offsets_point_to_original_span():
    span="up from the previous range of 8.40 to 8.75"
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":span,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    e = v.evidence[0]
    assert e.start_char is not None and WST[e.start_char:e.end_char]==span

def test_offsets_null_when_ambiguous_but_still_grounds():
    src="repeat this exact phrase and later repeat this exact phrase once more here now"
    q="repeat this exact phrase"
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":q,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[src])
    assert v.result==REFUTED and v.evidence[0].start_char is None and v.evidence[0].end_char is None

def test_offsets_handle_normalized_span():
    # smart quotes + case differ from the raw quote; offsets map to the ORIGINAL
    src='The board said the outlook was “RAISED to Record Levels” in the filing this quarter here.'
    q="raised to record levels"
    v = Skeptic(canned({"result":"CONFIRMED","evidence":[{"quote":q,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[src])
    e = v.evidence[0]
    from killpass.grounding import normalize
    assert e.start_char is not None and normalize(src[e.start_char:e.end_char])==normalize(q)

def test_source_sha256_on_span_and_manifest():
    span="up from the previous range of 8.40 to 8.75"
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":span,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[WST])
    assert v.evidence[0].source_sha256==_sha(WST)
    assert len(v.source_manifest)==1 and v.source_manifest[0].sha256==_sha(WST) and v.source_manifest[0].index==0

def test_manifest_hashes_the_truncated_judged_string():
    sk = Skeptic(canned({"result":"INSUFFICIENT","evidence":[],"rationale":"x","checks":ok_checks()}), max_source_chars=20)
    v = sk.attack("c",[WST])
    assert v.source_manifest[0].sha256==_sha(WST[:20])   # hash of what the model saw, not the full source

def test_source_document_input_carries_id_and_uri():
    span="up from the previous range of 8.40 to 8.75"
    doc = SourceDocument(content=WST, id="doc-1", uri="https://example.test/wst")
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":span,"source_index":0}],"rationale":"x","checks":ok_checks()})).attack("c",[doc])
    assert v.result==REFUTED
    ref = v.source_manifest[0]
    assert ref.id=="doc-1" and ref.uri=="https://example.test/wst" and ref.sha256==_sha(WST)

def test_source_document_and_str_mixed():
    span="up from the previous range of 8.40 to 8.75"
    v = Skeptic(canned({"result":"REFUTED","evidence":[{"quote":span,"source_index":1}],"rationale":"x","checks":ok_checks()})).attack("c",["unrelated first source text here", SourceDocument(content=WST, id="d2")])
    assert v.result==REFUTED and v.evidence[0].source_index==1 and v.source_manifest[1].id=="d2"

def test_source_document_non_str_content_raises():
    with pytest.raises(TypeError):
        Skeptic(canned({})).attack("c",[SourceDocument(content=123)])

def test_locate_span_never_emits_a_wrong_offset_property():
    """Property: any non-null (s,e) from locate_span must re-normalize to the
    quote, over a fuzz of adversarial unicode. Exact-or-null, by construction."""
    import random

    from killpass.grounding import _normalize_with_map, locate_span, normalize
    alphabet = list("abcAB 12.,") + ["́","̣","​","﻿","ß","é",
                                      "½","’","—","Ａ","\t","  ","ẞ"]
    rng = random.Random(20260801)
    emits = 0
    for _ in range(5000):
        src = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 22)))
        assert _normalize_with_map(src)[0] == normalize(src)   # map integrity
        ns = normalize(src)
        if ns and rng.random() < 0.7 and len(ns) >= 2:
            a = rng.randint(0, len(ns)-1)
            b = rng.randint(a+1, len(ns))
            nq = ns[a:b]
        else:
            nq = normalize("".join(rng.choice(alphabet) for _ in range(rng.randint(1,5))))
        off = locate_span(src, nq)
        if off is None:
            continue
        emits += 1
        s, e = off
        assert 0 <= s < e <= len(src)
        assert normalize(src[s:e]) == nq
    assert emits > 0   # the fuzz actually exercised the emit path

def test_offsets_never_change_the_verdict_invariance():
    # identical result/reason/quote/source_index whether or not offsets resolve
    span="up from the previous range of 8.40 to 8.75"
    payload={"result":"CONFIRMED","evidence":[{"quote":span,"source_index":0}],"rationale":"x","checks":ok_checks()}
    v = Skeptic(canned(payload)).attack("c",[WST])
    import killpass.core as core
    orig = core.locate_span
    try:
        core.locate_span = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offset engine down"))
        v2 = Skeptic(canned(payload)).attack("c",[WST])
    finally:
        core.locate_span = orig
    assert v.result==v2.result==CONFIRMED
    assert (v2.evidence[0].quote, v2.evidence[0].source_index)==(span,0)
    assert v2.evidence[0].start_char is None  # engine down -> null offsets, verdict intact
