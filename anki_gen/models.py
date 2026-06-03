"""genanki note models for each supported note type.

All three models share the same theme CSS so cards look identical regardless of
type. Model IDs are derived deterministically from a stable string, so the same
model is reused across runs (Anki updates rather than duplicating).

Card chrome (``Term`` / ``Tier``) renders conditionally via Mustache sections,
so a plain front/back card stays clean while richer cards gain context badges.
"""

from __future__ import annotations

import hashlib

import genanki

from .schema import Card

# Field order per note type. The builder must supply values in this order.
MODEL_FIELDS: dict[str, list[str]] = {
    "basic": ["Front", "Back", "Extra", "Term", "Tier"],
    "reversed": ["Front", "Back", "Extra", "Term", "Tier"],
    "cloze": ["Text", "Extra", "Term", "Tier"],
}

_HINT = '{{#Tier}}<div class="hint">{{Tier}}</div>{{/Tier}}'
_TERM = '{{#Term}}<div class="term">{{Term}}</div>{{/Term}}'
_EXTRA = '{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}'
_TERM_TAG = '{{#Term}}<div class="meta"><span class="tag tag-term">{{Term}}</span></div>{{/Term}}'

_BASIC_FRONT = f"""
<div class="card">
  {_HINT}
  {_TERM}
  <div class="front">{{{{Front}}}}</div>
</div>
"""

_BASIC_BACK = f"""
<div class="card">
  {_TERM}
  <div class="front">{{{{Front}}}}</div>
  <hr>
  <div class="back">{{{{Back}}}}</div>
  {_EXTRA}
  {{{{#Tier}}}}<div class="meta"><span class="tag tag-tier">{{{{Tier}}}}</span></div>{{{{/Tier}}}}
</div>
"""

# Reverse direction (used as the 2nd template of the `reversed` model).
_REVERSE_FRONT = f"""
<div class="card">
  {_HINT}
  <div class="front">{{{{Back}}}}</div>
</div>
"""

_REVERSE_BACK = f"""
<div class="card">
  <div class="front">{{{{Back}}}}</div>
  <hr>
  <div class="back">{{{{Front}}}}</div>
  {_EXTRA}
  {_TERM_TAG}
</div>
"""

_CLOZE_FRONT = f"""
<div class="card">
  {_HINT}
  <div class="desc">{{{{cloze:Text}}}}</div>
</div>
"""

_CLOZE_BACK = f"""
<div class="card">
  {_HINT}
  <div class="desc">{{{{cloze:Text}}}}</div>
  {_EXTRA}
  {_TERM_TAG}
</div>
"""


def stable_id(text: str) -> int:
    """Deterministic ID in genanki's recommended range [2^30, 2^31)."""
    digest = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    return (digest % (1 << 30)) + (1 << 30)


def build_model(note_type: str, css: str) -> genanki.Model:
    """Build the genanki model for ``note_type`` with the given ``css``."""
    if note_type not in MODEL_FIELDS:
        raise ValueError(f"unknown note_type {note_type!r}")

    fields = [{"name": name} for name in MODEL_FIELDS[note_type]]
    model_id = stable_id(f"anki_gen::model::{note_type}")

    if note_type == "basic":
        return genanki.Model(
            model_id,
            "anki_gen Basic",
            fields=fields,
            templates=[{"name": "Card 1", "qfmt": _BASIC_FRONT, "afmt": _BASIC_BACK}],
            css=css,
        )
    if note_type == "reversed":
        return genanki.Model(
            model_id,
            "anki_gen Basic (and reversed)",
            fields=fields,
            templates=[
                {"name": "Card 1", "qfmt": _BASIC_FRONT, "afmt": _BASIC_BACK},
                {"name": "Card 2", "qfmt": _REVERSE_FRONT, "afmt": _REVERSE_BACK},
            ],
            css=css,
        )
    # cloze
    return genanki.Model(
        model_id,
        "anki_gen Cloze",
        fields=fields,
        templates=[{"name": "Cloze", "qfmt": _CLOZE_FRONT, "afmt": _CLOZE_BACK}],
        css=css,
        model_type=genanki.Model.CLOZE,
    )


def ordered_field_values(card: Card) -> list[str]:
    """Return ``card``'s field values ordered to match its model's fields."""
    f = card.fields
    if card.note_type == "cloze":
        return [f.get("text", ""), f.get("extra", ""), card.term, card.tier]
    return [
        f.get("front", ""),
        f.get("back", ""),
        f.get("extra", ""),
        card.term,
        card.tier,
    ]
