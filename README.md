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

## Project layout

```
anki_gen/
  schema.py     # dataclasses + validation
  loader.py     # YAML -> Deck/Section/Card
  models.py     # genanki models for basic/reversed/cloze (share theme CSS)
  builder.py    # Deck -> .apkg (deterministic IDs, content GUIDs)
  htmlpage.py   # Deck -> reference.html (same theme CSS)
  theme.py      # locate/read themes/<name>.css
  cli.py        # `build` command
themes/default.css   # single styling source
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
  "Build an Anki deck from https://en.wikipedia.org/wiki/Baltic_states — focus on geography and modern history, ~25 cards. Use reversed for country/capital pairs and basic for the rest. Deck name 'Baltic States', tags [geography, history]. Write it to baltic.yaml, then build baltic.apkg + baltic.html. In the README.md you will find all the instructions you need."
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