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
# schema_version 2: the model's own source_index is validated, not rewritten.
INVALID_SOURCE_INDEX = "INVALID_SOURCE_INDEX"   # missing, non-int, or out of range
SOURCE_INDEX_MISMATCH = "SOURCE_INDEX_MISMATCH"  # in range, but the quote is not in that source


def check_quote(quote: str, norm_sources: List[str], norm_claim: str,
                source_index: object) -> Tuple[Optional[int], Optional[str]]:
    """Return (source_index, None) if the quote grounds, else (None, reason).

    The quote must be a verbatim span of the source the model DECLARED, not
    merely of some source. Grounded-elsewhere is not grounded-as-cited: a
    provenance claim the harness cannot confirm is a failure, not a save.
    """
    # bool is an int subclass in Python; a JSON `true` must not read as index 1.
    if isinstance(source_index, bool) or not isinstance(source_index, int):
        return None, INVALID_SOURCE_INDEX
    if source_index < 0 or source_index >= len(norm_sources):
        return None, INVALID_SOURCE_INDEX
    nq = normalize(quote)
    if len(nq) < QUOTE_MIN_CHARS:
        return None, Q_SHORT
    if len(nq) > QUOTE_MAX_CHARS:
        return None, Q_LONG
    if is_claim_echo(nq, norm_claim):
        return None, Q_ECHO
    ns = norm_sources[source_index]
    if nq not in ns:
        return None, SOURCE_INDEX_MISMATCH
    src_len = len(ns)
    alpha = NEAR_WHOLE_SOURCE_ALPHA if src_len >= SOURCE_MIN_FOR_ALPHA else NEAR_WHOLE_SOURCE_ALPHA_SHORT
    if len(nq) >= alpha * src_len:
        return None, Q_NEAR_WHOLE
    return source_index, None


# --- schema_version 3: best-effort original-text offsets for audit ------------
# The gate above matches in normalized space; these functions map a grounded
# quote back to exact character offsets in the ORIGINAL source, or return None.
# They NEVER affect a verdict: a decisive verdict is decided entirely by
# check_quote. Offsets are exact-or-null (a wrong highlight is a lying audit
# trail), so every emit is guarded by a round-trip re-normalization.


def _nfkc_groups(text: str):
    """Yield (nfkc_text, o_start, o_end) per combining sequence (a starter plus
    its following combining marks). Per-group NFKC equals global NFKC because
    canonical composition never crosses a starter boundary, which is what makes
    an origin map recoverable through NFKC at all."""
    n = len(text)
    i = 0
    while i < n:
        j = i + 1
        while j < n and unicodedata.combining(text[j]) != 0:
            j += 1
        yield unicodedata.normalize("NFKC", text[i:j]), i, j
        i = j


def _normalize_with_map(text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """Reproduce normalize() while tracking, for each output char, the half-open
    range of ORIGINAL indices that produced it. Same stages, same order:
    NFKC -> fold -> casefold -> whitespace-collapse. The caller must confirm the
    returned text equals normalize(text); if a future normalize() diverges, the
    map is discarded and offsets fall back to None."""
    text = text or ""
    # NFKC, carrying each output char's origin range.
    chars: List[Tuple[str, int, int]] = []
    for grp, os, oe in _nfkc_groups(text):
        for c in grp:
            chars.append((c, os, oe))
    # Fold (per char); a deleted char (ZWSP/BOM) is absorbed into the previous
    # kept char's range so its original position stays inside any covering span.
    folded: List[Tuple[str, int, int]] = []
    for c, os, oe in chars:
        f = _FOLD.get(c, c)
        if f == "":
            if folded:
                pc, pos, poe = folded[-1]
                folded[-1] = (pc, pos, max(poe, oe))
            continue
        folded.append((f, os, oe))
    # Casefold (one char may expand to several; all share the origin).
    cased: List[Tuple[str, int, int]] = []
    for c, os, oe in folded:
        for cc in c.casefold():
            cased.append((cc, os, oe))
    # Whitespace collapse == " ".join(split()): drop leading/trailing runs,
    # collapse each interior run to one space spanning the whole run.
    out_chars: List[str] = []
    out_orig: List[Tuple[int, int]] = []
    pending = False
    p_os = p_oe = 0
    started = False
    for c, os, oe in cased:
        if c.isspace():
            if started:
                if not pending:
                    pending, p_os, p_oe = True, os, oe
                else:
                    p_oe = oe
            continue
        if pending:
            out_chars.append(" ")
            out_orig.append((p_os, p_oe))
            pending = False
        out_chars.append(c)
        out_orig.append((os, oe))
        started = True
    return "".join(out_chars), out_orig


def locate_span(original: str, norm_quote: str) -> Optional[Tuple[int, int]]:
    """Return (start_char, end_char) into `original` for a grounded quote, or
    None. None whenever anything is uncertain: map integrity fails, the match is
    not unique, or the re-normalized slice does not equal norm_quote. Exact or
    null, never a best guess."""
    try:
        norm_text, origins = _normalize_with_map(original)
        if norm_text != normalize(original):      # map integrity guard
            return None
        if not norm_quote or norm_text.count(norm_quote) != 1:
            return None                            # absent or ambiguous locus
        i = norm_text.index(norm_quote)
        j = i + len(norm_quote)
        if j - 1 >= len(origins):
            return None
        start, end = origins[i][0], origins[j - 1][1]
        if not (0 <= start < end <= len(original)):
            return None
        if normalize(original[start:end]) != norm_quote:   # round-trip proof
            return None
        return start, end
    except Exception:
        return None
