"""Tests for the YAML loader and card parsing/validation."""

import pytest

from anki_gen.loader import parse_deck
from anki_gen.schema import ValidationError, convert_cloze_shorthand


def test_parses_deck_name_theme_and_tags():
    # Arrange
    data = {"deck": "Geography", "theme": "default", "tags": ["geo"], "sections": []}

    # Act
    deck = parse_deck(data)

    # Assert
    assert deck.name == "Geography"
    assert deck.theme == "default"
    assert deck.tags == ("geo",)


def test_parses_optional_description():
    deck = parse_deck({"deck": "D", "description": "All about D.", "sections": []})
    assert deck.description == "All about D."


def test_description_defaults_to_empty():
    assert parse_deck({"deck": "D", "sections": []}).description == ""


def test_missing_deck_name_raises():
    with pytest.raises(ValidationError, match="deck"):
        parse_deck({"sections": []})


def test_q_a_aliases_map_to_front_back():
    data = {
        "deck": "D",
        "sections": [{"title": "S", "cards": [{"q": "2+2?", "a": "4"}]}],
    }

    card = parse_deck(data).sections[0].cards[0]

    assert card.note_type == "basic"
    assert card.fields["front"] == "2+2?"
    assert card.fields["back"] == "4"


def test_note_type_precedence_card_over_section_over_deck():
    data = {
        "deck": "D",
        "note_type": "reversed",
        "sections": [
            {
                "title": "S",
                "note_type": "basic",
                "cards": [
                    {"front": "a", "back": "b"},  # inherits section -> basic
                    {"front": "c", "back": "d", "note_type": "reversed"},  # override
                ],
            }
        ],
    }

    cards = parse_deck(data).sections[0].cards

    assert cards[0].note_type == "basic"
    assert cards[1].note_type == "reversed"


def test_deck_tags_merge_onto_card_tags():
    data = {
        "deck": "D",
        "tags": ["base"],
        "sections": [{"title": "S", "cards": [{"q": "x", "a": "y", "tags": ["extra"]}]}],
    }

    card = parse_deck(data).sections[0].cards[0]

    assert "base" in card.tags
    assert "extra" in card.tags


def test_cloze_shorthand_is_converted():
    data = {
        "deck": "D",
        "sections": [
            {
                "title": "S",
                "cards": [{"note_type": "cloze", "text": "The capital is [[Paris]]."}],
            }
        ],
    }

    card = parse_deck(data).sections[0].cards[0]

    assert card.fields["text"] == "The capital is {{c1::Paris}}."


def test_cloze_shorthand_numbering_continues_past_explicit():
    text = "{{c1::a}} and [[b]] and [[c]]"
    assert convert_cloze_shorthand(text) == "{{c1::a}} and {{c2::b}} and {{c3::c}}"


def test_basic_card_missing_back_raises_with_location():
    data = {
        "deck": "D",
        "sections": [{"title": "S", "cards": [{"front": "only front"}]}],
    }

    with pytest.raises(ValidationError, match="section 1.*card 1.*back"):
        parse_deck(data)


def test_cloze_card_without_deletion_raises():
    data = {
        "deck": "D",
        "sections": [
            {"title": "S", "cards": [{"note_type": "cloze", "text": "no blanks here"}]}
        ],
    }

    with pytest.raises(ValidationError, match="cloze.*deletion"):
        parse_deck(data)


def test_term_and_tier_chrome_captured():
    data = {
        "deck": "D",
        "sections": [
            {
                "title": "Tier 1",
                "cards": [{"q": "x", "a": "y", "term": "Water column"}],
            }
        ],
    }

    card = parse_deck(data).sections[0].cards[0]

    assert card.term == "Water column"
    assert card.tier == "Tier 1"  # defaults to section title
