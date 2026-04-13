"""Streaming markdown widget for TUI applications"""

from __future__ import annotations

from typing import Callable

from markdown_it import MarkdownIt
from textual.await_complete import AwaitComplete
from textual.content import Content
from textual.highlight import highlight as highlight_code

from claude_code.ui.utils import sanitize_terminal_text
from claude_code.ui.patched_markdown import MarkdownFence, MarkdownStream, Markdown, MarkdownBlock


def _create_markdown_parser() -> MarkdownIt:
    """Build a Markdown parser aligned with the TypeScript implementation."""
    return MarkdownIt("gfm-like", {"linkify": False}).disable("strikethrough")


class TranscriptMarkdownFence(MarkdownFence):
    """Markdown fence that treats untyped code blocks as plain text."""

    @classmethod
    def highlight(cls, code: str, language: str) -> Content:
        return highlight_code(code, language=language or "text")


class StreamingMarkdownWidget(Markdown):
    """Markdown widget for streaming markdown content with terminal sanitization."""

    FOCUS_ON_CLICK = False

    def __init__(
        self,
        initial_text: str = "",
        *,
        should_stream_live: Callable[[], bool] | None = None,
        **kwargs,
    ):
        normalized = sanitize_terminal_text(initial_text)
        self._markdown_text = normalized
        self._rendered_markdown_text = normalized
        self._stream: MarkdownStream | None = None
        self._should_stream_live_callback = should_stream_live
        super().__init__(
            normalized,
            parser_factory=_create_markdown_parser,
            open_links=False,
            **kwargs,
        )

    def update(self, markdown: str) -> AwaitComplete:
        """Update markdown content with terminal sanitization."""
        normalized = sanitize_terminal_text(markdown)
        self._markdown_text = normalized
        self._rendered_markdown_text = normalized
        update = super().update(normalized)
        return update

    def _should_stream_live(self) -> bool:
        """Return True when transcript output should update live."""
        if not self.is_mounted:
            return False
        if self._should_stream_live_callback is not None:
            return self._should_stream_live_callback()
        return True

    async def _flush_pending_markdown(self) -> None:
        """Flush any buffered markdown content to the widget."""
        if self._rendered_markdown_text == self._markdown_text:
            return
        pending = self._markdown_text
        rendered = self._rendered_markdown_text
        if pending.startswith(rendered):
            delta = pending[len(rendered) :]
            if delta:
                await self._get_stream().write(delta)
        else:
            await self.update(pending)
        self._rendered_markdown_text = pending

    def _get_stream(self) -> MarkdownStream:
        """Lazily create a Textual markdown stream for high-frequency appends."""
        if self._stream is None:
            self._stream = Markdown.get_stream(self)
        return self._stream

    async def finish_streaming(self) -> None:
        """Stop the background markdown stream, flushing any queued fragments."""
        await self._flush_pending_markdown()
        if self._stream is None:
            return
        stream = self._stream
        self._stream = None
        await stream.stop()

    async def append_text(self, markdown: str) -> None:
        """Append a markdown fragment using Textual's streaming helper."""
        normalized = sanitize_terminal_text(markdown)
        if not normalized:
            return
        self._markdown_text += normalized
        if not self.is_mounted:
            self._initial_markdown = self._markdown_text
            return
        if not self._should_stream_live():
            return
        await self._flush_pending_markdown()

    async def set_markdown_text(self, text: str) -> None:
        """Reconcile the widget with the provided full markdown text."""
        normalized = sanitize_terminal_text(text)
        previous = self._markdown_text

        if normalized == previous:
            return

        if not self.is_mounted:
            self._markdown_text = normalized
            self._initial_markdown = normalized
            return

        if normalized.startswith(previous):
            await self.append_text(normalized[len(previous) :])
            return

        await self.finish_streaming()
        await self.update(normalized)
        self._rendered_markdown_text = normalized

    async def _on_unmount(self) -> None:
        await self.finish_streaming()
