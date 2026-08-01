import zipfile

import pytest

from killpass import load
from killpass.sources import strip_html

DOC_XML = '<?xml version="1.0"?><w:document xmlns:w="x"><w:body><w:p><w:r><w:t>Guidance is unchanged</w:t></w:r></w:p><w:p><w:r><w:t>EPS revised to $28.36</w:t></w:r><w:r><w:t xml:space="preserve"> to $28.80</w:t></w:r></w:p></w:body></w:document>'

def test_docx_roundtrip(tmp_path):
    p = tmp_path / "mini.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/document.xml", DOC_XML)
    text = load(str(p))
    assert "Guidance is unchanged" in text
    assert "EPS revised to $28.36 to $28.80" in text

def test_strip_html():
    html = "<html><head><style>x{}</style></head><body><h1>Acme Q2</h1><p>Sales guidance is <b>unchanged</b>.</p><script>bad()</script></body></html>"
    text = strip_html(html)
    assert "Sales guidance is unchanged" in text
    assert "bad()" not in text and "x{}" not in text

def test_txt_passthrough(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("plain words")
    assert load(str(p)) == "plain words"


def test_from_url_blocks_ssrf():
    from killpass.sources import from_url
    for bad in ["http://localhost/x", "http://127.0.0.1/x",
                "http://169.254.169.254/latest/meta-data", "ftp://host/y"]:
        with pytest.raises(ValueError):
            from_url(bad)


def test_docx_bomb_guard(tmp_path, monkeypatch):
    """A docx whose document.xml decompresses past the cap is refused, before
    the whole thing is decompressed into memory."""
    from killpass import sources
    monkeypatch.setattr(sources, "_MAX_DOCX_XML_BYTES", 500)
    big = '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>' + ("<w:p><w:r><w:t>x</w:t></w:r></w:p>" * 400) + "</w:body></w:document>"
    p = tmp_path / "bomb.docx"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", big)   # highly compressible: small on disk, large decompressed
    assert p.stat().st_size < 2000 and len(big) > 500
    with pytest.raises(ValueError):
        sources.from_docx(str(p))


def test_prompt_uses_per_run_nonce_delimiters():
    import re

    from killpass.prompts import build_attack_prompt
    p1 = build_attack_prompt("a claim", ["source zero", "source one"])
    p2 = build_attack_prompt("a claim", ["source zero", "source one"])
    t1 = re.search(r"KP_([0-9a-f]{12})", p1).group(1)
    assert t1 != re.search(r"KP_([0-9a-f]{12})", p2).group(1)   # token rotates per run
    assert f"<<<KP_CLAIM_{t1}>>>" in p1 and f"<<<KP_SRC_{t1}_1>>>" in p1
