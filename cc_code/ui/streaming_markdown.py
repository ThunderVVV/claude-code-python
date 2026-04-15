"""Streaming markdown widget for TUI applications"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from textual.await_complete import AwaitComplete
from textual.content import Content
from textual.highlight import highlight as highlight_code

from cc_code.ui.utils import sanitize_terminal_text
from cc_code.ui.patched_markdown import MarkdownFence, MarkdownStream, Markdown


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
    _TABLE_SEPARATOR_RE = re.compile(r"^\|?[\s:|\-]+\|?$")

    def __init__(
        self,
        initial_text: str = "",
        **kwargs,
    ):
        normalized = sanitize_terminal_text(initial_text)
        self._markdown_text = normalized
        self._rendered_markdown_text = normalized
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
        self._rendered_markdown_text = normalized
        update = super().update(normalized)
        return update

    @classmethod
    def _is_table_separator_line(cls, line: str) -> bool:
        """Return True if the line looks like a GFM table separator."""
        stripped = line.strip()
        if "|" not in stripped or "-" not in stripped:
            return False
        if not cls._TABLE_SEPARATOR_RE.match(stripped):
            return False
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            return False
        return all(cell and set(cell) <= {":", "-"} for cell in cells)

    @staticmethod
    def _is_table_header_candidate_line(line: str) -> bool:
        """Return True for a line that looks like a pipe table header row."""
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return False
        return stripped.count("|") >= 2

    @classmethod
    def _has_unterminated_trailing_table(cls, markdown: str) -> bool:
        """Detect whether the last non-empty block is an unfinished table."""
        lines = markdown.splitlines()
        if not lines:
            return False

        last_non_empty = len(lines) - 1
        while last_non_empty >= 0 and not lines[last_non_empty].strip():
            last_non_empty -= 1
        if last_non_empty < 0:
            return False

        block_start = last_non_empty
        while block_start > 0 and lines[block_start - 1].strip():
            block_start -= 1

        trailing_block = lines[block_start : last_non_empty + 1]
        header_line = trailing_block[0]
        if not cls._is_table_header_candidate_line(header_line):
            return False

        # A lone header row may still become a table on the next chunk.
        if len(trailing_block) == 1:
            return True

        separator_line = trailing_block[1]
        if cls._is_table_separator_line(separator_line):
            return True

        return False

    async def _flush_pending_markdown(self, force: bool = False) -> None:
        """Flush any buffered markdown content to the widget."""
        if self._rendered_markdown_text == self._markdown_text:
            return
        pending = self._markdown_text
        rendered = self._rendered_markdown_text
        if not force and self._has_unterminated_trailing_table(pending):
            return
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
        await self._flush_pending_markdown(force=True)
        if self._stream is None:
            return
        stream = self._stream
        self._stream = None
        await stream.stop()

    async def flush_pending_markdown(self) -> None:
        """Render any buffered markdown without stopping future streaming."""
        await self._flush_pending_markdown(force=True)

    async def append_text(self, markdown: str) -> None:
        """Append a markdown fragment using Textual's streaming helper."""
        normalized = sanitize_terminal_text(markdown)
        if not normalized:
            return
        self._markdown_text += normalized
        if not self.is_mounted:
            self._initial_markdown = self._markdown_text
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
