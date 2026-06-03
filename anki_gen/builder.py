"""Assemble a parsed :class:`~anki_gen.schema.Deck` into an Anki ``.apkg``.

Note GUIDs are seeded from the deck name + card content, so re-running on edited
input updates existing notes in Anki instead of creating duplicates (mirroring
the behaviour of the original make_anki_deck.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import genanki

from .models import build_model, ordered_field_values, stable_id
from .schema import Card, Deck, Section
from .theme import load_theme_css

_CLOZE_INDEX = re.compile(r"\{\{c(\d+)::")


@dataclass
class BuildStats:
    notes: int = 0
    cards: int = 0
    by_type: dict[str, int] = field(default_factory=dict)


def slugify(value: str) -> str:
    """Lowercase, hyphenated, Anki-tag-safe slug (no spaces)."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def cloze_card_count(text: str) -> int:
    """Number of cards a cloze note produces = count of distinct ``cN`` indices."""
    indices = {int(n) for n in _CLOZE_INDEX.findall(text)}
    return len(indices) or 1


def _card_count(card: Card) -> int:
    if card.note_type == "reversed":
        return 2
    if card.note_type == "cloze":
        return cloze_card_count(card.fields.get("text", ""))
    return 1


def _note_tags(card: Card, section_title: str) -> list[str]:
    tags = [slugify(t) for t in card.tags]
    tags.append(slugify(section_title))
    if card.term:
        tags.append(slugify(card.term))
    # De-duplicate while preserving order, dropping any empties.
    seen: dict[str, None] = {}
    for t in tags:
        if t:
            seen.setdefault(t, None)
    return list(seen)


def _guid_seed(deck_name: str, card: Card) -> str:
    f = card.fields
    content = f.get("text") or f"{f.get('front', '')}|{f.get('back', '')}"
    return f"{deck_name}|{card.note_type}|{content}"


def build_package(deck: Deck) -> tuple[genanki.Package, BuildStats]:
    """Build a genanki Package and collect statistics for ``deck``."""
    css = load_theme_css(deck.theme)
    models = {nt: build_model(nt, css) for nt in {"basic", "reversed", "cloze"}}

    g_deck = genanki.Deck(stable_id(deck.name), deck.name, description=deck.description)
    stats = BuildStats()

    for section in deck.sections:
        _add_section(g_deck, section, deck.name, models, stats)

    return genanki.Package(g_deck), stats


def _add_section(
    g_deck: genanki.Deck,
    section: Section,
    deck_name: str,
    models: dict[str, genanki.Model],
    stats: BuildStats,
) -> None:
    for card in section.cards:
        note = genanki.Note(
            model=models[card.note_type],
            fields=ordered_field_values(card),
            tags=_note_tags(card, section.title),
            guid=genanki.guid_for(_guid_seed(deck_name, card)),
        )
        g_deck.add_note(note)

        stats.notes += 1
        stats.cards += _card_count(card)
        stats.by_type[card.note_type] = stats.by_type.get(card.note_type, 0) + 1


def write_deck(deck: Deck, out_path: str | Path) -> BuildStats:
    """Build ``deck`` and write the ``.apkg`` to ``out_path``."""
    package, stats = build_package(deck)
    package.write_to_file(str(out_path))
    return stats
