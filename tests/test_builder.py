"""Tests for deck assembly and .apkg output."""

import sqlite3
import zipfile

from anki_gen.builder import (
    BuildStats,
    build_package,
    cloze_card_count,
    slugify,
    write_deck,
)
from anki_gen.loader import parse_deck

SAMPLE = {
    "deck": "Sample Deck",
    "tags": ["sample"],
    "sections": [
        {
            "title": "Group A",
            "cards": [
                {"q": "What is 2+2?", "a": "4"},  # basic -> 1 card
                {"front": "Capital of France?", "back": "Paris", "note_type": "reversed"},  # 2 cards
                {"note_type": "cloze", "text": "The sky is [[blue]] and grass is [[green]]."},  # 2 cards
            ],
        }
    ],
}


def _deck():
    return parse_deck(SAMPLE)


def test_card_counts_per_note_type():
    _, stats = build_package(_deck())
    assert isinstance(stats, BuildStats)
    assert stats.notes == 3
    # basic(1) + reversed(2) + cloze(2 distinct deletions) = 5
    assert stats.cards == 5
    assert stats.by_type == {"basic": 1, "reversed": 1, "cloze": 1}


def test_deck_description_reaches_genanki_deck():
    data = dict(SAMPLE, description="My study deck.")
    package, _ = build_package(parse_deck(data))
    assert package.decks[0].description == "My study deck."


def test_cloze_card_count_counts_distinct_indices():
    assert cloze_card_count("{{c1::a}} {{c2::b}}") == 2
    assert cloze_card_count("{{c1::a}} {{c1::b}}") == 1  # same index = one card
    assert cloze_card_count("no cloze") == 1


def test_slugify_makes_tag_safe():
    assert slugify("Tier 1 — Foundational") == "tier-1-foundational"


def test_write_deck_produces_valid_apkg(tmp_path):
    out = tmp_path / "deck.apkg"
    stats = write_deck(_deck(), out)

    assert out.exists()
    assert stats.notes == 3
    # .apkg is a zip containing an Anki SQLite collection.
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "collection.anki2" in names or "collection.anki21" in names


def test_reimport_guids_are_stable(tmp_path):
    """Same content -> same note GUIDs across builds (no duplicate-on-reimport)."""
    deck = _deck()
    pkg1, _ = build_package(deck)
    pkg2, _ = build_package(deck)

    guids1 = sorted(n.guid for n in pkg1.decks[0].notes)
    guids2 = sorted(n.guid for n in pkg2.decks[0].notes)
    assert guids1 == guids2


def test_apkg_collection_contains_notes(tmp_path):
    out = tmp_path / "deck.apkg"
    write_deck(_deck(), out)

    with zipfile.ZipFile(out) as zf:
        member = "collection.anki21" if "collection.anki21" in zf.namelist() else "collection.anki2"
        zf.extract(member, tmp_path)

    con = sqlite3.connect(tmp_path / member)
    try:
        note_count = con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    finally:
        con.close()
    assert note_count == 3
