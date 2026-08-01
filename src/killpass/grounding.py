"""The grounding engine: mechanical gates that kill worthless quotes.

Grounded != supported. This module proves a quote is a real, non-trivial,
non-dump, non-echo verbatim span of ONE source. It cannot prove the quote
supports the verdict (negation, sarcasm, third-party rumor survive). That
residual is measured, not hidden — see tests/adversarial and SECURITY.md.
"""
from __future__ import annotations

import unicodedata
from typing import List, Optional, Tuple

from .constants import (
    NEAR_WHOLE_SOURCE_ALPHA,
    NEAR_WHOLE_SOURCE_ALPHA_SHORT,
    QUOTE_MAX_CHARS,
    QUOTE_MIN_CHARS,
    SOURCE_MIN_FOR_ALPHA,
)

# Fancy characters folded to ASCII so smart-quotes/dashes/NBSP don't break
# matching in either direction.
_FOLD = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
    "​": "", "﻿": "",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = "".join(_FOLD.get(ch, ch) for ch in text)
    return " ".join(text.casefold().split())


_PUNCT = str.maketrans("", "", ".,;:!?\"'()[]{}")


def _depunct(norm_text: str) -> str:
    return " ".join(w.translate(_PUNCT) for w in norm_text.split())


def _tokens(norm_text: str) -> frozenset:
    return frozenset(_depunct(norm_text).split())


def is_claim_echo(norm_quote: str, norm_claim: str) -> bool:
    """Echo = the quote adds NO information beyond the claim itself."""
    if not norm_quote or not norm_claim:
        return False
    dq, dc = _depunct(norm_quote), _depunct(norm_claim)
    if dq and dq in dc:
        return True
    return _tokens(norm_quote) <= _tokens(norm_claim)


# Reason codes a single quote can fail with (severity handled by the caller).
Q_SHORT = "QUOTE_TOO_SHORT"
Q_LONG = "QUOTE_TOO_LONG"
Q_NEAR_WHOLE = "NEAR_WHOLE_SOURCE"
Q_ECHO = "CLAIM_ECHO"
Q_UNGROUNDED = "UNGROUNDED"


def check_quote(quote: str, norm_sources: List[str], norm_claim: str) -> Tuple[Optional[int], Optional[str]]:
    """Return (source_index, None) if the quote grounds, else (None, reason)."""
    nq = normalize(quote)
    if len(nq) < QUOTE_MIN_CHARS:
        return None, Q_SHORT
    if len(nq) > QUOTE_MAX_CHARS:
        return None, Q_LONG
    if is_claim_echo(nq, norm_claim):
        return None, Q_ECHO
    hit_but_near_whole = False
    for i, ns in enumerate(norm_sources):
        if nq in ns:
            src_len = len(ns)
            alpha = NEAR_WHOLE_SOURCE_ALPHA if src_len >= SOURCE_MIN_FOR_ALPHA else NEAR_WHOLE_SOURCE_ALPHA_SHORT
            if len(nq) >= alpha * src_len:
                hit_but_near_whole = True   # keep scanning: a later source may hold a proper span
                continue
            return i, None
    return None, (Q_NEAR_WHOLE if hit_but_near_whole else Q_UNGROUNDED)
