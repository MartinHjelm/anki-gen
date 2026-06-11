"""Vendored MathJax support for the reference HTML page.

Anki renders LaTeX written with ``\\(...\\)`` (inline) and ``\\[...\\]`` (display)
via its own built-in MathJax, so equations work in the ``.apkg`` with no help from
us. The reference HTML page has no such engine, so to render the *same* source
identically we inline a vendored MathJax build into the page's ``<head>``.

The SVG-output build (``vendor/mathjax/tex-svg-full.js``) is used deliberately: it
embeds glyph paths in the JS, so the page needs no external font files and renders
offline. We inline it only when a deck actually contains math (see
:func:`deck_has_math`), keeping math-free pages lean.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .schema import Deck

MATHJAX_JS_PATH = (
    Path(__file__).resolve().parent.parent / "vendor" / "mathjax" / "tex-svg-full.js"
)

# A card "has math" if any field contains an opening LaTeX delimiter that matches
# Anki's MathJax: ``\(`` (inline) or ``\[`` (display). In a Python source string
# the pattern below is a single backslash followed by ``(`` or ``[``.
_MATH_DELIMITER = re.compile(r"\\[(\[]")

# Configure MathJax before the library script runs. Delimiters are pinned to
# Anki's (``\(...\)`` / ``\[...\]``) so the YAML source renders identically in both
# outputs; ``$...$`` is intentionally *not* enabled, so literal dollar signs in
# card text are never mistaken for math. ``fontCache: 'global'`` dedupes repeated
# glyphs across the page into shared ``<defs>``.
_CONFIG_JS = (
    "window.MathJax={"
    "tex:{inlineMath:[['\\\\(','\\\\)']],displayMath:[['\\\\[','\\\\]']]},"
    "svg:{fontCache:'global'}"
    "};"
)


def deck_has_math(deck: Deck) -> bool:
    """True if any card field in ``deck`` contains a LaTeX delimiter.

    Used to decide whether the (large) MathJax bundle is worth inlining; a deck
    with no equations renders a lean page with no script at all.
    """
    for section in deck.sections:
        for card in section.cards:
            for value in card.fields.values():
                if _MATH_DELIMITER.search(value):
                    return True
    return False


@lru_cache(maxsize=1)
def load_mathjax_js() -> str:
    """Return the vendored MathJax library source (cached after first read)."""
    if not MATHJAX_JS_PATH.exists():
        raise FileNotFoundError(
            f"vendored MathJax not found at {MATHJAX_JS_PATH}; "
            "re-download es5/tex-svg-full.js (see vendor/mathjax/README.md)"
        )
    return MATHJAX_JS_PATH.read_text(encoding="utf-8")


def mathjax_head_html() -> str:
    """Return the ``<script>`` block to inline MathJax into the page ``<head>``.

    The config script must precede the library script so MathJax reads it on load.
    """
    return f"<script>{_CONFIG_JS}</script>\n<script>{load_mathjax_js()}</script>"
