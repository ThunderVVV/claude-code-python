"""Streaming markdown widget for TUI applications"""

from __future__ import annotations

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

    def __init__(self, initial_text: str = "", **kwargs):
        normalized = sanitize_terminal_text(initial_text)
        self._markdown_text = normalized
        self._stream: MarkdownStream | None = None
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
        update = super().update(normalized)
        return update

    def _get_stream(self) -> MarkdownStream:
        """Lazily create a Textual markdown stream for high-frequency appends."""
        if self._stream is None:
            self._stream = Markdown.get_stream(self)
        return self._stream

    async def finish_streaming(self) -> None:
        """Stop the background markdown stream, flushing any queued fragments."""
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
        await self._get_stream().write(normalized)

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

    async def _on_unmount(self) -> None:
        await self.finish_streaming()
