"""Skeptic harness core — hardened through adversarial review.

Grounded != supported. killpass proves a verdict's evidence is a real,
non-trivial verbatim span of the source the model cited. It does NOT prove
the span supports the claim; negation/rumor/sarcasm survive the substring
engine and are measured, not hidden (tests/adversarial, SECURITY.md).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Union

from ._version import __version__
from .grounding import (
    INVALID_SOURCE_INDEX, Q_ECHO, Q_LONG, Q_NEAR_WHOLE, Q_SHORT,
    Q_UNGROUNDED, SOURCE_INDEX_MISMATCH, check_quote, locate_span, normalize,
)
from .prompts import TRAP_KEYS, build_attack_prompt

CONFIRMED, REFUTED, INSUFFICIENT = "CONFIRMED", "REFUTED", "INSUFFICIENT"
_DECISIVE = {CONFIRMED, REFUTED}
_RESULTS = {CONFIRMED, REFUTED, INSUFFICIENT}
ESCALATE = "ESCALATE"

# schema_version 3: adds optional audit fields (evidence offsets, per-source
# sha256, source manifest) on top of v2. v1/v2 reason codes and gate semantics
# are unchanged; the new fields default to null/empty when unavailable.
# Consumers pinning an older version MUST ignore unknown fields, not crash.
# See SCHEMA.md.
SCHEMA_VERSION = 3

# Operational / bound reasons: the harness could not obtain a judgeable verdict.
# These are NOT content verdicts; a crash or an oversize input is not "the
# source does not settle it."
LLM_ERROR = "LLM_ERROR"                 # the model raised, or returned empty/non-text
INPUT_TOO_LARGE = "INPUT_TOO_LARGE"     # claim/source count/total source chars over budget (pre-call)
RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"  # model response or evidence-item count over budget

# BOM and zero-width space: not whitespace to str.strip(), so a model that
# prefixes one would false-reject to UNPARSEABLE unless we strip them.
_INVISIBLE_EDGE = "\ufeff\u200b"

# Generous defaults; tune only against measured false rejects.
_MAX_CLAIM_CHARS = 20_000
_MAX_SOURCES = 32
_MAX_TOTAL_SOURCE_CHARS = 500_000
_MAX_MODEL_RESPONSE_CHARS = 100_000
_MAX_EVIDENCE_ITEMS = 16

# Severity order (highest first): the reported downgrade_reason when several
# quotes fail on the decisive path is the highest-severity one. Operational
# and bound codes are returned directly (never via this fold) but are listed
# for the documented order in SCHEMA.md.
_SEVERITY = [
    "NO_SOURCES", LLM_ERROR, INPUT_TOO_LARGE, RESPONSE_TOO_LARGE,
    "UNPARSEABLE", "SCHEMA", "TRUNCATED",
    INVALID_SOURCE_INDEX, SOURCE_INDEX_MISMATCH,
    Q_LONG, Q_NEAR_WHOLE, Q_ECHO, Q_SHORT, Q_UNGROUNDED,
    "MODEL_INSUFFICIENT",
]


@dataclass(frozen=True)
class SourceDocument:
    """Optional input wrapper: a single, already-formed source plus caller
    metadata. killpass judges `content` exactly as if it were a plain str; `id`
    and `uri` are carried through to the audit manifest and never influence the
    verdict. killpass does NOT fetch `uri` (retrieval stays in your loader, out
    of the judge)."""
    content: str
    id: Optional[str] = None
    uri: Optional[str] = None


@dataclass
class SourceRef:
    """One entry in a verdict's audit manifest: the fingerprint of a judged
    source (post-truncation, exactly what the model saw) and its echoed id/uri."""
    index: int
    sha256: str
    id: Optional[str] = None
    uri: Optional[str] = None


@dataclass
class EvidenceSpan:
    quote: str
    source_index: int
    start_char: Optional[int] = None   # offset into the ORIGINAL cited source, or None
    end_char: Optional[int] = None     # exclusive end; None when offsets are not exact
    source_sha256: Optional[str] = None  # fingerprint of the cited source


@dataclass
class Verdict:
    result: str
    evidence: List[EvidenceSpan] = field(default_factory=list)
    rationale: str = ""
    checks: dict = field(default_factory=dict)
    downgrade_reason: Optional[str] = None
    schema_version: int = SCHEMA_VERSION
    killpass_version: str = __version__
    raw: str = ""
    source_manifest: List[SourceRef] = field(default_factory=list)

    @property
    def survived(self) -> bool:
        return self.result == CONFIRMED


def _insufficient(reason: str, *, rationale: str = "", raw: str = "", checks=None,
                  manifest=None) -> Verdict:
    return Verdict(INSUFFICIENT, rationale=rationale, downgrade_reason=reason,
                   checks=checks or {}, raw=raw, source_manifest=manifest or [])


def _grounded_span(quote: str, idx: int, content: str, sha: str) -> EvidenceSpan:
    """Build the span for an already-grounded quote, attaching best-effort audit
    offsets. Isolated so an offset failure can never change the verdict: on any
    doubt the offsets are None and the span still stands (it grounded)."""
    start = end = None
    try:
        off = locate_span(content, normalize(quote))
        if off is not None:
            start, end = off
    except Exception:  # noqa: BLE001 — audit annotation must never break a verdict
        start = end = None
    return EvidenceSpan(quote=quote, source_index=idx, start_char=start,
                        end_char=end, source_sha256=sha)


def _parse_response(text: str) -> Optional[dict]:
    """Whole-response JSON: after one optional markdown fence strip, the entire
    response must be exactly one JSON object. No brace scanner, no first-object-
    wins: a decoy object or trailing model output fails closed to UNPARSEABLE.
    """
    # Strip unicode whitespace, then BOM/ZWSP that .strip() misses, then any
    # whitespace they were hiding. A model that prefixes a BOM must still parse.
    s = (text or "").strip().strip(_INVISIBLE_EDGE).strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]          # drop the opening ```lang line
        s = s.rstrip()
        if s.endswith("```"):
            s = s[:-3]              # drop the closing fence
        s = s.strip()
    try:
        obj = json.loads(s)         # json.loads rejects trailing/extra data itself
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


class Skeptic:
    """A second AI whose only job is to prove the first one wrong.

    llm: any callable prompt -> response text. killpass is the harness, not
    the brain.

    attack(claim, sources) takes a str claim and a list of str sources. A None
    claim is treated as empty and a None source is skipped (runtime data
    conditions); any other non-str raises TypeError at the boundary rather than
    failing silently.

    max_source_chars: optional per-source truncation budget (the caller's
    knowledge of the model's context). Default None = never truncate. If set
    and truncation occurs, a decisive verdict is forced to INSUFFICIENT
    (TRUNCATED) — the harness never silently judges on a partial read. This is
    distinct from the DoS bounds below: truncation reshapes the read, bounds
    reject the run.

    The remaining kwargs are generous hard bounds that reject a run outright
    rather than let the harness build a megabyte prompt or chew an unbounded
    model response. Over budget returns INPUT_TOO_LARGE (pre-call) or
    RESPONSE_TOO_LARGE (the model's output), never a content verdict.
    """

    def __init__(self, llm: Callable[[str], str], max_source_chars: Optional[int] = None,
                 *, max_claim_chars: int = _MAX_CLAIM_CHARS,
                 max_sources: int = _MAX_SOURCES,
                 max_total_source_chars: int = _MAX_TOTAL_SOURCE_CHARS,
                 max_model_response_chars: int = _MAX_MODEL_RESPONSE_CHARS,
                 max_evidence_items: int = _MAX_EVIDENCE_ITEMS):
        self.llm = llm
        self.max_source_chars = max_source_chars
        self.max_claim_chars = max_claim_chars
        self.max_sources = max_sources
        self.max_total_source_chars = max_total_source_chars
        self.max_model_response_chars = max_model_response_chars
        self.max_evidence_items = max_evidence_items

    def attack(self, claim: str, sources: "List[Union[str, SourceDocument, None]]") -> Verdict:
        # Type-misuse is a programmer error, surfaced as a clear TypeError at the
        # boundary, not an obscure AttributeError from deep inside (and not a
        # silent INSUFFICIENT that would hide the caller's bug). A None claim or
        # None source is a runtime data condition, handled gracefully below.
        if claim is None:
            claim = ""
        if not isinstance(claim, str):
            raise TypeError(f"claim must be a str, got {type(claim).__name__}")
        sources = sources if sources is not None else []
        if not isinstance(sources, (list, tuple)):
            raise TypeError(f"sources must be a list, got {type(sources).__name__}")
        # Each source is a str, a SourceDocument, or None (skipped). Anything else
        # is boundary misuse. killpass judges content only; id/uri ride to the
        # audit manifest and never touch the verdict.
        parsed: List[tuple] = []
        for s in sources:
            if s is None:
                continue
            if isinstance(s, SourceDocument):
                if not isinstance(s.content, str):
                    raise TypeError(f"SourceDocument.content must be a str, got {type(s.content).__name__}")
                parsed.append((s.content, s.id, s.uri))
            elif isinstance(s, str):
                parsed.append((s, None, None))
            else:
                raise TypeError(f"every source must be a str, SourceDocument, or None, got {type(s).__name__}")

        clean = [(c, cid, curi) for (c, cid, curi) in parsed if c and c.strip()]
        if not clean:
            return _insufficient("NO_SOURCES", rationale="No sources provided; nothing can be verified.")

        # F5 input bounds: reject oversize runs BEFORE building the prompt.
        if len(claim) > self.max_claim_chars:
            return _insufficient(INPUT_TOO_LARGE, rationale="Claim exceeds max_claim_chars.")
        if len(clean) > self.max_sources:
            return _insufficient(INPUT_TOO_LARGE, rationale="Source count exceeds max_sources.")
        if sum(len(c) for (c, _, _) in clean) > self.max_total_source_chars:
            return _insufficient(INPUT_TOO_LARGE, rationale="Total source length exceeds max_total_source_chars.")

        truncated = False
        if self.max_source_chars is not None:
            capped = []
            for c, cid, curi in clean:
                if len(c) > self.max_source_chars:
                    truncated = True
                    capped.append((c[: self.max_source_chars], cid, curi))
                else:
                    capped.append((c, cid, curi))
            clean = capped

        # The judged content (post-truncation) and its audit manifest. The hash
        # fingerprints exactly what the model saw, not the pre-truncation source.
        contents = [c for (c, _, _) in clean]
        manifest = [SourceRef(index=i, sha256=hashlib.sha256(c.encode("utf-8")).hexdigest(),
                              id=cid, uri=curi)
                    for i, (c, cid, curi) in enumerate(clean)]

        # F4 operational split: a model crash or empty response is not a content
        # verdict. A model/transport failure never escapes as an exception and is
        # never called UNPARSEABLE.
        try:
            raw = self.llm(build_attack_prompt(claim, contents, truncated=truncated))
        except Exception as e:  # noqa: BLE001 — any model/transport failure is operational
            return _insufficient(LLM_ERROR, rationale=f"Model invocation failed: {type(e).__name__}.", manifest=manifest)
        if not isinstance(raw, str):
            return _insufficient(LLM_ERROR, rationale="Model returned a non-text response.", manifest=manifest)
        raw = str(raw)  # flatten any str subclass so overridden methods can't run in parsing
        if not raw.strip():
            return _insufficient(LLM_ERROR, rationale="Model returned an empty response.", raw=raw, manifest=manifest)
        if len(raw) > self.max_model_response_chars:
            return _insufficient(RESPONSE_TOO_LARGE, rationale="Model response exceeds max_model_response_chars.",
                                 raw=raw[: self.max_model_response_chars], manifest=manifest)

        data = _parse_response(raw)
        if data is None:
            return _insufficient("UNPARSEABLE", rationale="Skeptic response was not exactly one JSON object.",
                                 raw=raw, manifest=manifest)

        # --- schema gate ---
        result = str(data.get("result", "")).upper()
        checks = data.get("checks")
        ev_raw = data.get("evidence")
        rationale = str(data.get("rationale", ""))
        if (result not in _RESULTS
                or not isinstance(ev_raw, list)
                or not isinstance(checks, dict)
                or set(checks) != set(TRAP_KEYS)
                or any(str(v).lower() not in {"yes", "no", "n/a"} for v in checks.values())):
            return _insufficient("SCHEMA", rationale="Skeptic response failed the verdict schema.",
                                 raw=raw, checks=checks if isinstance(checks, dict) else {}, manifest=manifest)
        checks = {k: str(v).lower() for k, v in checks.items()}

        if result == INSUFFICIENT:
            return Verdict(INSUFFICIENT, rationale=rationale, checks=checks,
                           downgrade_reason="MODEL_INSUFFICIENT", raw=raw, source_manifest=manifest)

        # --- decisive path ---
        if truncated:
            return _insufficient("TRUNCATED", checks=checks, raw=raw, manifest=manifest,
                                 rationale="A source was truncated to the caller's budget; decisive verdict withheld.")
        if len(ev_raw) > self.max_evidence_items:
            return _insufficient(RESPONSE_TOO_LARGE, checks=checks, raw=raw, manifest=manifest,
                                 rationale="Evidence item count exceeds max_evidence_items.")
        # F1 amend: malformed evidence is a SCHEMA failure, never a silent drop —
        # a fabricated companion that is not a well-formed item must not vanish
        # and let a real quote rescue the verdict.
        for e in ev_raw:
            if not isinstance(e, dict) or "quote" not in e or "source_index" not in e:
                return _insufficient("SCHEMA", checks=checks, raw=raw, manifest=manifest,
                                     rationale="An evidence item is missing quote or source_index.")
        if not ev_raw:
            return _insufficient(Q_UNGROUNDED, checks=checks, raw=raw, manifest=manifest,
                                 rationale="Decisive verdict carried no evidence to ground.")

        # F1 strict-all: EVERY evidence item must ground, or the whole verdict
        # downgrades. One real quote does not rescue a fabricated companion.
        norm_sources = [normalize(c) for c in contents]
        norm_claim = normalize(claim)
        spans: List[EvidenceSpan] = []
        failures: List[str] = []
        for e in ev_raw:
            q = str(e.get("quote", ""))
            idx, reason = check_quote(q, norm_sources, norm_claim, e.get("source_index"))
            if idx is not None:
                spans.append(_grounded_span(q, idx, contents[idx], manifest[idx].sha256))
            else:
                failures.append(reason)
        if failures:
            reason = min(failures, key=_SEVERITY.index)
            return _insufficient(reason, checks=checks, raw=raw, manifest=manifest,
                                 rationale="Verdict downgraded: an evidence quote failed the grounding gate.")
        return Verdict(result, evidence=spans, rationale=rationale, checks=checks, raw=raw,
                       source_manifest=manifest)


def dual_attack(skeptic_a: Skeptic, skeptic_b: Skeptic, claim: str, sources: List[str]) -> dict:
    """Two independent skeptics; disagreement returns ESCALATE (human should look).

    Agreement measures reliability of THIS run, not truth.
    """
    va, vb = skeptic_a.attack(claim, sources), skeptic_b.attack(claim, sources)
    agree = va.result == vb.result
    return {"result": va.result if agree else ESCALATE, "agree": agree, "a": va, "b": vb}
