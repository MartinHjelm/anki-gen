"""Data model for a deck and its cards, plus card validation.

These frozen dataclasses are the internal contract between the loader (which
parses YAML) and the builders (which emit ``.apkg`` / HTML). Keeping them
immutable means a parsed deck can be passed around without fear of mutation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

# Supported note types. ``basic`` is the default when none is specified.
NOTE_TYPES: tuple[str, ...] = ("basic", "reversed", "cloze")
DEFAULT_NOTE_TYPE = "basic"

# Where a card's image is shown: on the question side, the answer side, or both.
# ``back`` keeps the image hidden until the answer is revealed.
IMAGE_SIDES: tuple[str, ...] = ("both", "front", "back")
DEFAULT_IMAGE_SIDE = "both"

# Matches an explicit Anki cloze deletion, e.g. {{c1::Paris}} or {{c12::x::hint}}.
_CLOZE_DELETION = re.compile(r"\{\{c(\d+)::")
# Matches the friendly shorthand [[Paris]] (no nested brackets).
_CLOZE_SHORTHAND = re.compile(r"\[\[(.+?)\]\]")


class ValidationError(ValueError):
    """Raised when a card or deck fails validation."""


@dataclass(frozen=True)
class Card:
    """A single source card.

    ``fields`` holds the note-type-specific content:
      - basic / reversed: ``front``, ``back``, and optional ``extra``
      - cloze:            ``text`` (with cloze deletions) and optional ``extra``

    ``term`` and ``tier`` are optional styling chrome rendered only when present.

    ``image`` is an optional reference to an illustration — either a local file
    path (resolved to absolute by the loader) or an ``http(s)`` URL. The media is
    resolved separately (see :mod:`anki_gen.media`); the card only holds the
    reference. ``image_credit`` is an optional caption/attribution line.
    ``image_side`` controls where the image appears (``both``/``front``/``back``);
    ``back`` keeps it hidden until the answer is shown.
    """

    note_type: str
    fields: Mapping[str, str]
    tags: tuple[str, ...] = ()
    term: str = ""
    tier: str = ""
    image: str = ""
    image_credit: str = ""
    image_side: str = DEFAULT_IMAGE_SIDE

    def __post_init__(self) -> None:
        # Freeze the mapping so the "frozen" dataclass is genuinely immutable.
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True)
class Section:
    title: str
    cards: tuple[Card, ...] = ()


@dataclass(frozen=True)
class Deck:
    name: str
    sections: tuple[Section, ...] = ()
    theme: str = "default"
    tags: tuple[str, ...] = ()
    description: str = ""


def has_cloze_deletion(text: str) -> bool:
    """True if ``text`` contains at least one explicit ``{{cN::...}}`` deletion."""
    return bool(_CLOZE_DELETION.search(text))


def convert_cloze_shorthand(text: str) -> str:
    """Rewrite friendly ``[[word]]`` shorthand into Anki ``{{cN::word}}`` syntax.

    Numbering continues past any explicit ``{{cN::}}`` already in the text, so
    mixing the two forms never produces a duplicate cloze index. Explicit
    deletions are left untouched.
    """
    explicit = [int(n) for n in _CLOZE_DELETION.findall(text)]
    counter = max(explicit, default=0)

    def _replace(match: "re.Match[str]") -> str:
        nonlocal counter
        counter += 1
        return f"{{{{c{counter}::{match.group(1)}}}}}"

    return _CLOZE_SHORTHAND.sub(_replace, text)


def validate_image_side(side: str) -> None:
    """Validate an ``image_side`` value, raising :class:`ValidationError`."""
    if side not in IMAGE_SIDES:
        allowed = ", ".join(IMAGE_SIDES)
        raise ValidationError(
            f"unknown image_side {side!r} (expected one of: {allowed})"
        )


def validate_card_fields(note_type: str, fields: Mapping[str, str]) -> None:
    """Validate a card's note type and required fields.

    Raises :class:`ValidationError` with a message describing the problem (the
    caller is expected to prepend the card's location, e.g. ``section 1 card 3``).
    """
    if note_type not in NOTE_TYPES:
        allowed = ", ".join(NOTE_TYPES)
        raise ValidationError(
            f"unknown note_type {note_type!r} (expected one of: {allowed})"
        )

    if note_type in ("basic", "reversed"):
        if not fields.get("front", "").strip():
            raise ValidationError(f"{note_type!r} note requires a non-empty 'front'")
        if not fields.get("back", "").strip():
            raise ValidationError(f"{note_type!r} note requires a non-empty 'back'")
    elif note_type == "cloze":
        text = fields.get("text", "")
        if not text.strip():
            raise ValidationError("'cloze' note requires a non-empty 'text'")
        if not has_cloze_deletion(text):
            raise ValidationError(
                "'cloze' note 'text' must contain a cloze deletion, "
                "e.g. {{c1::...}} or the [[...]] shorthand"
            )
