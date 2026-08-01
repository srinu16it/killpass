import io, zipfile
from killpass import load
from killpass.sources import strip_html, from_docx

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
