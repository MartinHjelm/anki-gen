"""Tests for genanki model construction and theme loading."""

from pathlib import Path

import genanki
import pytest

from anki_gen.media import ResolvedMedia
from anki_gen.models import (
    MODEL_FIELDS,
    build_model,
    ordered_field_values,
    stable_id,
)
from anki_gen.schema import Card
from anki_gen.theme import load_theme_css

CSS = ".card { color: red; }"


def _media(src, filename="ab12cd34_pic.jpg"):
    return {src: ResolvedMedia(src=src, local_path=Path(filename),
                               filename=filename, mime="image/jpeg")}


def test_basic_model_has_one_template_and_shared_css():
    model = build_model("basic", CSS)
    assert len(model.templates) == 1
    assert model.css == CSS


def test_reversed_model_has_two_templates():
    model = build_model("reversed", CSS)
    assert len(model.templates) == 2


def test_cloze_model_uses_cloze_type():
    model = build_model("cloze", CSS)
    assert model.model_type == genanki.Model.CLOZE
    assert len(model.templates) == 1


def test_unknown_note_type_raises():
    with pytest.raises(ValueError):
        build_model("flashy", CSS)


def test_stable_id_is_deterministic_and_in_range():
    a = stable_id("anki_gen::model::basic")
    b = stable_id("anki_gen::model::basic")
    assert a == b
    assert (1 << 30) <= a < (1 << 31)


def test_ordered_field_values_match_model_field_count():
    basic = Card("basic", {"front": "f", "back": "b"}, term="T", tier="Tier 1")
    cloze = Card("cloze", {"text": "{{c1::x}}"}, term="T", tier="Tier 1")

    assert len(ordered_field_values(basic)) == len(MODEL_FIELDS["basic"])
    assert len(ordered_field_values(cloze)) == len(MODEL_FIELDS["cloze"])


def _image_fields(values, note_type="basic"):
    fields = MODEL_FIELDS[note_type]
    return (
        values[fields.index("ImageFront")],
        values[fields.index("ImageBack")],
    )


def test_image_fields_present_in_every_model():
    for note_type in ("basic", "reversed", "cloze"):
        assert "ImageFront" in MODEL_FIELDS[note_type]
        assert "ImageBack" in MODEL_FIELDS[note_type]


def test_question_template_renders_front_image_answer_renders_back():
    model = build_model("basic", CSS)
    qfmt = model.templates[0]["qfmt"]
    afmt = model.templates[0]["afmt"]
    assert "{{#ImageFront}}" in qfmt and "media" in qfmt
    assert "{{#ImageBack}}" in afmt and "media" in afmt


def test_ordered_field_values_embeds_image_tag_when_media_present():
    card = Card("basic", {"front": "f", "back": "b"}, image="pics/x.png")
    front, back = _image_fields(ordered_field_values(card, _media("pics/x.png")))

    # default side is "both" -> image on each side
    assert '<img src="ab12cd34_pic.jpg"' in front
    assert '<img src="ab12cd34_pic.jpg"' in back


def test_ordered_field_values_renders_credit_as_figcaption():
    card = Card("basic", {"front": "f", "back": "b"},
                image="pics/x.png", image_credit="CC BY-SA")
    front, _ = _image_fields(ordered_field_values(card, _media("pics/x.png")))

    assert "<figcaption>CC BY-SA</figcaption>" in front


def test_ordered_field_values_image_empty_without_media():
    card = Card("basic", {"front": "f", "back": "b"}, image="pics/x.png")
    front, back = _image_fields(ordered_field_values(card))  # no media map

    assert front == "" and back == ""


def test_image_side_back_fills_only_answer():
    card = Card("basic", {"front": "f", "back": "b"},
                image="pics/x.png", image_side="back")
    front, back = _image_fields(ordered_field_values(card, _media("pics/x.png")))

    assert front == ""  # hidden until the answer
    assert '<img src="ab12cd34_pic.jpg"' in back


def test_image_side_front_fills_only_question():
    card = Card("basic", {"front": "f", "back": "b"},
                image="pics/x.png", image_side="front")
    front, back = _image_fields(ordered_field_values(card, _media("pics/x.png")))

    assert '<img src="ab12cd34_pic.jpg"' in front
    assert back == ""


def test_default_theme_loads_and_targets_card_class():
    css = load_theme_css("default")
    assert ".card" in css


def test_missing_theme_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        load_theme_css("does-not-exist")
