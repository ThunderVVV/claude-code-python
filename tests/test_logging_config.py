from __future__ import annotations

import logging

from claude_code.utils.logging_config import _SourceTagFilter


def test_source_tag_filter_maps_modules_to_expected_tags():
    filter_ = _SourceTagFilter("TUI")

    cases = [
        ("claude_code.api.server", "FASTAPI"),
        ("claude_code.core.query_engine", "ENGINE"),
        ("claude_code.services.openai_client", "ENGINE"),
        ("claude_code.client.http_client", "CLIENT"),
        ("claude_code.ui.screens", "TUI"),
        ("claude_code.cli", "TUI"),
        ("claude_code.unknown.module", "TUI"),
    ]

    for logger_name, expected_tag in cases:
        record = logging.LogRecord(
            name=logger_name,
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="message",
            args=(),
            exc_info=None,
        )

        assert filter_.filter(record) is True
        assert record.source_tag == expected_tag
