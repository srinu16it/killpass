"""Source loaders: turn files/URLs into plain text for the Skeptic.

Design rule: the judge (core.py) only ever sees text. These adapters do the
fetching/parsing OUTSIDE the judgment, so verdicts stay auditable — the text
handed to the skeptic is the text that was judged.

Zero-dependency formats: .txt/.md, .docx (a zip of XML), http(s) pages.
PDF needs the optional extra:  pip install killpass[pdf]
"""
from __future__ import annotations

import html as _html
import re
import urllib.request
import zipfile
from pathlib import Path

_UA = {"User-Agent": "killpass-source-loader (+https://github.com/srinu16it/killpass)"}


def load(source: str) -> str:
    """Load one source (file path or URL) as plain text.

    Dispatch: http(s):// -> web page | .pdf -> PDF (optional extra)
    | .docx -> Word | anything else -> read as text file.
    """
    s = str(source)
    if s.startswith(("http://", "https://")):
        return from_url(s)
    p = Path(s)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return from_pdf(p)
    if suffix == ".docx":
        return from_docx(p)
    return p.read_text(errors="replace")


def load_all(sources: list) -> list:
    return [load(s) for s in sources]


def from_docx(path) -> str:
    """A .docx is a zip; the text lives in word/document.xml. Stdlib only."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    paragraphs = []
    for para in re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", xml, flags=re.S):
        runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, flags=re.S)
        if runs:
            paragraphs.append(_html.unescape("".join(runs)))
    return "\n".join(paragraphs)


def from_url(url: str) -> str:
    req = urllib.request.Request(url, headers=_UA)
    raw = urllib.request.urlopen(req, timeout=60).read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    return strip_html(text)


def strip_html(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", markup)
    markup = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</h[1-6]>|</li>|</tr>", "\n", markup)
    text = re.sub(r"(?s)<[^>]+>", " ", markup)
    text = _html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def from_pdf(path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ImportError(
            "PDF support needs the optional extra: pip install killpass[pdf]"
        ) from e
    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)
