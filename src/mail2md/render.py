"""Stable Markdown rendering and attachment extraction."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from markdownify import markdownify

from mail2md.models import EmailDocument

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(value: str, fallback: str = "email") -> str:
    """Produce a portable filename and prevent path traversal."""

    name = _UNSAFE_FILENAME.sub("-", Path(value).name).strip("-.")
    return (name or fallback)[:120]


def _source_digest(document: EmailDocument) -> str:
    """Create a stable identity from every normalized content-bearing field."""

    identity = {
        "source": str(document.source_path),
        "format": document.source_format,
        "headers": document.raw_headers,
        "subject": document.subject,
        "sender": document.sender,
        "to": document.to,
        "cc": document.cc,
        "bcc": document.bcc,
        "reply_to": document.reply_to,
        "date": document.date,
        "message_id": document.message_id,
        "body_text": document.body_text,
        "body_html": document.body_html,
        "attachments": [
            {
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "content_id": attachment.content_id,
                "disposition": attachment.disposition,
                "sha256": hashlib.sha256(attachment.payload).hexdigest(),
            }
            for attachment in document.attachments
        ],
    }
    serialized = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8", errors="replace")).hexdigest()


def _yaml_value(value: object) -> str:
    """JSON strings and arrays are valid YAML and avoid hand-rolled escaping."""

    return json.dumps(value, ensure_ascii=False)


def _safe_directory(path: Path) -> None:
    """Create a directory while rejecting symlinked output boundaries."""

    if path.is_symlink():
        raise RuntimeError(f"Refusing symlinked output directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError(f"Unsafe output directory: {path}")


def _write_once(path: Path, data: bytes) -> None:
    """Write a new file exclusively, permitting only identical idempotent reruns."""

    if path.is_symlink():
        raise RuntimeError(f"Refusing symlinked output file: {path}")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if not path.is_file() or path.is_symlink() or path.read_bytes() != data:
            raise FileExistsError(f"Refusing to overwrite existing output: {path}") from None
        return
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)


def _unique_attachment_name(filename: str, used_names: set[str]) -> str:
    """Return a portable filename unique under case-insensitive filesystems."""

    candidate = filename
    stem = Path(filename).stem or "attachment"
    suffix = Path(filename).suffix
    counter = 2
    while candidate.casefold() in used_names:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    used_names.add(candidate.casefold())
    return candidate


def _fenced_text(value: str, language: str = "text") -> str:
    """Fence untrusted text with a delimiter longer than any embedded run."""

    longest = max((len(match.group(0)) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{value}\n{fence}"


def _heading(value: str) -> str:
    """Render untrusted text as a single escaped Markdown heading."""

    single_line = " ".join(value.splitlines()) or "(No subject)"
    return re.sub(r"([\`*_{}\[\]()#+.!|>-])", r"\\\1", single_line)


def render_document(document: EmailDocument, output_root: Path) -> Path:
    """Write one email as Markdown plus inert attachment bytes."""

    digest = _source_digest(document)
    stem = safe_name(document.subject, fallback="untitled")
    email_dir = output_root / f"{stem}-{digest[:12]}"
    attachment_dir = email_dir / "attachments"
    _safe_directory(output_root)
    _safe_directory(email_dir)

    attachment_rows: list[str] = []
    used_names: set[str] = set()
    cid_paths: dict[str, str] = {}
    for index, attachment in enumerate(document.attachments, start=1):
        filename = _unique_attachment_name(
            safe_name(attachment.filename, fallback=f"attachment-{index}"),
            used_names,
        )
        _safe_directory(attachment_dir)
        attachment_path = attachment_dir / filename
        _write_once(attachment_path, attachment.payload)
        checksum = hashlib.sha256(attachment.payload).hexdigest()
        if attachment.content_id:
            cid_paths[attachment.content_id.strip("<>").casefold()] = f"attachments/{filename}"
        attachment_rows.append(
            f"| [{filename}](attachments/{filename}) | `{attachment.content_type}` | "
            f"{len(attachment.payload)} | `{checksum}` |"
        )

    if document.body_text.strip():
        body = _fenced_text(document.body_text.strip())
    elif document.body_html.strip():
        html = document.body_html
        for content_id, relative_path in cid_paths.items():
            html = re.sub(
                rf"cid:{re.escape(content_id)}",
                relative_path,
                html,
                flags=re.IGNORECASE,
            )
        body = markdownify(html, heading_style="ATX").strip()
    else:
        body = "_No readable text or HTML body was present in the source email._"

    frontmatter = [
        "---",
        f"title: {_yaml_value(document.subject)}",
        f"from: {_yaml_value(document.sender)}",
        f"to: {_yaml_value(document.to)}",
        f"cc: {_yaml_value(document.cc)}",
        f"bcc: {_yaml_value(document.bcc)}",
        f"reply_to: {_yaml_value(document.reply_to)}",
        f"date: {_yaml_value(document.date)}",
        f"message_id: {_yaml_value(document.message_id)}",
        f"source_format: {_yaml_value(document.source_format)}",
        f"source_name: {_yaml_value(document.source_path.name)}",
        f"content_sha256: {_yaml_value(digest)}",
        f"attachment_count: {len(document.attachments)}",
        "---",
    ]
    sections = [
        "\n".join(frontmatter),
        f"# {_heading(document.subject)}",
        "## Message\n\n" + body,
    ]

    if document.body_html.strip():
        sections.append("## Original HTML\n\n" + _fenced_text(document.body_html, "html"))

    if attachment_rows:
        sections.append(
            "## Attachments\n\n"
            "| File | MIME type | Bytes | SHA-256 |\n"
            "|---|---|---:|---|\n" + "\n".join(attachment_rows)
        )

    raw_headers = "\n".join(f"{name}: {value}" for name, value in document.raw_headers)
    sections.append("## Raw Headers\n\n" + _fenced_text(raw_headers))

    output_path = email_dir / "email.md"
    markdown = ("\n\n".join(sections).rstrip() + "\n").encode("utf-8")
    _write_once(output_path, markdown)
    return output_path
