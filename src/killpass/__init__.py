"""killpass — AI that double-checks itself before it speaks.

killpass verifies that a claim is GROUNDED in a verbatim source span. It does
NOT verify that the claim is true or fully supported: a quote can exist in a
source yet be negated, sarcastic, or a third-party rumor. That residual is
measured (tests/adversarial) and documented (SECURITY.md), never hidden.
"""
from ._version import __version__

from .core import (
    CONFIRMED, REFUTED, INSUFFICIENT, ESCALATE, SCHEMA_VERSION,
    Skeptic, Verdict, EvidenceSpan, SourceDocument, SourceRef, dual_attack,
)
from .sources import load, load_all

__all__ = [
    "Skeptic", "Verdict", "EvidenceSpan", "SourceDocument", "SourceRef",
    "dual_attack", "load", "load_all",
    "CONFIRMED", "REFUTED", "INSUFFICIENT", "ESCALATE", "SCHEMA_VERSION", "__version__",
]
