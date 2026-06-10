"""Tests for deck assembly and .apkg output."""

import io
import sqlite3
import zipfile

from PIL import Image

from anki_gen.builder import (
    BuildStats,
    _guid_seed,
    build_package,
    cloze_card_count,
    slugify,
    write_deck,
)
from anki_gen.loader import parse_deck
from anki_gen.media import resolve_deck_media
from anki_gen.schema import Card, Deck, Section

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


def _png(path, size=(120, 90)):
    Image.new("RGB", size, (1, 2, 3)).save(path)
    return path


def _image_deck(image_src, credit=""):
    card = Card("basic", {"front": "q", "back": "a"},
                image=str(image_src), image_credit=credit)
    return Deck(name="Img Deck", sections=(Section(title="S", cards=(card,)),))


def test_build_package_bundles_media_files(tmp_path):
    img = _png(tmp_path / "cell.png")
    staging = tmp_path / "stage"
    staging.mkdir()
    deck = _image_deck(img)
    media = resolve_deck_media(deck, staging_dir=staging)

    package, _ = build_package(deck, media)

    assert len(package.media_files) == 1
    assert package.media_files[0] == str(media[str(img)].local_path)


def test_build_package_no_media_when_no_images():
    package, _ = build_package(_deck())
    assert package.media_files == []


def test_guid_seed_for_imageless_card_matches_legacy_format():
    # An imageless note must hash to the SAME seed as before image support, so
    # upgrading and re-importing updates notes in place instead of duplicating.
    basic = Card("basic", {"front": "q", "back": "a"})
    cloze = Card("cloze", {"text": "{{c1::x}}"})

    assert _guid_seed("Deck", basic) == "Deck|basic|q|a"
    assert _guid_seed("Deck", cloze) == "Deck|cloze|{{c1::x}}"


def test_guid_seed_includes_image_metadata_when_present():
    card = Card("basic", {"front": "q", "back": "a"},
                image="/abs/x.png", image_credit="CC", image_side="back")

    seed = _guid_seed("Deck", card)

    assert seed.startswith("Deck|basic|q|a|")
    assert "/abs/x.png" in seed and "back" in seed


def test_guid_changes_when_image_changes(tmp_path):
    img1 = _png(tmp_path / "one.png")
    img2 = _png(tmp_path / "two.png", size=(60, 60))
    staging = tmp_path / "stage"
    staging.mkdir()

    d1 = _image_deck(img1)
    d2 = _image_deck(img2)
    p1, _ = build_package(d1, resolve_deck_media(d1, staging_dir=staging))
    p2, _ = build_package(d2, resolve_deck_media(d2, staging_dir=staging))

    assert p1.decks[0].notes[0].guid != p2.decks[0].notes[0].guid


def test_write_deck_resolves_media_and_bundles_image(tmp_path):
    img = _png(tmp_path / "diagram.png")
    out = tmp_path / "deck.apkg"

    write_deck(_image_deck(img), out)

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "media" in names  # genanki media manifest present
    # at least one numbered media entry alongside the collection
    assert any(n.isdigit() for n in names)


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
