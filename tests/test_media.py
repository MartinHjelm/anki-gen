"""Tests for image resolution, normalization, and staging (anki_gen.media)."""

import io

import pytest
from PIL import Image

from anki_gen.media import (
    MAX_IMAGE_EDGE_PX,
    MediaError,
    ResolvedMedia,
    _safe_stem,
    data_uri,
    normalize_image,
    resolve_deck_media,
)
from anki_gen.schema import Card, Deck, Section


# --- helpers ---------------------------------------------------------------

def _png_bytes(size, mode="RGB", color=(10, 20, 30)):
    """Return encoded PNG bytes for an image of ``size`` in ``mode``."""
    img = Image.new(mode, size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _deck_with_images(*image_paths):
    cards = tuple(
        Card("basic", {"front": f"q{i}", "back": f"a{i}"}, image=str(p))
        for i, p in enumerate(image_paths)
    )
    return Deck(name="D", sections=(Section(title="S", cards=cards),))


class _FakeResponse:
    """Minimal stand-in for urllib's HTTPResponse used as a context manager."""

    def __init__(self, data, content_type):
        self._data = data
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, amt=-1):
        if amt is None or amt < 0:
            data, self._data = self._data, b""
            return data
        chunk, self._data = self._data[:amt], self._data[amt:]
        return chunk

    def getheader(self, name, default=None):
        return self.headers.get(name, default)


# --- normalize_image -------------------------------------------------------

def test_normalize_downscales_to_longest_edge():
    big = _png_bytes((1500, 900))

    out_bytes, mime, ext = normalize_image(big)

    w, h = Image.open(io.BytesIO(out_bytes)).size
    assert max(w, h) == MAX_IMAGE_EDGE_PX
    assert (w, h) == (1000, 600)  # aspect ratio preserved
    assert mime == "image/jpeg" and ext == "jpg"


def test_normalize_leaves_small_image_unscaled():
    small = _png_bytes((50, 40))

    out_bytes, _, _ = normalize_image(small)

    assert Image.open(io.BytesIO(out_bytes)).size == (50, 40)  # never upscales


def test_normalize_keeps_transparency_as_png():
    transparent = _png_bytes((40, 40), mode="RGBA", color=(0, 0, 0, 0))

    out_bytes, mime, ext = normalize_image(transparent)

    assert mime == "image/png" and ext == "png"
    assert Image.open(io.BytesIO(out_bytes)).mode in ("RGBA", "LA", "P")


def test_normalize_opaque_photo_becomes_jpeg():
    _, mime, ext = normalize_image(_png_bytes((300, 200)))
    assert mime == "image/jpeg" and ext == "jpg"


def test_normalize_applies_exif_orientation_before_stripping():
    # 20x10 image tagged "rotate 90" should come out transposed to 10x20.
    img = Image.new("RGB", (20, 10), (200, 50, 50))
    exif = img.getexif()
    exif[0x0112] = 6  # EXIF orientation: rotate 90° clockwise
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)

    out_bytes, _, _ = normalize_image(buf.getvalue())

    assert Image.open(io.BytesIO(out_bytes)).size == (10, 20)


# --- resolve_deck_media: local files --------------------------------------

def test_resolve_local_file_stages_with_hashed_name(tmp_path):
    src = tmp_path / "mito.png"
    src.write_bytes(_png_bytes((100, 100)))
    staging = tmp_path / "stage"
    staging.mkdir()

    media = resolve_deck_media(_deck_with_images(src), staging_dir=staging)

    resolved = media[str(src)]
    assert isinstance(resolved, ResolvedMedia)
    assert resolved.local_path.exists()
    assert resolved.local_path.parent == staging
    assert resolved.filename.endswith(".png") or resolved.filename.endswith(".jpg")
    assert "_" in resolved.filename  # {hash}_{stem}.{ext}


def test_resolve_missing_local_file_raises(tmp_path):
    missing = tmp_path / "nope.png"
    staging = tmp_path / "stage"
    staging.mkdir()

    with pytest.raises(MediaError, match="nope.png"):
        resolve_deck_media(_deck_with_images(missing), staging_dir=staging)


def test_resolve_dedupes_repeated_source(tmp_path):
    src = tmp_path / "shared.png"
    src.write_bytes(_png_bytes((80, 80)))
    staging = tmp_path / "stage"
    staging.mkdir()

    media = resolve_deck_media(
        _deck_with_images(src, src), staging_dir=staging
    )

    assert len(media) == 1
    assert len(list(staging.iterdir())) == 1


def test_resolve_is_deterministic_across_runs(tmp_path):
    src = tmp_path / "x.png"
    src.write_bytes(_png_bytes((120, 90)))
    staging = tmp_path / "stage"
    staging.mkdir()

    first = resolve_deck_media(_deck_with_images(src), staging_dir=staging)
    second = resolve_deck_media(_deck_with_images(src), staging_dir=staging)

    assert first[str(src)].filename == second[str(src)].filename


# --- resolve_deck_media: SVG pass-through ---------------------------------

