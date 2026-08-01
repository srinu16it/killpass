"""Frozen mechanical constants (adversarial review, 2026).

Every value carries its rationale so no code review has to ask "why this
number." These gate WORTHLESS spans; none of them check meaning/polarity —
that is out of reach for a substring engine, by design (see SECURITY.md).
"""

# A quote shorter than this is usually a name, ticker, bare number, or
# yes/no fragment that substring-matches almost any corpus. Char floor (not
# word count) stays stable for "$9.05", tickers, and non-English text.
QUOTE_MIN_CHARS = 12

# A citation should be the deciding SENTENCE, not a paragraph. News
# sentences cluster ~100-250 chars; dense SEC/legal run 300-450. 500 clears
# real deciding sentences while staying under a short paragraph (~600-1000),
# so paragraph-dumps are caught by the near-whole test below.
QUOTE_MAX_CHARS = 500

# On a long source, a single "quote" covering >= this fraction of the source
# is a dump, not a pointer. Applied per matching source, never on a join.
NEAR_WHOLE_SOURCE_ALPHA = 0.5

# The alpha test only applies when the source is at least this long; below
# it, 0.5 would false-kill normal citations from short sources (tweets,
# one-line IR blasts).
SOURCE_MIN_FOR_ALPHA = 500

# For short sources (< SOURCE_MIN_FOR_ALPHA), reject only near-total copies.
NEAR_WHOLE_SOURCE_ALPHA_SHORT = 0.9
