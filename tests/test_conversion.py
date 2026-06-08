"""Independent deterministic checks for parsing and Markdown rendering."""

from __future__ import annotations

import mailbox
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

import pytest

from mail2md.browser_agent import _host_allowed
from mail2md.converter import convert
from mail2md.models import Attachment, EmailDocument
from mail2md.parsers import parse_eml, parse_mbox
from mail2md.render import render_document, safe_name

FIXTURE = Path(__file__).parent / "fixtures" / "sample.eml"


def test_parse_eml_preserves_core_content_and_attachment() -> None:
    document = parse_eml(FIXTURE)

    assert document.subject == "Quarterly status & next steps"
    assert document.to == ["Bob Example <bob@example.com>"]
    assert "Revenue increased by 12%." in document.body_text
    assert document.attachments[0].payload == b"Follow up next week."
    assert ("Message-ID", "<sample-123@example.com>") in document.raw_headers


def test_convert_writes_markdown_and_attachment(tmp_path: Path) -> None:
    generated = convert(FIXTURE, tmp_path)

    markdown = generated[0].read_text(encoding="utf-8")
    assert "content_sha256:" in markdown
    assert "## Raw Headers" in markdown
    assert "[notes.txt](attachments/notes.txt)" in markdown
    attachment = generated[0].parent / "attachments" / "notes.txt"
    assert attachment.read_bytes() == b"Follow up next week."


def test_parse_mbox_yields_every_message(tmp_path: Path) -> None:
    with FIXTURE.open("rb") as source:
        message = BytesParser(policy=policy.default).parse(source)
    mbox_path = tmp_path / "archive.mbox"
    box = mailbox.mbox(mbox_path)
    box.add(message)
    box.add(message)
    box.flush()
    box.close()

    assert len(list(parse_mbox(mbox_path))) == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("../../secret.txt", "secret.txt"),
        ("A subject: with / punctuation", "punctuation"),
        ("", "email"),
    ],
)
def test_safe_name_blocks_path_traversal(value: str, expected: str) -> None:
    assert safe_name(value) == expected


def test_provider_allowlist_rejects_subdomain_tricks() -> None:
    assert _host_allowed("gmail", "https://mail.google.com/mail/u/0/")
    assert not _host_allowed("gmail", "https://mail.google.com.evil.example/")
    assert not _host_allowed("gmail", "https://example.com/")


def test_attached_email_is_not_merged_into_parent_body(tmp_path: Path) -> None:
    child = EmailMessage()
    child["Subject"] = "Nested secret"
    child.set_content("Nested body")

    parent = EmailMessage()
    parent["Subject"] = "Parent"
    parent["To"] = "Bob Example <bob@example.com>"
    parent.set_content("Parent body")
    parent.add_attachment(child, filename="forwarded.eml")
    source = tmp_path / "nested.eml"
    source.write_bytes(parent.as_bytes(policy=policy.default))

    document = parse_eml(source)

    assert document.to == ["Bob Example <bob@example.com>"]
    assert "Parent body" in document.body_text
    assert "Nested body" not in document.body_text
    assert document.attachments[0].filename == "forwarded.eml"
    assert b"Nested body" in document.attachments[0].payload


def test_distinct_attachments_produce_distinct_outputs(tmp_path: Path) -> None:
    common = {
        "source_path": Path("same.eml"),
        "source_format": "eml",
        "raw_headers": [],
        "subject": "Same",
        "sender": "sender@example.com",
        "body_text": "Body",
    }
    first = EmailDocument(
        **common,
        attachments=[Attachment("report.txt", "text/plain", b"first")],
    )
    second = EmailDocument(
        **common,
        attachments=[Attachment("report.txt", "text/plain", b"second")],
    )

    assert render_document(first, tmp_path) != render_document(second, tmp_path)


def test_attachment_names_never_overwrite_case_insensitively(tmp_path: Path) -> None:
    document = EmailDocument(
        source_path=Path("collision.eml"),
        source_format="eml",
        raw_headers=[],
        subject="Collision",
        sender="sender@example.com",
        body_text="Body",
        attachments=[
            Attachment("x", "application/octet-stream", b"first"),
            Attachment("X", "application/octet-stream", b"second"),
            Attachment("x", "application/octet-stream", b"third"),
        ],
    )

    output = render_document(document, tmp_path)
    files = sorted(
        (path.name, path.read_bytes()) for path in (output.parent / "attachments").iterdir()
    )

    assert files == [("X-2", b"second"), ("x", b"first"), ("x-3", b"third")]


def test_html_cid_references_point_to_extracted_attachment(tmp_path: Path) -> None:
    document = EmailDocument(
        source_path=Path("cid.eml"),
        source_format="eml",
        raw_headers=[],
        subject="CID",
        sender="sender@example.com",
        body_html='<p>Logo</p><img src="cid:logo@example">',
        attachments=[
            Attachment(
                "logo.png",
                "image/png",
                b"png",
                content_id="<logo@example>",
                disposition="inline",
            )
        ],
    )

    markdown = render_document(document, tmp_path).read_text(encoding="utf-8")

    assert "attachments/logo.png" in markdown
    assert markdown.count("cid:logo@example") == 1
    assert "## Original HTML" in markdown


def test_untrusted_markdown_and_header_fences_remain_literal(tmp_path: Path) -> None:
    document = EmailDocument(
        source_path=Path("literal.eml"),
        source_format="eml",
        raw_headers=[("X-Test", "```\n# forged section")],
        subject="# forged heading\nsecond line",
        sender="sender@example.com",
        body_text="# not a generated heading",
    )

    markdown = render_document(document, tmp_path).read_text(encoding="utf-8")

    assert r"# \# forged heading second line" in markdown
    assert "```text\n# not a generated heading\n```" in markdown
    assert "````text\nX-Test: ```\n# forged section\n````" in markdown


def test_existing_symlinked_output_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "output"
    output.symlink_to(outside, target_is_directory=True)
    document = EmailDocument(
        source_path=Path("unsafe.eml"),
        source_format="eml",
        raw_headers=[],
        subject="Unsafe",
        sender="sender@example.com",
    )

    with pytest.raises(RuntimeError, match="symlinked output directory"):
        render_document(document, output)
