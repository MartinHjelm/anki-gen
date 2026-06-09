"""Locate and read theme stylesheets shared by the Anki cards and HTML page."""

from __future__ import annotations

from pathlib import Path

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"


def theme_path(theme: str = "default") -> Path:
    return THEMES_DIR / f"{theme}.css"


def load_theme_css(theme: str = "default") -> str:
    """Return the CSS text for ``theme``.

    Raises :class:`FileNotFoundError` if the theme does not exist, listing the
    themes that are available.
    """
    path = theme_path(theme)
    if not path.exists():
        available = sorted(p.stem for p in THEMES_DIR.glob("*.css"))
        raise FileNotFoundError(
            f"theme {theme!r} not found in {THEMES_DIR} "
            f"(available: {', '.join(available) or 'none'})"
        )
    return path.read_text(encoding="utf-8")
