# Project Notes For Agents

## Source Of Truth

- This repository is a Python port of the official TypeScript Claude Code project.
- When behavior is ambiguous, align with the TypeScript implementation before adding Python-specific logic.
- Tool descriptions, system prompts, and prompt-building helpers must stay exactly aligned with the TypeScript version.

## Repository Hygiene

- Keep the project root limited to product files and top-level docs.
- Reusable developer utilities belong in `scripts/debug/`.
- Screenshots, archived notes, and long-form references belong in `docs/`.
- Runtime logs belong in `.logs/`.
- Do not add new root-level `debug*.py`, `diagnose*.py`, `*.log`, or ad hoc `test_*.py` files.

## TUI Development

### Layout Debugging

If the transcript area looks blank while scrollbars still move, inspect layout and widget sizing before assuming a color or markup issue.

- Use `VerticalGroup` for dynamic content that should fit its content.
- Use `Container` or `Vertical` only when expanding behavior is intentional.
- Avoid mounting empty streaming placeholders because they create false blank rows.
- Keep spacing ownership simple: assistant text owns the gap before the first tool block, and each tool block owns its own trailing spacing.

### Tool-Only Response Path

The TUI must handle the case where the assistant emits tool calls without preceding text:

1. User submits a prompt.
2. Assistant emits `ToolUseEvent`.
3. Assistant emits `ToolResultEvent`.
4. No normal assistant text is emitted first.

This path previously rendered as a black screen. Tests must cover tool-only and tool-first sequences explicitly.

### Tool Block Structure

- Each tool call should render as a single collapsible block.
- Before the result arrives, the collapsible title shows the tool invocation summary.
- After the result arrives, update that same title in place to the compact result summary instead of adding a second summary row.
- Tool parameters and `Output:` content live inside the same collapsible body; do not add a second nested "Output Preview" collapsible for normal tool rendering.
- Compact tool summaries should not end with a trailing colon.

### Dynamic Text Rendering

- Always use `markup=False` when rendering dynamic content such as tool output or user input.
- Sanitize ANSI and control characters before rendering assistant or tool output.
- Summarize large tool results instead of dumping unbounded raw output into the transcript.

### Transcript Behavior

- Auto-follow should stay active only while the user is effectively pinned near the bottom.
- Changes to streaming, scrolling, or collapsible tool blocks should be verified with headless Textual tests.
- Prefer a single assistant widget that can start with text or with tool blocks; do not assume text arrives first.

## Testing

- Keep automated tests under `tests/` only.
- Prefer headless `Textual` tests for TUI regressions instead of one-off manual scripts.
- When touching `claude_code/ui/`, cover tool-only responses, mixed text/tool sequences, copy behavior, and input disable/reset state.

## Debugging Utilities

- `scripts/debug/diagnose_api.py` checks DNS, TCP, HTTP, and chat completion connectivity against the current `.env`.
- `scripts/debug/debug_query.py` traces a single query loop and prints the emitted events.
- `scripts/debug/debug_tui.py` launches the TUI with safe fallback credentials for layout debugging.

## Documentation

- Keep `README.md` paths and examples aligned with the actual repository layout.
- If you move debugging tools, logs, or workflow files, update both `README.md` and this file in the same change.
- Historical implementation details stay in `CHANGELOG.md`; stable developer rules belong here.
