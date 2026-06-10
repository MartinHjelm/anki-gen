"""Tests for vendored MathJax detection and inlining into the HTML page."""

from anki_gen.htmlpage import render_page
from anki_gen.mathjax import (
    MATHJAX_JS_PATH,
    deck_has_math,
    load_mathjax_js,
    mathjax_head_html,
)
from anki_gen.schema import Card, Deck, Section


def _deck(*cards: Card) -> Deck:
    return Deck(name="Math", sections=(Section(title="S", cards=cards),))


def test_deck_has_math_detects_inline_delimiter():
    deck = _deck(Card("basic", {"front": "Mass-energy?", "back": r"\(E=mc^2\)"}))

    assert deck_has_math(deck) is True


def test_deck_has_math_detects_display_delimiter():
    deck = _deck(Card("basic", {"front": "Gaussian", "back": r"\[\int e^{-x^2}\,dx\]"}))

    assert deck_has_math(deck) is True


def test_deck_has_math_false_without_delimiters():
    deck = _deck(Card("basic", {"front": "Capital of France?", "back": "Paris"}))

    assert deck_has_math(deck) is False


def test_vendored_bundle_is_present_and_substantial():
    # Guards against the large binary being lost in a rebase/clean checkout.
    assert MATHJAX_JS_PATH.exists()
    assert len(load_mathjax_js()) > 100_000


def test_mathjax_head_html_includes_config_then_library():
    head = mathjax_head_html()

    # Config must precede the library so MathJax reads it on load, and the
    # delimiters must match Anki's so both outputs render the same source.
    config_at = head.index("window.MathJax")
    library_at = head.index("__webpack_modules__")
    assert config_at < library_at
    assert r"\\(" in head and r"\\[" in head  # inline + display delimiters


def test_render_page_inlines_mathjax_when_deck_has_math():
    deck = _deck(Card("basic", {"front": "Mass-energy?", "back": r"\(E=mc^2\)"}))

    html = render_page(deck)

    assert "window.MathJax" in html
    assert "__webpack_modules__" in html  # the vendored library is inlined
    assert r"\(E=mc^2\)" in html          # raw LaTeX passes through for MathJax


def test_render_page_omits_mathjax_when_deck_has_no_math():
    deck = _deck(Card("basic", {"front": "Capital of France?", "back": "Paris"}))

    html = render_page(deck)

    assert "window.MathJax" not in html
    assert "__webpack_modules__" not in html
