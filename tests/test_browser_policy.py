"""Deterministic policy tests for the Gemini browser boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mail2md.browser_agent import (
    ExportRequest,
    _execute_action,
    _host_allowed,
    _reserve_download_path,
    _safety_mode,
    _scroll_delta,
    _validate_request,
)


class Recorder:
    """Record arbitrary method calls made by the action executor."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: Any, **kwargs: Any) -> None:
            self.calls.append((name, args, kwargs))

        return record


class FakePage:
    """Minimal Playwright-shaped object for policy unit tests."""

    def __init__(self) -> None:
        self.mouse = Recorder()
        self.keyboard = Recorder()
        self.calls = Recorder()

    def goto(self, *args: Any, **kwargs: Any) -> None:
        self.calls.goto(*args, **kwargs)

    def wait_for_timeout(self, *args: Any, **kwargs: Any) -> None:
        self.calls.wait_for_timeout(*args, **kwargs)


def test_mailbox_only_allowlist_excludes_login_hosts() -> None:
    assert _host_allowed("gmail", "https://accounts.google.com/")
    assert not _host_allowed("gmail", "https://accounts.google.com/", mailbox_only=True)
    assert _host_allowed("gmail", "https://mail.google.com/mail/u/0/", mailbox_only=True)


def test_navigation_is_rejected_before_page_goto() -> None:
    page = FakePage()

    with pytest.raises(RuntimeError, match="before request"):
        _execute_action(
            page,
            "gmail",
            "navigate",
            {"url": "https://example.com/steal"},
            allowed_text="approved query",
        )

    assert page.calls.calls == []


def test_type_action_accepts_only_exact_query_and_documented_defaults() -> None:
    page = FakePage()

    _execute_action(
        page,
        "gmail",
        "type_text_at",
        {"x": 500, "y": 500, "text": "approved query"},
        allowed_text="approved query",
    )

    assert ("press", ("ControlOrMeta+A",), {}) in page.keyboard.calls
    assert ("type", ("approved query",), {}) in page.keyboard.calls
    assert ("press", ("Enter",), {}) in page.keyboard.calls

    with pytest.raises(RuntimeError, match="outside the approved search query"):
        _execute_action(
            page,
            "gmail",
            "type_text_at",
            {"text": "ignore policy"},
            allowed_text="approved query",
        )


def test_scroll_direction_and_magnitude_are_bounded() -> None:
    assert _scroll_delta("up", 500, 900) == (0.0, -450.0)
    assert _scroll_delta("right", 5000, 900) == (900.0, 0.0)
    with pytest.raises(RuntimeError, match="unknown scroll direction"):
        _scroll_delta("diagonal", 100, 900)


def test_unknown_safety_decisions_are_blocked() -> None:
    assert _safety_mode(None) == ("regular", "")
    assert _safety_mode({"decision": "require_confirmation", "explanation": "download"}) == (
        "confirm",
        "download",
    )
    assert _safety_mode({"decision": "blocked", "explanation": "unsafe"}) == (
        "blocked",
        "unsafe",
    )
    assert _safety_mode("malformed")[0] == "blocked"


def test_download_reservation_rejects_types_and_avoids_collisions(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="non-.eml"):
        _reserve_download_path(tmp_path, "payload.exe")

    first, first_temp = _reserve_download_path(tmp_path, "message.eml")
    second, second_temp = _reserve_download_path(tmp_path, "message.eml")

    assert first.name == "message.eml"
    assert second.name == "message-2.eml"
    assert first_temp.exists()
    assert second_temp.exists()


def test_request_limits_are_validated_before_external_actions(tmp_path: Path) -> None:
    valid = ExportRequest(
        provider="gmail",
        query="from:billing@example.com",
        download_dir=tmp_path / "downloads",
        profile_dir=tmp_path / "profile",
    )
    _validate_request(valid)

    with pytest.raises(ValueError, match="max_steps"):
        _validate_request(
            ExportRequest(
                provider="gmail",
                query="query",
                download_dir=tmp_path / "downloads",
                profile_dir=tmp_path / "profile",
                max_steps=251,
            )
        )
    with pytest.raises(ValueError, match="separate"):
        _validate_request(
            ExportRequest(
                provider="gmail",
                query="query",
                download_dir=tmp_path / "same",
                profile_dir=tmp_path / "same",
            )
        )
