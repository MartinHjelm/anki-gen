"""End-to-end tests for the CLI and HTML page rendering."""

import zipfile
from pathlib import Path

from anki_gen.cli import main
from anki_gen.htmlpage import render_page, reveal_cloze
from anki_gen.loader import load_deck

FIXTURE = Path(__file__).parent / "fixtures" / "sample.yaml"


def test_build_writes_apkg_and_html(tmp_path, capsys):
    apkg = tmp_path / "demo.apkg"
    html = tmp_path / "demo.html"

    rc = main(["build", str(FIXTURE), "-o", str(apkg), "--html", str(html)])

    assert rc == 0
    assert apkg.exists() and html.exists()
    with zipfile.ZipFile(apkg) as zf:
        assert any(n.startswith("collection.anki2") for n in zf.namelist())
    out = capsys.readouterr().out
    assert "notes: 6" in out  # 2 basic + 2 reversed + 2 cloze


def test_build_invalid_yaml_returns_error(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("deck: D\nsections:\n  - title: S\n    cards:\n      - {front: x}\n")

    rc = main(["build", str(bad), "-o", str(tmp_path / 'x.apkg')])

    assert rc == 1
    assert "error" in capsys.readouterr().err


def test_reveal_cloze_strips_syntax_and_highlights():
    assert reveal_cloze("a {{c1::b}} c") == 'a <span class="cloze">b</span> c'
    assert reveal_cloze("{{c1::x::hint}}") == '<span class="cloze">x</span>'


def test_render_page_shares_theme_and_lists_cards():
    deck = load_deck(FIXTURE)
    html = render_page(deck)

    assert "anki-gen Demo" in html
    assert ".anki-gen-page" in html      # scoped theme CSS is inlined
    assert "Paris" in html               # reversed card answer
    assert 'class="cloze">100<' in html  # cloze revealed on the page
    assert "deck-description" in html     # description rendered in header
    assert "basic, reversed, and cloze" in html  # description text from fixture
