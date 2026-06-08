"""Batch conversion orchestration."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from mail2md.parsers import UnsupportedFormatError, parse_path
from mail2md.render import render_document

SUPPORTED_SUFFIXES = {".eml", ".msg", ".mbox", ".mbx"}


def discover_sources(source: Path, recursive: bool) -> Iterator[Path]:
    """Yield supported files in deterministic lexical order."""

    if source.is_file():
        yield source
        return
    if not source.is_dir():
        raise FileNotFoundError(source)

    iterator = source.rglob("*") if recursive else source.glob("*")
    for path in sorted(iterator):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def convert(source: Path, output: Path, recursive: bool = True) -> list[Path]:
    """Convert every supported message and return the generated Markdown paths."""

    generated: list[Path] = []
    for path in discover_sources(source, recursive):
        try:
            documents = parse_path(path)
        except UnsupportedFormatError:
            continue
        for document in documents:
            generated.append(render_document(document, output))
    return generated

