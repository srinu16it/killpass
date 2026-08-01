"""Evaluation 1 — mechanical contract validation.

Validates what killpass's CODE guarantees, independent of any model's
intelligence. Every "model response" here is canned, so this measures the gate,
not an LLM. It says nothing about real-model behaviour (that is Evaluation 2/3,
not yet run).

The lead metric is the Unsupported Evidence Escape Rate (UEER):

    UEER = (decisive outputs carrying invalid evidence that PASSED the gate)
           / (all cases whose model proposed a decisive verdict on invalid evidence)

Target: 0. Every fixture's label is provable by construction and self-checked
before it counts, so a mislabelled fixture raises instead of corrupting a metric.

    python evals/run_mechanical.py            # ~10,500 cases, writes evals/reports/
    python evals/run_mechanical.py --n 2000   # smaller run

Reproducible: the generator is seeded, so anyone re-running gets identical cases.
A sha256 of the full serialized case set is written to the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from killpass import CONFIRMED, REFUTED, Skeptic  # noqa: E402
from killpass.grounding import is_claim_echo, normalize  # noqa: E402

DECISIVE = {CONFIRMED, REFUTED}
OK_CHECKS = {"title_vs_body": "no", "raise_inside_cut": "no", "borrowed_good_news": "no",
             "recycled_news": "no", "stale_claim": "no"}
WORDS = ("board quarter guidance outlook revenue margin filing company results raised cut "
         "unchanged record segment backlog cash debt dividend buyback forecast annual report "
         "review analyst growth decline target range earnings reported increased lowered "
         "confirmed stated noted fiscal capital expense operating investor briefing").split()

# Default per-category counts (external reviewer's taxonomy); sums to ~10,500.
COUNTS = {
    "fabricated": 1000, "wrong_source_index": 1000, "cross_source_stitch": 750,
    "claim_echo": 750, "too_short": 500, "too_long": 500, "whole_source_dump": 500,
    "multi_one_invalid": 1000, "malformed_schema": 1000, "decoy_json": 500,
    "unicode_valid": 750, "ambiguous_offsets": 500, "truncation": 500,
    "input_response_bounds": 500, "valid_control": 750,
}
# Categories whose model proposes a DECISIVE verdict on invalid/unverifiable
# evidence: the gate MUST downgrade. A decisive result here is an UEER escape.
INVALID_CATS = {"fabricated", "wrong_source_index", "cross_source_stitch", "claim_echo",
                "too_short", "too_long", "whole_source_dump", "multi_one_invalid",
                "malformed_schema", "decoy_json", "truncation", "input_response_bounds"}
# Categories whose model proposes VALID decisive evidence: the gate MUST keep it
# decisive. An INSUFFICIENT result here is a false rejection.
VALID_CATS = {"unicode_valid", "ambiguous_offsets", "valid_control"}


def sent(rng, n):
    return " ".join(rng.choice(WORDS) for _ in range(n))


def source_with(rng, span):
    return f"{sent(rng, rng.randint(6, 18))}. {span}. {sent(rng, rng.randint(6, 18))}."


def source_padded(rng, span):
    # heavily padded so the span is comfortably under half the source, keeping
    # valid controls clear of the near-whole-source threshold.
    return f"{sent(rng, rng.randint(22, 40))}. {span}. {sent(rng, rng.randint(22, 40))}."


def M(result, ev):
    return {"result": result, "evidence": ev, "rationale": "x", "checks": dict(OK_CHECKS)}


def fabricated_token(rng):
    # A sentinel guaranteed absent from any generated source (no real words).
    return "zzq" + "".join(rng.choice("0123456789abcdef") for _ in range(10)) + " sentinel absent line"


def gen_case(cat, i, rng):
    """Return a case dict. Each carries `expect`: 'insufficient' (invalid, must be
    caught) or 'decisive' (valid, must pass), plus optional expected_reason and
    offset expectation. Labels are enforced by _self_check below."""
    dec = rng.choice([CONFIRMED, REFUTED])
    if cat == "fabricated":
        real = sent(rng, rng.randint(6, 12))
        src = source_with(rng, real)
        fake = fabricated_token(rng)
        return dict(cat=cat, claim=sent(rng, 5), sources=[src],
                    model=M(dec, [{"quote": fake, "source_index": 0}]),
                    expect="insufficient", expected_reason="SOURCE_INDEX_MISMATCH")
    if cat == "wrong_source_index":
        span = sent(rng, rng.randint(6, 12))
        s0 = source_with(rng, sent(rng, 10))     # unrelated
        s1 = source_with(rng, span)              # holds the span
        return dict(cat=cat, claim=sent(rng, 5), sources=[s0, s1],
                    model=M(dec, [{"quote": span, "source_index": 0}]),  # cite 0, it's in 1
                    expect="insufficient", expected_reason="SOURCE_INDEX_MISMATCH")
    if cat == "cross_source_stitch":
        a, b = sent(rng, 5), sent(rng, 5)
        sa, sb = source_with(rng, a), source_with(rng, b)
        stitched = a + " " + b                   # verbatim in neither
        return dict(cat=cat, claim=sent(rng, 5), sources=[sa, sb],
                    model=M(dec, [{"quote": stitched, "source_index": 0}]),
                    expect="insufficient", expected_reason="SOURCE_INDEX_MISMATCH")
    if cat == "claim_echo":
        claim = sent(rng, rng.randint(4, 8))
        src = source_with(rng, claim)            # claim text present, but echo fires first
        quote = claim if rng.random() < 0.5 else " ".join(claim.split()[:max(3, len(claim.split()) - 1)])
        return dict(cat=cat, claim=claim, sources=[src],
                    model=M(dec, [{"quote": quote, "source_index": 0}]),
                    expect="insufficient", expected_reason="CLAIM_ECHO")
    if cat == "too_short":
        quote = sent(rng, 1)[:rng.randint(3, 11)]  # < 12 chars
        return dict(cat=cat, claim=sent(rng, 5), sources=[source_with(rng, sent(rng, 8))],
                    model=M(dec, [{"quote": quote, "source_index": 0}]),
                    expect="insufficient", expected_reason="QUOTE_TOO_SHORT")
    if cat == "too_long":
        long_span = (sent(rng, 90) + " ")[:rng.randint(520, 700)]
        src = sent(rng, 40) + ". " + long_span + ". " + sent(rng, 40)
        return dict(cat=cat, claim=sent(rng, 5), sources=[src],
                    model=M(dec, [{"quote": long_span, "source_index": 0}]),
                    expect="insufficient", expected_reason="QUOTE_TOO_LONG")
    if cat == "whole_source_dump":
        # sent() text is normalization-identity (lowercase, single spaces), so raw
        # length == normalized length. Source in [520, 720] chars: >=500 (so the
        # 0.5 alpha applies) and small enough that a quote >=50% still fits <=495
        # (else QUOTE_TOO_LONG would fire first).
        target = rng.randint(520, 720)
        src = ""
        while len(src) < target:
            src += sent(rng, 10) + " "
        src = src[:target].rstrip()
        qlen = rng.randint(int(len(src) * 0.55), min(495, int(len(src) * 0.85)))
        quote = src[:qlen].rstrip()
        return dict(cat=cat, claim=sent(rng, 5), sources=[src],
                    model=M(dec, [{"quote": quote, "source_index": 0}]),
                    expect="insufficient", expected_reason="NEAR_WHOLE_SOURCE")
    if cat == "multi_one_invalid":
        good = sent(rng, rng.randint(6, 12))
        src = source_with(rng, good)
        fake = fabricated_token(rng)
        ev = [{"quote": good, "source_index": 0}, {"quote": fake, "source_index": 0}]
        rng.shuffle(ev)
        return dict(cat=cat, claim=sent(rng, 5), sources=[src], model=M(dec, ev),
                    expect="insufficient", expected_reason="SOURCE_INDEX_MISMATCH")
    if cat == "malformed_schema":
        src = source_with(rng, sent(rng, 8))
        kind = i % 5
        if kind == 0:
            model = {"result": dec, "evidence": "a string not a list", "rationale": "x", "checks": dict(OK_CHECKS)}
        elif kind == 1:
            model = {"result": dec, "evidence": [{"quote": sent(rng, 6), "source_index": 0}],
                     "rationale": "x", "checks": {"title_vs_body": "no"}}          # missing keys
        elif kind == 2:
            model = {"result": dec, "evidence": [{"quote": 123456789012, "source_index": 0}],
                     "rationale": "x", "checks": dict(OK_CHECKS)}                   # non-str quote
        elif kind == 3:
            model = {"result": dec, "evidence": [{"quote": sent(rng, 6)}],
                     "rationale": "x", "checks": dict(OK_CHECKS)}                   # missing source_index
        else:
            model = {"result": 12345, "evidence": [], "rationale": "x", "checks": dict(OK_CHECKS)}  # non-str result
        return dict(cat=cat, claim=sent(rng, 5), sources=[src], model=model,
                    expect="insufficient", expected_reason="SCHEMA")
    if cat == "decoy_json":
        src = source_with(rng, sent(rng, 8))
        good = json.dumps(M(dec, [{"quote": sent(rng, 6), "source_index": 0}]))
        decoy = json.dumps(M(CONFIRMED, []))
        variant = i % 3
        if variant == 0:
            raw = decoy + " " + good
        elif variant == 1:
            raw = good + " trailing model chatter here"
        else:
            raw = "Sure, here you go: " + good
        return dict(cat=cat, claim=sent(rng, 5), sources=[src], raw_model=raw,
                    expect="insufficient", expected_reason="UNPARSEABLE")
    if cat == "unicode_valid":
        # a legit span, then a unicode variant that normalizes BACK to it (so it
        # still grounds against the plain source). Tests we do not false-reject.
        plain = sent(rng, rng.randint(6, 10))
        src = source_padded(rng, plain)
        variant = i % 4
        if variant == 0:
            quote = plain.upper()                          # casefold -> plain
        elif variant == 1:
            quote = plain.replace(" ", "\u00a0", 1)        # NBSP -> space
        elif variant == 2:
            quote = plain[:1] + "\u200b" + plain[1:]        # ZWSP deleted
        else:
            quote = plain.upper().replace(" ", "\u00a0", 1) # both
        return dict(cat=cat, claim=sent(rng, 5), sources=[src],
                    model=M(dec, [{"quote": quote, "source_index": 0}]),
                    expect="decisive")

    if cat == "ambiguous_offsets":
        span = sent(rng, rng.randint(6, 10))
        src = f"{sent(rng, 6)}. {span}. {sent(rng, 4)}. {span}. {sent(rng, 6)}."  # appears twice
        return dict(cat=cat, claim=sent(rng, 5), sources=[src],
                    model=M(dec, [{"quote": span, "source_index": 0}]),
                    expect="decisive", offset="null")
    if cat == "truncation":
        span = sent(rng, rng.randint(8, 14))
        src = sent(rng, 30) + ". " + span + ". " + sent(rng, 30)
        cap = rng.randint(20, 40)
        return dict(cat=cat, claim=sent(rng, 5), sources=[src],
                    model=M(dec, [{"quote": span, "source_index": 0}]),
                    skeptic_kwargs={"max_source_chars": cap},
                    expect="insufficient", expected_reason="TRUNCATED")
    if cat == "input_response_bounds":
        src = source_with(rng, sent(rng, 8))
        variant = i % 3
        if variant == 0:
            return dict(cat=cat, claim="x" * rng.randint(30, 60), sources=[src],
                        model=M(dec, [{"quote": sent(rng, 6), "source_index": 0}]),
                        skeptic_kwargs={"max_claim_chars": 10},
                        expect="insufficient", expected_reason="INPUT_TOO_LARGE")
        elif variant == 1:
            return dict(cat=cat, claim=sent(rng, 5), sources=[src, src, src],
                        model=M(dec, [{"quote": sent(rng, 6), "source_index": 0}]),
                        skeptic_kwargs={"max_sources": 2},
                        expect="insufficient", expected_reason="INPUT_TOO_LARGE")
        else:
            ev = [{"quote": sent(rng, 6), "source_index": 0} for _ in range(4)]
            return dict(cat=cat, claim=sent(rng, 5), sources=[src], model=M(dec, ev),
                        skeptic_kwargs={"max_evidence_items": 2},
                        expect="insufficient", expected_reason="RESPONSE_TOO_LARGE")
    if cat == "valid_control":
        span = sent(rng, rng.randint(6, 14))
        n_src = rng.randint(1, 3)
        idx = rng.randint(0, n_src - 1)
        sources = [source_padded(rng, sent(rng, 8)) for _ in range(n_src)]
        sources[idx] = source_padded(rng, span)
        return dict(cat=cat, claim=sent(rng, 5), sources=sources,
                    model=M(dec, [{"quote": span, "source_index": idx}]),
                    expect="decisive", offset="nonnull")
    raise ValueError(cat)


def _self_check(c):
    """Prove the case's LABEL by construction before it counts. Raises on any
    mislabel, so a generator bug cannot silently inflate or deflate a metric."""
    cat, srcs = c["cat"], c["sources"]
    nsrcs = [normalize(s) for s in srcs]
    m = c.get("model")
    if cat == "fabricated":
        q = normalize(m["evidence"][0]["quote"])
        assert all(q not in ns for ns in nsrcs), "fabricated quote must be absent from all sources"
    elif cat == "wrong_source_index":
        q = normalize(m["evidence"][0]["quote"])
        assert q not in nsrcs[0] and q in nsrcs[1], "wrong-index quote must be in cited-wrong source only"
    elif cat == "cross_source_stitch":
        q = normalize(m["evidence"][0]["quote"])
        assert all(q not in ns for ns in nsrcs), "stitched quote must be verbatim in no single source"
    elif cat == "claim_echo":
        assert is_claim_echo(normalize(m["evidence"][0]["quote"]), normalize(c["claim"])), "must be a claim echo"
    elif cat == "too_short":
        assert len(normalize(m["evidence"][0]["quote"])) < 12, "quote must be under the min length"
    elif cat == "too_long":
        assert len(normalize(m["evidence"][0]["quote"])) > 500, "quote must exceed the max length"
    elif cat == "whole_source_dump":
        q = normalize(m["evidence"][0]["quote"])
        assert q in nsrcs[0] and len(q) >= 0.5 * len(nsrcs[0]) and len(q) <= 500, "must be a near-whole dump"
    elif cat == "unicode_valid" or cat == "valid_control":
        e = m["evidence"][0]
        q = normalize(e["quote"])
        ns = nsrcs[e["source_index"]]
        assert q in ns and 12 <= len(q) <= 500 and len(q) < 0.5 * len(ns), "valid control must ground cleanly"
    elif cat == "ambiguous_offsets":
        q = normalize(m["evidence"][0]["quote"])
        assert nsrcs[0].count(q) >= 2, "ambiguous case must occur 2+ times"
    elif cat == "truncation":
        assert len(srcs[0]) > c["skeptic_kwargs"]["max_source_chars"], "source must exceed the truncation cap"


def build(counts, seed):
    rng = random.Random(seed)
    cases = []
    for cat, n in counts.items():
        for i in range(n):
            c = gen_case(cat, i, rng)
            c["id"] = f"{cat}-{i}"
            _self_check(c)
            cases.append(c)
    rng.shuffle(cases)
    return cases


def run_case(c):
    kwargs = c.get("skeptic_kwargs", {})
    if "raw_model" in c:
        raw = c["raw_model"]
        sk = Skeptic(lambda p, r=raw: r, **kwargs)
    else:
        model = c["model"]
        sk = Skeptic(lambda p, m=model: json.dumps(m), **kwargs)
    return sk.attack(c["claim"], c["sources"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None, help="cap total cases (scales each category)")
    ap.add_argument("--seed", type=int, default=20260801)
    args = ap.parse_args()

    counts = dict(COUNTS)
    if args.n:
        scale = args.n / sum(COUNTS.values())
        counts = {k: max(1, int(v * scale)) for k, v in COUNTS.items()}

    cases = build(counts, args.seed)
    fingerprint = hashlib.sha256(
        "\n".join(json.dumps({k: c[k] for k in ("cat", "claim", "sources", "id")}, sort_keys=True)
                  for c in cases).encode()).hexdigest()

    # --- run + score ---
    invalid_total = invalid_escapes = 0
    valid_total = valid_false_reject = 0
    reason_total = reason_correct = 0
    offset_checked = offset_wrong = 0
    exceptions = 0
    per_cat = {}
    escape_examples, reject_examples = [], []

    for c in cases:
        cat = c["cat"]
        pc = per_cat.setdefault(cat, {"n": 0, "fail": 0})
        pc["n"] += 1
        try:
            v = run_case(c)
        except Exception:  # noqa: BLE001 — an uncaught exception is itself a failure to report
            exceptions += 1
            pc["fail"] += 1
            continue
        decisive = v.result in DECISIVE

        if c["expect"] == "insufficient":       # invalid evidence: must be caught
            invalid_total += 1
            if decisive:
                invalid_escapes += 1
                pc["fail"] += 1
                if len(escape_examples) < 8:
                    escape_examples.append({"id": c["id"], "cat": cat, "result": v.result})
            if c.get("expected_reason"):
                reason_total += 1
                if v.downgrade_reason == c["expected_reason"]:
                    reason_correct += 1
                else:
                    pc["fail"] += 1
        else:                                     # valid: must stay decisive
            valid_total += 1
            if not decisive:
                valid_false_reject += 1
                pc["fail"] += 1
                if len(reject_examples) < 8:
                    reject_examples.append({"id": c["id"], "cat": cat, "reason": v.downgrade_reason})
            elif c.get("offset") is not None:
                offset_checked += 1
                span = v.evidence[0]
                got = "nonnull" if span.start_char is not None else "null"
                if got != c["offset"]:
                    offset_wrong += 1
                    pc["fail"] += 1
                elif got == "nonnull":
                    src = c["sources"][span.source_index]
                    if normalize(src[span.start_char:span.end_char]) != normalize(span.quote):
                        offset_wrong += 1
                        pc["fail"] += 1

    def rule_of_three(n):     # 95% upper bound on a rate observed as 0/n
        return 3.0 / n if n else float("nan")

    frr = valid_false_reject / valid_total if valid_total else 0.0
    reason_acc = reason_correct / reason_total if reason_total else 0.0

    reports = ROOT / "evals" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    # sample of cases for inspection
    (reports / "mechanical_sample.jsonl").write_text(
        "\n".join(json.dumps({k: c.get(k) for k in ("id", "cat", "claim", "sources", "expect", "expected_reason")})
                  for c in cases[:120]))
    # per-category CSV
    (reports / "mechanical_category_metrics.csv").write_text(
        "category,n,failures\n" + "\n".join(f"{k},{v['n']},{v['fail']}" for k, v in sorted(per_cat.items())))

    lines = []
    lines.append("# Evaluation 1 — mechanical contract validation")
    lines.append("")
    lines.append(f"- cases: **{len(cases)}**  (seed {args.seed}; dataset sha256 `{fingerprint[:16]}…`)")
    lines.append("- canned model output; no LLM was called. This measures the gate, not a model.")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"**Mechanical UEER (generated fixtures, canned output, no LLM): "
                 f"{invalid_escapes} escapes out of {invalid_total} invalid-evidence cases.**")
    if invalid_escapes == 0:
        lines.append(f"Rule-of-three 95% upper bound ≈ {rule_of_three(invalid_total)*100:.3f}% "
                     "**on this generated distribution only** (not a claim about real-model "
                     "deployments or residual classes the gate does not target).")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("All figures are on generated fixtures with canned model output (no LLM); "
                 "\"fixture target\" is the bar for the gate's code, not an accuracy claim.")
    lines.append("")
    lines.append("| metric (generated fixtures) | value | fixture target |")
    lines.append("|---|---|---|")
    lines.append(f"| invalid-evidence escape rate (UEER) | {invalid_escapes}/{invalid_total} | 0 |")
    lines.append(f"| valid-evidence false-rejection rate | {valid_false_reject}/{valid_total} | <0.5% |")
    lines.append(f"| correct downgrade reason | {reason_correct}/{reason_total} | >99% |")
    lines.append(f"| incorrect non-null offsets | {offset_wrong}/{offset_checked} | 0 |")
    lines.append(f"| uncaught exceptions | {exceptions}/{len(cases)} | 0 |")
    lines.append("")
    lines.append("## Per-category (failures should be 0)")
    lines.append("")
    lines.append("| category | n | failures |")
    lines.append("|---|---|---|")
    for k, v in sorted(per_cat.items()):
        lines.append(f"| {k} | {v['n']} | {v['fail']} |")
    lines.append("")
    if escape_examples:
        lines.append("### UEER escapes (should be empty)")
        for e in escape_examples:
            lines.append(f"- {e}")
    if reject_examples:
        lines.append("### false rejections (should be empty)")
        for e in reject_examples:
            lines.append(f"- {e}")
    lines.append("")
    lines.append("## Scope and honesty")
    lines.append("")
    lines.append("This validates the harness's mechanical guarantee ONLY. It says nothing about "
                 "whether a real model returns good evidence, nor about incremental value over a "
                 "plain prompt — those are Evaluation 2 (incremental lift) and Evaluation 3 "
                 "(end-to-end decision quality with human labels), which are NOT yet run. Fixtures "
                 "are systematically generated and self-checked by construction, not hand-audited.")
    report = "\n".join(lines)
    (reports / "mechanical_report.md").write_text(report + "\n")

    print(report)
    ok = (invalid_escapes == 0 and offset_wrong == 0 and exceptions == 0
          and frr < 0.005 and reason_acc > 0.99)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
