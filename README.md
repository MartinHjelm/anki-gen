# anki-gen

A generic Anki deck generator. Author your cards once in a simple **YAML** file
and build both:

- an Anki **`.apkg`** deck, and
- a browsable **reference HTML page**,

from a **single shared stylesheet** (`themes/default.css`) — so the cards and the
page always look the same.

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

## Note on the original Baltic deck

`make_anki_deck.py` and the `bal_*.html` files are the original, domain-specific
generator that scraped hand-authored HTML. They still work standalone. To move
that content onto anki-gen, transcribe it into a YAML file using the format
above (a future `import-html` command could automate this).
