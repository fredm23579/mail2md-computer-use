"""Typed, provider-neutral email representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Attachment:
    """An attachment and the metadata needed to reconstruct its relationship."""

    filename: str
    content_type: str
    payload: bytes
    content_id: str | None = None
    disposition: str | None = None

    def __post_init__(self) -> None:
        """Defensive default for filename in case of empty strings."""
        if not self.filename:
            self.filename = "unnamed_attachment"


@dataclass(slots=True)
class EmailDocument:
    """Normalized email data without lossy provider-specific assumptions."""

    source_path: Path
    source_format: str
    raw_headers: list[tuple[str, str]]
    subject: str
    sender: str
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: list[str] = field(default_factory=list)
    date: str = ""
    message_id: str = ""
    body_text: str = ""
    body_html: str = ""
    attachments: list[Attachment] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure critical fields are strings to prevent downstream exceptions."""
        self.subject = str(self.subject) if self.subject is not None else "(No subject)"
        self.sender = str(self.sender) if self.sender is not None else "Unknown sender"


