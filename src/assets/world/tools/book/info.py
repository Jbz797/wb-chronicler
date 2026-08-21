#!/usr/bin/env python3

# A single volume, reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.
# The handle is a book id — a town's `books` and a culture's both print it beside the title, each listing refs alone and leaving the volume itself here.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import (
    UNITS_PER_YEAR,
    books_held,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    load_data,
    load_save,
    parse_sections,
    take_chapter,
)

_ALL_SECTIONS = ("gains", "metadata", "origin", "teaches")
_BOOK_TRAITS = ("trait_id_actor", "trait_id_culture", "trait_id_language", "trait_id_religion")  # what a volume teaches, each absent where WB set none


# `{id, name}` off a book's own `<prefix>_id`/`<prefix>_name` pair — `None` where WB stamped neither (a book need carry no religion).
def _book_ref(book: dict, prefix: str) -> dict | None:
    ref_id = book.get(f"{prefix}_id")
    return None if ref_id is None else {"id": ref_id, "name": book.get(f"{prefix}_name")}


# The volume's identity card. `held_by` is the town shelving it now, which its author's need not be — a book travels, its stamps do not; `genre` drops the asset id.
def _build_metadata(book: dict, ctx: dict) -> dict:
    genre = load_data("books.json").get(book.get("book_type")) or {}
    return {
        "age": entity_age(book, ctx["world_time"]),
        "genre": {"description": genre.get("description"), "name": genre.get("name")},
        "held_by": entity_ref(ctx["city_of_book"]().get(book["id"]), ctx["cities_by_id"]),
        "last_read": int((ctx["world_time"] - float(book.get("timestamp_read_last_time") or 0)) / UNITS_PER_YEAR),  # years since the last reading WB stamped
        "name": book.get("name"),
        "times_read": book.get("times_read", 0),
    }


# Everything WB stamped on the volume at the writing — read off the book, never the registries: a dead author has left `actors_data`, their custom may be gone too.
def _build_origin(book: dict) -> dict:
    return {
        "author": _book_ref(book, "author"),
        "city": _book_ref(book, "author_city"),
        "clan": _book_ref(book, "author_clan"),
        "culture": _book_ref(book, "culture"),
        "kingdom": _book_ref(book, "author_kingdom"),
        "language": _book_ref(book, "language"),
        "religion": _book_ref(book, "religion"),
    }


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        book_id = int(argv[0])
    except ValueError:
        print(f"invalid id: {argv[0]}", file=sys.stderr)
        return 1

    requested = argv[1] if len(argv) > 1 else None
    try:
        sections = parse_sections(requested, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    book = next((b for b in save.get("books") or [] if b.get("id") == book_id), None)  # one lookup, and a world holds a few dozen volumes at most
    if book is None:
        print(f"unknown book: {book_id}", file=sys.stderr)
        return 1

    ctx = {
        "cities_by_id": index_by_id(save.get("cities") or []),
        "city_of_book": lambda: books_held(save)[2],  # custody, not authorship; called not stored, a 15 k-row walk only `metadata` needs
        "world_time": save["mapStats"]["world_time"],
    }

    out: dict = {}
    if "gains" in sections:  # the panel's « En lecture »: what a reader walks away with (WB `BookTypeAsset.base_stats`) — the genre's, not the volume's
        out["gains"] = (load_data("books.json").get(book.get("book_type")) or {}).get("read") or {}
    if "metadata" in sections:
        out["metadata"] = _build_metadata(book, ctx)
    if "origin" in sections:
        out["origin"] = _build_origin(book)
    if "teaches" in sections:  # the traits a volume passes on, each absent where WB set none — a reader may catch the custom, the tongue or the rite
        out["teaches"] = {field.removeprefix("trait_id_"): trait for field in _BOOK_TRAITS if (trait := book.get(field))}
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
