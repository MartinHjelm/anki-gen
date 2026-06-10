"""Load a deck definition from YAML into the :mod:`anki_gen.schema` dataclasses.

The YAML schema (see README) supports:

    deck: "Deck name"          # required
    theme: default             # optional, default "default"
    tags: [a, b]               # optional, merged onto every card
    note_type: basic           # optional deck-level default
    sections:
      - title: "Section"
        note_type: reversed    # optional section override
        cards:
          - {q: "...", a: "..."}                 # basic/reversed (q/a aliases)
          - {front: "...", back: "...", extra: "..."}
          - {note_type: cloze, text: "... [[x]] ..."}

``note_type`` resolves with precedence: card > section > deck (default ``basic``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from .schema import (
    DEFAULT_IMAGE_SIDE,
    DEFAULT_NOTE_TYPE,
    Card,
    Deck,
    Section,
    ValidationError,
    convert_cloze_shorthand,
    validate_card_fields,
    validate_image_side,
)


def load_deck(path: str | Path) -> Deck:
    """Read a YAML file from ``path`` and parse it into a :class:`Deck`.

    Relative image paths are resolved against the YAML file's directory.
    """
    yaml_path = Path(path)
    raw = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValidationError("top-level YAML must be a mapping with a 'deck' key")
    return parse_deck(data, base_dir=yaml_path.resolve().parent)


def parse_deck(data: dict[str, Any], base_dir: Path | None = None) -> Deck:
    """Parse an already-loaded mapping into a validated :class:`Deck`.

    ``base_dir`` is the directory relative image paths resolve against (the YAML
    file's directory when called via :func:`load_deck`); it defaults to the
    current working directory.
    """
    base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    name = data.get("deck")
    if not name or not str(name).strip():
        raise ValidationError("missing required 'deck' name")

    theme = str(data.get("theme") or "default")
    description = str(data.get("description") or "")
    deck_tags = _as_str_tuple(data.get("tags"))
    deck_note_type = data.get("note_type", DEFAULT_NOTE_TYPE)

    sections: list[Section] = []
    for s_index, raw_section in enumerate(data.get("sections") or [], start=1):
        sections.append(
            _parse_section(raw_section, s_index, deck_note_type, deck_tags, base_dir)
        )

    return Deck(
        name=str(name),
        sections=tuple(sections),
        theme=theme,
        tags=deck_tags,
        description=description,
    )


def _parse_section(
    raw: dict[str, Any],
    s_index: int,
    deck_note_type: str,
    deck_tags: tuple[str, ...],
    base_dir: Path,
) -> Section:
    title = str(raw.get("title") or f"Section {s_index}")
    section_note_type = raw.get("note_type", deck_note_type)

    cards: list[Card] = []
    for c_index, raw_card in enumerate(raw.get("cards") or [], start=1):
        try:
            cards.append(
                _parse_card(raw_card, title, section_note_type, deck_tags, base_dir)
            )
        except ValidationError as exc:
            raise ValidationError(
                f"section {s_index} ('{title}') card {c_index}: {exc}"
            ) from exc

    return Section(title=title, cards=tuple(cards))


def _parse_card(
    raw: dict[str, Any],
    section_title: str,
    section_note_type: str,
    deck_tags: tuple[str, ...],
    base_dir: Path,
) -> Card:
    note_type = str(raw.get("note_type", section_note_type))

    fields = _build_fields(note_type, raw)
    validate_card_fields(note_type, fields)

    tags = deck_tags + _as_str_tuple(raw.get("tags"))
    term = str(raw.get("term") or "")
    tier = str(raw.get("tier") or section_title)
    image = _resolve_image_ref(str(raw.get("image") or ""), base_dir)
    image_credit = str(raw.get("image_credit") or "")
    image_side = str(raw.get("image_side") or DEFAULT_IMAGE_SIDE).lower()
    # Validate even without an image, so the same value can't pass now and fail
    # later once an image is added.
    validate_image_side(image_side)

    return Card(
        note_type=note_type,
        fields=fields,
        tags=tags,
        term=term,
        tier=tier,
        image=image,
        image_credit=image_credit,
        image_side=image_side,
    )


def _resolve_image_ref(ref: str, base_dir: Path) -> str:
    """Resolve a local image path against ``base_dir``; leave URLs untouched.

    Returns ``""`` for an empty reference. ``http(s)`` URLs pass through; relative
    local paths become absolute (so the builder can resolve them regardless of the
    process's working directory); absolute local paths are kept as-is.
    """
    if not ref:
        return ""
    if urlparse(ref).scheme in ("http", "https"):
        return ref
    path = Path(ref)
    return str(path if path.is_absolute() else base_dir / path)


def _build_fields(note_type: str, raw: dict[str, Any]) -> dict[str, str]:
    """Resolve note-type-specific fields, applying aliases and cloze shorthand."""
    if note_type == "cloze":
        fields = {"text": convert_cloze_shorthand(str(raw.get("text", "")))}
    else:
        # basic / reversed (and any unknown type, which validation will reject)
        fields = {
            "front": str(raw.get("front", raw.get("q", ""))),
            "back": str(raw.get("back", raw.get("a", ""))),
        }

    extra = raw.get("extra")
    if extra:
        fields["extra"] = str(extra)
    return fields


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)
