"""Command-line interface for anki-gen.

Usage:
    python -m anki_gen.cli build input.yaml -o deck.apkg [--html page.html]

Builds an Anki ``.apkg`` from a YAML source, and optionally a reference HTML
page from the same source.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .builder import write_deck
from .htmlpage import write_page
from .loader import load_deck
from .schema import ValidationError


def build_command(args: argparse.Namespace) -> int:
    try:
        deck = load_deck(args.input)
    except (ValidationError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output) if args.output else Path(args.input).with_suffix(".apkg")
    stats = write_deck(deck, out)

    print(f"Wrote {out}")
    print(f"  notes: {stats.notes}  cards: {stats.cards}")
    for note_type, count in sorted(stats.by_type.items()):
        print(f"    {note_type}: {count} notes")

    if args.html:
        write_page(deck, args.html)
        print(f"Wrote {args.html}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anki-gen", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build an .apkg (and optional HTML page)")
    build.add_argument("input", help="path to the YAML deck definition")
    build.add_argument("-o", "--output", help="output .apkg path (default: <input>.apkg)")
    build.add_argument("--html", help="also write a reference HTML page to this path")
    build.set_defaults(func=build_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
