# How the Skeptic Works

One rule drives everything: **a claim is guilty until proven innocent.**

Most AI pipelines generate an answer and then look for support. killpass
inverts that. The skeptic is told: *try to destroy this claim using only
the provided sources.* Only claims that survive destruction reach the user.

Three constraints make it fail-closed:

1. **Refute-first prompting.** The skeptic is rewarded for killing false
   claims, not for agreeing. Agreeable AIs are the problem; this one is
   paid to argue.
2. **The grounding rule (enforced in code, not by the model).** A verdict
   of CONFIRMED or REFUTED must quote its deciding sentence, and killpass
   checks — mechanically — that the quote actually appears in the sources.
   If it doesn't, the verdict is downgraded to INSUFFICIENT automatically.
   The model cannot invent evidence and get away with it.
3. **Unclear = failed.** Missing sources, unparseable answers, ambiguous
   evidence — all become INSUFFICIENT, never a quiet pass.
