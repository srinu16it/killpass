"""Skeptic harness core — hardened through adversarial review.

Grounded != supported. killpass proves a verdict's evidence is a real,
non-trivial verbatim span of a source. It does NOT prove the span supports
the claim; negation/rumor/sarcasm survive the substring engine and are
measured, not hidden (tests/adversarial, SECURITY.md).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ._version import __version__
from .grounding import (
    Q_ECHO, Q_LONG, Q_NEAR_WHOLE, Q_SHORT, Q_UNGROUNDED,
    check_quote, normalize,
)
from .prompts import TRAP_KEYS, build_attack_prompt

CONFIRMED, REFUTED, INSUFFICIENT = "CONFIRMED", "REFUTED", "INSUFFICIENT"
_DECISIVE = {CONFIRMED, REFUTED}
_RESULTS = {CONFIRMED, REFUTED, INSUFFICIENT}
ESCALATE = "ESCALATE"

SCHEMA_VERSION = 1
# Severity order (highest first): the reported downgrade_reason when a
# decisive verdict is stripped or the model itself declined.
_SEVERITY = ["NO_SOURCES", "UNPARSEABLE", "SCHEMA", "TRUNCATED", Q_LONG,
             Q_NEAR_WHOLE, Q_ECHO, Q_SHORT, Q_UNGROUNDED, "MODEL_INSUFFICIENT"]


@dataclass
class EvidenceSpan:
    quote: str
    source_index: int


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

    @property
    def survived(self) -> bool:
        return self.result == CONFIRMED


def _insufficient(reason: str, *, rationale: str = "", raw: str = "", checks=None) -> Verdict:
    return Verdict(INSUFFICIENT, rationale=rationale, downgrade_reason=reason,
                   checks=checks or {}, raw=raw)


def _extract_json(text: str) -> Optional[dict]:
    """String-aware brace scanner: braces inside JSON strings don't count."""
    depth = start = None
    in_str = esc = False
    depth = 0
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        start = None
    return None


class Skeptic:
    """A second AI whose only job is to prove the first one wrong.

    llm: any callable prompt -> response text. killpass is the harness,
    not the brain.
    max_source_chars: optional per-source truncation budget (caller's
    knowledge of the model's context). Default None = never truncate. If set
    and truncation occurs, a decisive verdict is forced to INSUFFICIENT
    (TRUNCATED) — the harness never silently judges on a partial read.
    """

    def __init__(self, llm: Callable[[str], str], max_source_chars: Optional[int] = None):
        self.llm = llm
        self.max_source_chars = max_source_chars

    def attack(self, claim: str, sources: List[str]) -> Verdict:
        clean = [s for s in (sources or []) if s and s.strip()]
        if not clean:
            return _insufficient("NO_SOURCES", rationale="No sources provided; nothing can be verified.")

        truncated = False
        if self.max_source_chars is not None:
            capped = []
            for s in clean:
                if len(s) > self.max_source_chars:
                    truncated = True
                    capped.append(s[: self.max_source_chars])
                else:
                    capped.append(s)
            clean = capped

        raw = self.llm(build_attack_prompt(claim, clean, truncated=truncated))
        data = _extract_json(raw or "")
        if not data:
            return _insufficient("UNPARSEABLE", rationale="Skeptic response was not parseable JSON.", raw=raw or "")

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
                                 raw=raw, checks=checks if isinstance(checks, dict) else {})
        checks = {k: str(v).lower() for k, v in checks.items()}
        quotes = [str(e.get("quote", "")) for e in ev_raw if isinstance(e, dict) and "quote" in e]

        if result == INSUFFICIENT:
            return Verdict(INSUFFICIENT, rationale=rationale, checks=checks,
                           downgrade_reason="MODEL_INSUFFICIENT", raw=raw)

        # --- decisive path: grounding gate ---
        if truncated:
            return _insufficient("TRUNCATED", checks=checks, raw=raw,
                                 rationale="A source was truncated to the caller's budget; decisive verdict withheld.")
        norm_sources = [normalize(s) for s in clean]
        norm_claim = normalize(claim)
        survivors: List[EvidenceSpan] = []
        failures: List[str] = []
        for q in quotes:
            idx, reason = check_quote(q, norm_sources, norm_claim)
            if idx is not None:
                survivors.append(EvidenceSpan(quote=q, source_index=idx))
            else:
                failures.append(reason)
        if survivors:
            return Verdict(result, evidence=survivors, rationale=rationale, checks=checks, raw=raw)
        reason = min(failures, key=_SEVERITY.index) if failures else Q_UNGROUNDED
        return _insufficient(reason, checks=checks, raw=raw,
                             rationale="Verdict downgraded: no evidence quote survived the grounding gate.")


def dual_attack(skeptic_a: Skeptic, skeptic_b: Skeptic, claim: str, sources: List[str]) -> dict:
    """Two independent skeptics; disagreement returns ESCALATE (human should look).

    Agreement measures reliability of THIS run, not truth.
    """
    va, vb = skeptic_a.attack(claim, sources), skeptic_b.attack(claim, sources)
    agree = va.result == vb.result
    return {"result": va.result if agree else ESCALATE, "agree": agree, "a": va, "b": vb}
