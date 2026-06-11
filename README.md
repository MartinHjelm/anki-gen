# anki-gen

A generic Anki deck generator. Author your cards once in a simple **YAML** file
and build both:

- an Anki **`.apkg`** deck, and
- a browsable **reference HTML page**,

from a **single shared stylesheet** (`themes/default.css`) — so the cards and the page always look the same.

Good thing about apkg files is that you can iterate on a deck without destroying previous practice rounds when importing the changed deck.

## Install

```bash
pip install -r requirements-pip.txt
```

## Quick start

```bash
python -m anki_gen.cli build tests/fixtures/sample.yaml -o demo.apkg --html demo.html
```

Then double-click `demo.apkg` (or **File → Import** in Anki) to install the deck.
Re-running on edited input **updates** existing notes instead of creating
duplicates (note GUIDs are derived from card content).

## YAML format

```yaml
deck: "My Deck"          # required — also seeds stable deck/model IDs
description: "What this deck covers."  # optional — shown on the HTML page
                                        # header AND on Anki's deck overview
theme: default           # optional — themes/<name>.css
tags: [tag1, tag2]       # optional — merged onto every card
note_type: basic         # optional deck-level default

sections:
  - title: "Section name"
    note_type: reversed   # optional — overrides the deck default
    cards:
      - q: "Question?"     # `q`/`a` are aliases for `front`/`back`
        a: "Answer"
        term: "Topic"      # optional badge shown on the card
        extra: "Footnote"  # optional, shown under the answer
        image: pics/x.png  # optional — local path (relative to this YAML) or URL
        image_credit: "Source, CC BY-SA 4.0"  # optional caption under the image
```

`note_type` resolves with precedence: **card > section > deck** (default `basic`).

## Note types

| `note_type` | Fields | Cards produced |
|---|---|---|
| `basic` | `front`/`q`, `back`/`a`, optional `extra` | 1 (front → back) |
| `reversed` | `front`/`q`, `back`/`a`, optional `extra` | 2 (both directions) |
| `cloze` | `text` (with blanks), optional `extra` | 1 per cloze group |

### Cloze (fill-in-the-blank)

Write blanks with the friendly `[[...]]` shorthand, or Anki's native
`{{cN::...}}` syntax — you can mix both:

```yaml
- note_type: cloze
  text: "Water boils at [[100]] °C; ice melts at {{c2::0}} °C."
```

`[[...]]` deletions are numbered automatically, continuing past any explicit
`{{cN::}}` so indices never collide. Each distinct `cN` index becomes one card.

## Images

Add `image:` to any card to illustrate it. The reference is either a **local
path** (resolved relative to the YAML file) or an **`http(s)` URL** (downloaded at
build time). An optional `image_credit:` renders as a caption beneath the image.

```yaml
- q: "Which organelle is the cell's powerhouse?"
  a: "Mitochondrion"
  image: pics/mitochondrion.png
  image_credit: "Wikimedia Commons, CC BY-SA 4.0"
- q: "Order the cell cycle phases"
  a: "G1 → S → G2 → M"
  image: diagrams/cell-cycle.svg          # SVG is kept as-is (vector)
- q: "What does a Golgi apparatus look like?"
  a: "A stack of flattened membrane sacs"
  image: pics/golgi.png
  image_side: back                        # hidden until you reveal the answer
```

### Where the image appears (`image_side`)

| `image_side` | Shown on |
|---|---|
| `both` *(default)* | question **and** answer |
| `front` | question only |
| `back` | answer only — **hidden until you flip the card** |

Use `back` when the image *is* the answer (or would give it away). On the
reference page, a `back` image appears in the Answer column to mirror this.

On build, each image is:

- **normalized** — raster images are downscaled so the longest edge is ≤ 1000px
  (crisp on phones, small files), re-encoded (photos → JPEG, transparency → PNG),
  and stripped of metadata. **SVGs pass through untouched.**
- **bundled** into the `.apkg` under a content-hashed filename, and **inlined** as a
  base64 data-URI in the HTML page (so the page stays a single self-contained file).

Re-running on an edited image updates the existing note rather than duplicating it.

There's a runnable demo at `tests/fixtures/sample_images.yaml`.

### Sourcing images (propose-and-review)

When asking an LLM to build a deck, the accuracy-first order is:

1. **Reuse the source page's own images** — if the deck comes from a URL (e.g. a
   Wikipedia article), its images are already topical and correctly licensed.
2. **Search Wikimedia Commons / Openverse** for the term when the source lacks one.
3. **Author an SVG diagram** for schematic concepts (cycles, labeled structures).

