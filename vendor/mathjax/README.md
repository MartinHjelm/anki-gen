# Vendored MathJax

`tex-svg-full.js` — MathJax **v3.2.2**, the all-in-one TeX-input → SVG-output
bundle (`es5/tex-svg-full.js`), downloaded from
<https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg-full.js>.

It is vendored (not loaded from a CDN) so the generated reference HTML page stays
a **single self-contained file that renders equations offline**. The SVG-output
build is used deliberately: it embeds glyph path data in the JS, so — unlike the
CommonHTML build — it needs **no external web-font files**.

`anki_gen/mathjax.py` inlines this file into the page's `<head>`, but only when a
deck actually contains math, so math-free pages are not bloated.

## License

MathJax is distributed under the Apache License 2.0.
See <https://github.com/mathjax/MathJax/blob/master/LICENSE>.

## Updating

Re-download the same `es5/tex-svg-full.js` asset for the desired version and bump
the version recorded here.