def test_resolve_svg_passes_through_untouched(tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg>'
    src = tmp_path / "diagram.svg"
    src.write_bytes(svg)
    staging = tmp_path / "stage"
    staging.mkdir()

    media = resolve_deck_media(_deck_with_images(src), staging_dir=staging)

    resolved = media[str(src)]
    assert resolved.mime == "image/svg+xml"
    assert resolved.filename.endswith(".svg")
    assert resolved.local_path.read_bytes() == svg  # vector left untouched


# --- resolve_deck_media: URLs ---------------------------------------------

def test_resolve_url_downloads_and_normalizes(tmp_path, monkeypatch):
    import anki_gen.media as media_mod

    url = "https://example.org/golgi.png"
    monkeypatch.setattr(
        media_mod.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(_png_bytes((1500, 750)), "image/png"),
    )
    staging = tmp_path / "stage"
    staging.mkdir()

    media = resolve_deck_media(_deck_with_images(url), staging_dir=staging)

    resolved = media[url]
    assert resolved.local_path.exists()
    w, h = Image.open(io.BytesIO(resolved.local_path.read_bytes())).size
    assert max(w, h) == MAX_IMAGE_EDGE_PX


def test_resolve_url_rejects_non_http_scheme(tmp_path):
    staging = tmp_path / "stage"
    staging.mkdir()

    with pytest.raises(MediaError, match="scheme"):
        resolve_deck_media(
            _deck_with_images("ftp://example.org/x.png"), staging_dir=staging
        )


def test_resolve_url_rejects_non_image_content_type(tmp_path, monkeypatch):
    import anki_gen.media as media_mod

    monkeypatch.setattr(
        media_mod.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(b"<html>not an image</html>", "text/html"),
    )
    staging = tmp_path / "stage"
    staging.mkdir()

    with pytest.raises(MediaError, match="image"):
        resolve_deck_media(
            _deck_with_images("https://example.org/page.html"),
            staging_dir=staging,
        )


def test_normalize_rejects_undecodable_bytes():
    with pytest.raises(MediaError, match="decode"):
        normalize_image(b"this is not an image")


def test_resolve_url_rejects_oversized_download(tmp_path, monkeypatch):
    import anki_gen.media as media_mod

    monkeypatch.setattr(media_mod, "MAX_DOWNLOAD_BYTES", 16)
    monkeypatch.setattr(
        media_mod.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(_png_bytes((50, 50)), "image/png"),
    )
    staging = tmp_path / "stage"
    staging.mkdir()

    with pytest.raises(MediaError, match="exceeds"):
        resolve_deck_media(
            _deck_with_images("https://example.org/big.png"), staging_dir=staging
        )


def test_resolve_svg_url_with_html_content_type_is_rejected(tmp_path, monkeypatch):
    import anki_gen.media as media_mod

    # A .svg URL must NOT bypass the content-type guard when the server says
    # the body is HTML — otherwise non-image content gets staged as an image.
    monkeypatch.setattr(
        media_mod.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(b"<html>nope</html>", "text/html"),
    )
    staging = tmp_path / "stage"
    staging.mkdir()

    with pytest.raises(MediaError, match="image"):
        resolve_deck_media(
            _deck_with_images("https://example.org/payload.svg"),
            staging_dir=staging,
        )


def test_resolve_svg_url_with_generic_content_type_passes_through(tmp_path, monkeypatch):
    import anki_gen.media as media_mod

    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    # Servers often serve .svg as application/octet-stream; the suffix is a valid
    # tiebreaker only when the type is generic.
    monkeypatch.setattr(
        media_mod.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(svg, "application/octet-stream"),
    )
    staging = tmp_path / "stage"
    staging.mkdir()

    media = resolve_deck_media(
        _deck_with_images("https://example.org/diagram.svg"), staging_dir=staging
    )

    assert media["https://example.org/diagram.svg"].mime == "image/svg+xml"


def test_safe_stem_is_length_capped():
    long_name = "a" * 500
    stem = _safe_stem(f"https://example.org/{long_name}.png")

    assert 0 < len(stem) <= 200


def test_resolve_svg_over_url_passes_through(tmp_path, monkeypatch):
    import anki_gen.media as media_mod

    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    monkeypatch.setattr(
        media_mod.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(svg, "image/svg+xml"),
    )
    staging = tmp_path / "stage"
    staging.mkdir()

    media = resolve_deck_media(
        _deck_with_images("https://example.org/diagram.svg"), staging_dir=staging
    )

    resolved = media["https://example.org/diagram.svg"]
    assert resolved.mime == "image/svg+xml"
    assert resolved.local_path.read_bytes() == svg


# --- data_uri --------------------------------------------------------------

def test_data_uri_inlines_base64(tmp_path):
    src = tmp_path / "i.png"
    src.write_bytes(_png_bytes((30, 30)))
    staging = tmp_path / "stage"
    staging.mkdir()

    media = resolve_deck_media(_deck_with_images(src), staging_dir=staging)
    uri = data_uri(media[str(src)])

    assert uri.startswith("data:image/")
    assert ";base64," in uri
