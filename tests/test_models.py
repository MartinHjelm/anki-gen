"""Tests for genanki model construction and theme loading."""

import genanki
import pytest

from anki_gen.models import (
    MODEL_FIELDS,
    build_model,
    ordered_field_values,
    stable_id,
)
from anki_gen.schema import Card
from anki_gen.theme import load_theme_css

CSS = ".card { color: red; }"


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


def test_default_theme_loads_and_targets_card_class():
    css = load_theme_css("default")
    assert ".card" in css


def test_missing_theme_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        load_theme_css("does-not-exist")
