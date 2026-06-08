"""Deterministic parsers for common exported email formats."""

from __future__ import annotations

import mailbox
from collections.abc import Iterable, Iterator
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import formataddr, getaddresses
from pathlib import Path
from typing import Any, cast

from mail2md.models import Attachment, EmailDocument


class UnsupportedFormatError(ValueError):
    """Raised when a source is not a supported email export format."""


def _addresses(message: Message, header: str) -> list[str]:
    """Return RFC-aware, decoded mailbox strings while preserving display names."""

    values = message.get_all(header, [])
    return [formataddr((name, address)) for name, address in getaddresses(values) if address]


def _decoded_payload(part: Message) -> bytes:
    """Decode a MIME payload without executing or interpreting attachment content."""

    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    text = part.get_payload()
    if isinstance(text, str):
        return text.encode(part.get_content_charset() or "utf-8", errors="replace")
    return str(text).encode("utf-8", errors="replace")


def _attachment_payload(part: Message) -> bytes:
    """Serialize attached messages without merging their children into the parent."""

    if part.get_content_type() == "message/rfc822":
        payload = part.get_payload()
        if isinstance(payload, list) and payload and isinstance(payload[0], Message):
            return payload[0].as_bytes(policy=policy.default)
    return _decoded_payload(part)


def _text_content(part: Message) -> str:
    """Decode text using the MIME charset, replacing only invalid byte sequences."""

    if isinstance(part, EmailMessage):
        try:
            content = part.get_content()
            return content if isinstance(content, str) else str(content)
        except (LookupError, UnicodeDecodeError):
            pass
    return _decoded_payload(part).decode(part.get_content_charset() or "utf-8", errors="replace")


def _from_message(message: Message, source: Path, source_format: str) -> EmailDocument:
    """Normalize an email.message object while retaining every original header."""

    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[Attachment] = []

    def visit(part: Message) -> None:
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        content_type = part.get_content_type()

        if disposition == "attachment" or filename or content_type == "message/rfc822":
            attachments.append(
                Attachment(
                    filename=filename
                    or (
                        "attached-message.eml"
                        if content_type == "message/rfc822"
                        else "unnamed-attachment"
                    ),
                    content_type=content_type,
                    payload=_attachment_payload(part),
                    content_id=part.get("Content-ID"),
                    disposition=disposition,
                )
            )
            return

        if part.is_multipart():
            payload = part.get_payload()
            if isinstance(payload, list):
                for child in payload:
                    if isinstance(child, Message):
                        visit(child)
            return

        if content_type == "text/plain":
            plain_parts.append(_text_content(part))
        elif content_type == "text/html":
            html_parts.append(_text_content(part))

    visit(message)

    return EmailDocument(
        source_path=source,
        source_format=source_format,
        raw_headers=list(message.raw_items()),
        subject=str(message.get("Subject", "")),
        sender=str(message.get("From", "")),
        to=_addresses(message, "To"),
        cc=_addresses(message, "Cc"),
        bcc=_addresses(message, "Bcc"),
        reply_to=_addresses(message, "Reply-To"),
        date=str(message.get("Date", "")),
        message_id=str(message.get("Message-ID", "")),
        body_text="\n\n".join(part.strip() for part in plain_parts if part.strip()),
        body_html="\n".join(part for part in html_parts if part.strip()),
        attachments=attachments,
    )


def parse_eml(path: Path) -> EmailDocument:
    """Parse an RFC 5322/MIME .eml file."""

    with path.open("rb") as source:
        message = BytesParser(policy=policy.default).parse(source)
    return _from_message(message, path, "eml")


def parse_mbox(path: Path) -> Iterator[EmailDocument]:
    """Yield each message from an mbox without modifying mailbox state."""

    box = mailbox.mbox(path, create=False)
    try:
        for index, message in enumerate(box):
            synthetic_source = path.with_name(f"{path.name}#message-{index + 1}")
            yield _from_message(message, synthetic_source, "mbox")
    finally:
        box.close()


def parse_msg(path: Path) -> EmailDocument:
    """Parse a Microsoft Outlook .msg file through extract-msg."""

    import extract_msg

    message: Any = extract_msg.Message(path)  # type: ignore[no-untyped-call]
    try:
        raw_html: bytes | str = message.htmlBody or b""
        html_body = (
            raw_html.decode("utf-8", errors="replace") if isinstance(raw_html, bytes) else raw_html
        )

        attachments = []
        for index, raw_attachment in enumerate(message.attachments):
            attachment = cast(Any, raw_attachment)
            raw_data: Any = attachment.data
            if isinstance(raw_data, bytes):
                data = raw_data
            elif hasattr(raw_data, "exportBytes"):
                data = cast(bytes, raw_data.exportBytes())
            elif raw_data is None:
                data = b""
            else:
                data = str(raw_data).encode("utf-8", errors="replace")
            filename = (
                getattr(attachment, "longFilename", None)
                or getattr(attachment, "shortFilename", None)
                or getattr(attachment, "name", None)
                or f"attachment-{index + 1}"
            )
            attachments.append(
                Attachment(
                    filename=str(filename),
                    content_type=str(
                        getattr(attachment, "mimetype", None)
                        or (
                            "application/vnd.ms-outlook"
                            if hasattr(raw_data, "exportBytes")
                            else "application/octet-stream"
                        )
                    ),
                    payload=data,
                    content_id=getattr(attachment, "cid", None),
                )
            )

        headers = [
            ("Subject", message.subject or ""),
            ("From", message.sender or ""),
            ("To", message.to or ""),
            ("Cc", message.cc or ""),
            ("Date", str(message.date or "")),
            ("Message-ID", message.messageId or ""),
        ]
        return EmailDocument(
            source_path=path,
            source_format="msg",
            raw_headers=[(name, value) for name, value in headers if value],
            subject=message.subject or "",
            sender=message.sender or "",
            to=[value.strip() for value in (message.to or "").split(";") if value.strip()],
            cc=[value.strip() for value in (message.cc or "").split(";") if value.strip()],
            date=str(message.date or ""),
            message_id=message.messageId or "",
            body_text=message.body or "",
            body_html=html_body,
            attachments=attachments,
        )
    finally:
        message.close()


def parse_path(path: Path) -> Iterable[EmailDocument]:
    """Dispatch a supported source path to its parser."""

    suffix = path.suffix.lower()
    if suffix == ".eml":
        return [parse_eml(path)]
    if suffix == ".msg":
        return [parse_msg(path)]
    if suffix in {".mbox", ".mbx"}:
        return parse_mbox(path)
    raise UnsupportedFormatError(f"Unsupported email format: {path}")
