"""Resolve, normalize, and stage card images for the ``.apkg`` and HTML page.

A card's ``image`` is just a reference — a local file path or an ``http(s)`` URL.
This module turns each distinct reference into a :class:`ResolvedMedia`: a real
file on disk under a content-hashed, collision-free basename, plus the MIME type.

The pipeline per reference is **fetch -> normalize -> stage**:

* **fetch**   read a local file, or download a URL (scheme/size/content-type guarded).
* **normalize** (raster only — SVG is vector and passes through untouched):
  downscale so the longest edge is at most :data:`MAX_IMAGE_EDGE_PX` (never upscale),
  re-encode photos as JPEG and anything with transparency as PNG, and strip metadata.
* **stage**   write the normalized bytes as ``{hash}_{stem}.{ext}`` so the file is
  unique within Anki's flat media namespace and stable across rebuilds.

Both builders consume the resulting ``{src: ResolvedMedia}`` map: ``builder`` bundles
``local_path`` into the package and references ``filename``; ``htmlpage`` inlines the
bytes via :func:`data_uri`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps

from .schema import Card, Deck

# Downscale target: the longest edge of a normalized raster image, in pixels.
# 1000px is crisp on retina phones while keeping files small. Smaller images are
# left at native size (we never upscale).
MAX_IMAGE_EDGE_PX = 1000
# JPEG quality for re-encoded photos (Pillow scale 1-95).
JPEG_QUALITY = 85
# Network guards for URL sources.
DOWNLOAD_TIMEOUT_S = 15
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MiB

_ALLOWED_SCHEMES = ("http", "https")
# Pillow modes that carry an alpha channel -> keep as PNG.
_ALPHA_MODES = ("RGBA", "LA", "PA")
# Content types that carry no real format signal; for these we may fall back to
# the URL's .svg suffix, but never override a server type that says otherwise.
_GENERIC_CONTENT_TYPES = ("", "application/octet-stream", "binary/octet-stream")
# Cap the human-readable stem so {hash}_{stem}.{ext} stays within the 255-byte
# filesystem limit (8 hex + separators + extension leave ample room).
_MAX_STEM_LEN = 200


class MediaError(ValueError):
    """Raised when an image reference cannot be resolved or is unsafe."""


@dataclass(frozen=True)
class ResolvedMedia:
    """A staged image ready for both outputs.

    ``filename`` is the bare basename used inside the ``.apkg`` (Anki's media
    namespace is flat, so it must be unique); ``local_path`` is the real file on
    disk that genanki bundles and that :func:`data_uri` reads.
    """

    src: str
    local_path: Path
    filename: str
    mime: str


def normalize_image(
    src_bytes: bytes, *, max_edge: int = MAX_IMAGE_EDGE_PX
) -> tuple[bytes, str, str]:
    """Downscale + re-encode raster bytes; return ``(bytes, mime, ext)``.

    Images larger than ``max_edge`` on their longest side are scaled down with
    aspect ratio preserved; smaller images are left unscaled. Images with
    transparency are emitted as optimized PNG; everything else as JPEG. Metadata
    (EXIF etc.) is dropped by re-encoding through a fresh buffer.
    """
    try:
        image = Image.open(io.BytesIO(src_bytes))
        image.load()
    except Exception as exc:  # Pillow raises a variety of types on bad input.
        raise MediaError(f"could not decode image data: {exc}") from exc

    # Bake in any EXIF orientation before we strip metadata, otherwise a phone
    # photo tagged "rotate 90" would render sideways once the tag is dropped.
    image = ImageOps.exif_transpose(image)

    # thumbnail() preserves aspect ratio and never upscales.
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

    has_alpha = image.mode in _ALPHA_MODES or "transparency" in image.info
    buf = io.BytesIO()
    if has_alpha:
        image.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "image/png", "png"

    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue(), "image/jpeg", "jpg"


def resolve_deck_media(deck: Deck, *, staging_dir: Path) -> dict[str, ResolvedMedia]:
    """Resolve every distinct ``card.image`` in ``deck`` into ``staging_dir``.

    Returns a ``{src: ResolvedMedia}`` map. Each distinct ``src`` is fetched,
    normalized, and staged exactly once.
    """
    staging_dir = Path(staging_dir)
    resolved: dict[str, ResolvedMedia] = {}

    for card in _image_cards(deck):
        src = card.image
        if src in resolved:
            continue
        resolved[src] = _resolve_one(src, staging_dir)

    return resolved


def data_uri(media: ResolvedMedia) -> str:
    """Return a base64 ``data:`` URI for ``media`` (for self-contained HTML)."""
    encoded = base64.b64encode(media.local_path.read_bytes()).decode("ascii")
    return f"data:{media.mime};base64,{encoded}"


# --- internals -------------------------------------------------------------


def _image_cards(deck: Deck):
    """Yield every card in ``deck`` that carries an image reference."""
    for section in deck.sections:
        for card in section.cards:
            if isinstance(card, Card) and card.image:
                yield card


def _resolve_one(src: str, staging_dir: Path) -> ResolvedMedia:
    raw, declared_type = _fetch(src)

    if _is_svg(src, declared_type, raw):
        out_bytes, mime, ext = raw, "image/svg+xml", "svg"
    else:
        out_bytes, mime, ext = normalize_image(raw)

    digest = hashlib.sha256(out_bytes).hexdigest()[:8]
    stem = _safe_stem(src)
    filename = f"{digest}_{stem}.{ext}"
    path = staging_dir / filename
    if not path.exists():
        path.write_bytes(out_bytes)

    return ResolvedMedia(src=src, local_path=path, filename=filename, mime=mime)


def _fetch(src: str) -> tuple[bytes, str | None]:
    """Return ``(bytes, content_type)`` for a local path or ``http(s)`` URL."""
    scheme = urlparse(src).scheme.lower()
    if scheme in _ALLOWED_SCHEMES:
        return _download(src)
    if scheme and scheme != "file":
        raise MediaError(f"unsupported URL scheme {scheme!r} in {src!r}")

    path = Path(src)
    if not path.is_file():
        raise MediaError(f"image file not found: {src}")
    return path.read_bytes(), None


def _download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "anki-gen"})
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S) as response:
            content_type = (response.getheader("Content-Type") or "").split(";")[0].strip()
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except urllib.error.URLError as exc:
        raise MediaError(f"failed to download {url}: {exc}") from exc

    if len(data) > MAX_DOWNLOAD_BYTES:
        raise MediaError(f"image exceeds {MAX_DOWNLOAD_BYTES} bytes: {url}")
    # Trust the server's Content-Type. Only fall back to the .svg URL suffix when
    # the server gave no real type — never let the suffix override a type that
    # explicitly says the body is something else (e.g. text/html).
    is_svg = content_type == "image/svg+xml" or (
        content_type in _GENERIC_CONTENT_TYPES and url.lower().endswith(".svg")
    )
    if not content_type.startswith("image/") and not is_svg:
        raise MediaError(
            f"expected an image at {url}, got Content-Type {content_type!r}"
        )
    return data, content_type


def _is_svg(src: str, content_type: str | None, data: bytes) -> bool:
    if content_type == "image/svg+xml" or src.lower().endswith(".svg"):
        return True
    head = data[:256].lstrip()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:256])


def _safe_stem(src: str) -> str:
    """A filesystem/Anki-safe stem derived from the source's basename."""
    name = Path(urlparse(src).path or src).stem or "image"
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")[:_MAX_STEM_LEN]
    return slug or "image"
