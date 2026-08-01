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

# Loaders run on untrusted files/URLs, so each caps its work. Defaults are
# generous; a real document clears them, a decompression bomb or binary blob
# does not. killpass judges text, it is not a hardened crawler (see SECURITY.md).
_MAX_DOCX_XML_BYTES = 64 * 1024 * 1024   # decompressed word/document.xml
_MAX_PDF_BYTES = 64 * 1024 * 1024        # PDF file on disk
_MAX_PDF_PAGES = 5000
# from_url only decodes text; a binary Content-Type is rejected, not stripped.
_TEXT_CONTENT_TYPES = {"application/xhtml+xml", "application/xml", "text/xml"}


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
    """A .docx is a zip; the text lives in word/document.xml. Stdlib only.

    Guarded against decompression bombs: document.xml is read through a bounded
    stream, so a small archive claiming to expand to gigabytes is refused before
    it is decompressed, not after."""
    with zipfile.ZipFile(path) as z:
        with z.open("word/document.xml") as f:
            data = f.read(_MAX_DOCX_XML_BYTES + 1)   # incremental decompress, bounded
        if len(data) > _MAX_DOCX_XML_BYTES:
            raise ValueError(
                f"docx word/document.xml exceeds {_MAX_DOCX_XML_BYTES} bytes decompressed "
                "(possible zip bomb); extract it yourself and pass the text in")
        xml = data.decode("utf-8", errors="replace")
    paragraphs = []
    for para in re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", xml, flags=re.S):
        runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, flags=re.S)
        if runs:
            paragraphs.append(_html.unescape("".join(runs)))
    return "\n".join(paragraphs)


# Fetching untrusted URLs from inside a service is an SSRF/DoS surface.
# from_url refuses private/loopback hosts, caps the download, and does not
# follow redirects. If you need broader fetching, do it in your own retrieval
# layer and pass the text in; killpass judges, it does not crawl.
_MAX_URL_BYTES = 10 * 1024 * 1024  # 10 MB


def _blocks_private(host: str) -> bool:
    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True  # unresolvable: refuse
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # do not follow redirects (redirect-to-internal SSRF)


def from_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("from_url only accepts http(s) URLs with a host")
    if _blocks_private(parsed.hostname):
        raise ValueError(f"from_url refuses private/loopback/unresolvable host: {parsed.hostname!r}")
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers=_UA)
    with opener.open(req, timeout=60) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype and not (ctype.startswith("text/") or ctype in _TEXT_CONTENT_TYPES):
            raise ValueError(
                f"from_url expected a text document, got Content-Type {ctype!r}; "
                "fetch and extract it yourself and pass the text in")
        raw = resp.read(_MAX_URL_BYTES + 1)
    if len(raw) > _MAX_URL_BYTES:
        raise ValueError(f"from_url response exceeds {_MAX_URL_BYTES} bytes; fetch it yourself and pass the text in")
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
    size = Path(path).stat().st_size
    if size > _MAX_PDF_BYTES:
        raise ValueError(f"PDF exceeds {_MAX_PDF_BYTES} bytes; extract the text yourself and pass it in")
    reader = PdfReader(str(path))
    pages = reader.pages
    if len(pages) > _MAX_PDF_PAGES:
        raise ValueError(f"PDF has {len(pages)} pages (> {_MAX_PDF_PAGES}); extract the pages you need and pass the text in")
    return "\n\n".join((page.extract_text() or "") for page in pages)
