"""End-to-end tests for the CLI and HTML page rendering."""

import zipfile
from pathlib import Path

from PIL import Image

from anki_gen.cli import main
from anki_gen.htmlpage import render_page, reveal_cloze
from anki_gen.loader import load_deck
from anki_gen.media import resolve_deck_media
from anki_gen.schema import Card, Deck, Section

FIXTURE = Path(__file__).parent / "fixtures" / "sample.yaml"


def _png(path, size=(80, 60)):
    Image.new("RGB", size, (200, 120, 40)).save(path)
    return path


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


def test_render_page_inlines_image_as_data_uri(tmp_path):
    img = _png(tmp_path / "cell.png")
    staging = tmp_path / "stage"
    staging.mkdir()
    card = Card("basic", {"front": "q", "back": "a"},
                image=str(img), image_credit="CC BY-SA 4.0")
    deck = Deck(name="Img", sections=(Section(title="S", cards=(card,)),))
    media = resolve_deck_media(deck, staging_dir=staging)

    html = render_page(deck, media)

    assert "data:image/" in html
    assert "<figcaption>CC BY-SA 4.0</figcaption>" in html


def test_back_side_image_renders_in_answer_column(tmp_path):
    img = _png(tmp_path / "reveal.png")
    staging = tmp_path / "stage"
    staging.mkdir()
    card = Card("basic", {"front": "What does it look like?", "back": "Like this"},
                image=str(img), image_side="back")
    deck = Deck(name="Reveal", sections=(Section(title="S", cards=(card,)),))
    media = resolve_deck_media(deck, staging_dir=staging)

    html = render_page(deck, media)

    # The image must appear after the prompt cell, inside the answer cell.
    answer_cell = html.split("What does it look like?", 1)[1]
    assert "data:image/" in answer_cell


def test_build_with_image_bundles_apkg_and_inlines_html(tmp_path):
    img = _png(tmp_path / "diagram.png")
    yaml_file = tmp_path / "deck.yaml"
    yaml_file.write_text(
        "deck: Img Deck\n"
        "sections:\n"
        "  - title: S\n"
        "    cards:\n"
        f"      - {{q: 'What is this?', a: 'A cell', image: {img.name}}}\n"
    )
    apkg = tmp_path / "out.apkg"
    html = tmp_path / "out.html"

    rc = main(["build", str(yaml_file), "-o", str(apkg), "--html", str(html)])

    assert rc == 0
    with zipfile.ZipFile(apkg) as zf:
        names = zf.namelist()
    assert "media" in names and any(n.isdigit() for n in names)
    assert "data:image/" in html.read_text()


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
