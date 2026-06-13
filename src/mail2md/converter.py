"""Batch conversion orchestration."""

from __future__ import annotations

from collections.abc import Iterator
import logging
from pathlib import Path

from mail2md.parsers import UnsupportedFormatError, parse_path
from mail2md.render import render_document

# Set up logging for defensive programming
logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".eml", ".msg", ".mbox", ".mbx"}


def discover_sources(source: Path, recursive: bool) -> Iterator[Path]:
    """
    Yield supported files in deterministic lexical order.
    Degrades gracefully by catching permission errors.
    """
    try:
        if source.is_file():
            yield source
            return
        if not source.is_dir():
            raise FileNotFoundError(f"Source directory not found: {source}")

        iterator = source.rglob("*") if recursive else source.glob("*")
        for path in sorted(iterator):
            try:
                if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                    yield path
            except PermissionError as e:
                logger.warning(f"Permission denied accessing file {path}: {e}")
    except Exception as e:
        logger.error(f"Error discovering sources in {source}: {e}")


def convert(source: Path, output: Path, recursive: bool = True) -> list[Path]:
    """
    Convert every supported message and return the generated Markdown paths.
    Wraps individual conversions in try/except blocks to prevent a single 
    corrupt file from halting the entire batch.
    """
    generated: list[Path] = []
    for path in discover_sources(source, recursive):
        try:
            documents = parse_path(path)
            for document in documents:
                try:
                    result_path = render_document(document, output)
                    generated.append(result_path)
                except Exception as doc_e:
                    logger.error(f"Error rendering document from {path}: {doc_e}")
        except UnsupportedFormatError:
            # Skip unsupported formats gracefully
            continue
        except Exception as e:
            logger.error(f"Unexpected error parsing file {path}: {e}")
            
    return generated