Avoid AI-generated images for factual cards — they are unreliable. Review the
proposed `image:` references in the YAML before building, and record attribution in
`image_credit:` if you plan to share the deck.

## Equations (LaTeX)

Write LaTeX inline with `\(...\)` and as a centered display block with `\[...\]` —
the same delimiters Anki uses. No new YAML fields: just put the math in any
`q`/`a`/`text`/`extra` content.

```yaml
- q: "State the mass–energy equivalence."
  a: 'Energy equals \(E = mc^2\).'
- q: "Write the Gaussian integral."
  a: 'A classic result: \[ \int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi} \]'
- note_type: cloze
  text: 'Euler''s identity is \( e^{i\pi} + [[1]] = 0 \).'
```

**Quoting:** LaTeX is full of backslashes, so wrap such values in **single quotes**
in YAML (double quotes treat `\` as an escape). A literal `'` inside a single-quoted
scalar is written `''` (see the cloze example).

Both outputs render the same source:

- **Anki deck** — uses Anki's **built-in MathJax**; nothing to install in the app.
- **Reference HTML page** — a vendored MathJax build (`vendor/mathjax/`, SVG output,
  Apache-2.0) is **inlined into the page**, so equations render **offline** and the
  page stays a single self-contained file. It is included **only when a deck
  actually contains math**, so math-free pages aren't bloated.

There's a runnable demo at `tests/fixtures/sample_equations.yaml`.

## Project layout

```
anki_gen/
  schema.py     # dataclasses + validation
  loader.py     # YAML -> Deck/Section/Card
  models.py     # genanki models for basic/reversed/cloze (share theme CSS)
  media.py      # resolve/download + normalize/stage card images
  builder.py    # Deck -> .apkg (deterministic IDs, content GUIDs)
  htmlpage.py   # Deck -> reference.html (same theme CSS)
  mathjax.py    # detect LaTeX + inline vendored MathJax into the HTML page
  theme.py      # locate/read themes/<name>.css
  cli.py        # `build` command
themes/default.css           # single styling source
vendor/mathjax/tex-svg-full.js  # inlined for offline equation rendering
tests/               # pytest suite (run: `pytest`)
```

## Tests

```bash
pytest --cov=anki_gen --cov-report=term-missing
```

## How to prompt Claude or any other LLM to get decent results as told by Claude
The ideal end state is a YAML file in your schema that I then build into .apkg + HTML — so the best prompts give me what I need to author good YAML.

The ideal request includes 5 things

  1. The source — a URL ("make a deck from https://en.wikipedia.org/wiki/Mitochondrion"), pasted text,
  or a local file path. URLs/Wikipedia are great because I can fetch them directly.
  2. Scope — what to cover and how deep. "Just the lead section" vs. "the whole article" vs. "only the
  section on X." Also roughly how many cards (e.g. "20–30 cards") so I don't under- or over-produce.
  3. Note type(s) — your schema supports three, and they suit different material:
    - basic — plain Q→A facts
    - reversed — when you need recall both directions (term↔definition, capital↔country)
    - cloze — fill-in-the-blank for definitions, dates, sequences

  You can say "use cloze for the definitions, basic for everything else" and I'll set note_type
  per-section.
  4. Angle / card style — "test me on dates and names," "conceptual understanding not trivia," "for an
  exam on X." This shapes which facts become cards and how questions are framed.
  5. Output prefs — deck name, tags, a one-line description, theme (you only have default right now),
  and the output filenames.

  A good prompt looks like

  ```
  "Build an Anki deck from https://en.wikipedia.org/wiki/Baltic_states — focus on geography and modern history, ~25 cards. Use reversed for country/capital pairs and basic for the rest. Deck name 'Baltic States', tags [geography, history]. Write it to baltic.yaml, then build baltic.apkg + baltic.html. Find and use images when it fits and helps the understanding of the question/answer. Images should always be above the text. In the README.md you will find all the instructions you need."
  ```

  That gives me everything to: fetch → draft YAML → run python -m anki_gen.cli build baltic.yaml -o 
  baltic.apkg --html baltic.html → show you the result.

  Tips for quality output

  - Iterate on the YAML, not the deck. Ask me to draft the YAML first, review it, then build. Cards are
  easy to tweak in YAML; rebuilding is cheap and updates existing notes (GUIDs are content-derived), so
  editing later won't create duplicates.
  - Atomic cards beat fat ones. If you want one-fact-per-card (better for SRS), say so — otherwise I'll
  use reasonable judgment.
  - For cloze, tell me what to blank ("blank the years and the key terms") — otherwise I'll pick the
  load-bearing words.
  - Paste text when the source is paywalled/dynamic — fetching JS-heavy pages can be unreliable.