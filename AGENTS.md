# Project Notes For Agents

## Source Of Truth

- This repository is a Python port of the official TypeScript Claude Code project.
- When behavior is ambiguous, align with the TypeScript implementation before adding Python-specific logic.
- Tool descriptions, system prompts, and prompt-building helpers must stay exactly aligned with the TypeScript version.

## Architecture

This project uses a frontend-backend separation architecture with gRPC communication.

**Frontend (TUI Client):**
- `REPLScreen` - Textual TUI interface
- `ClaudeCodeClient` - gRPC client

**Backend (gRPC Server):**
- `ChatServiceServicer` + `SessionServiceServicer` - gRPC server
- `QueryEngine` - Core query engine
- `OpenAIClient` - OpenAI-compatible API client

**Communication Flow:**
```
REPLScreen -> ClaudeCodeClient --gRPC--> ChatServiceServicer -> QueryEngine -> OpenAIClient
```

**Key Directories:**
- `claude_code/ui/` - Frontend TUI (Textual)
- `claude_code/client/` - gRPC client
- `claude_code/server/` - gRPC server
- `claude_code/core/` - Core logic (QueryEngine, tools, messages)
- `claude_code/services/` - OpenAI client
- `claude_code/proto/` - gRPC protocol definitions

## Repository Hygiene

- Keep the project root limited to product files and top-level docs.
- Reusable developer utilities belong in `scripts/`.
- Screenshots and assets belong in `docs/assets/`.
- Runtime logs belong in `.logs/`.
- Do not add new root-level `debug*.py`, `diagnose*.py`, `*.log`, or ad hoc `test_*.py` files.

## TUI Development

### TUI Logging

**IMPORTANT:** All TUI debug logs must use `tui_log()` function from `claude_code.utils.logging_config`, not `print()` or standard `logging`.

```python
from claude_code.utils.logging_config import tui_log

tui_log(f"Debug message: {variable}")
```

Regular `print()` statements are not captured in TUI log files, making debugging impossible when issues occur in the Textual event loop.

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

### Custom Line API Widgets

- If a TUI widget uses Textual's `ScrollView` / Line API instead of `Static`, preserve text selection behavior explicitly.
- Line API widgets that should support copy/selection must keep Textual offset metadata by returning strips with `Strip.apply_offsets(...)`.
- Custom virtualized text widgets must implement `get_selection()` and `selection_updated()` if they bypass the default `Static` / `Content` rendering path.
- When replacing an official Textual widget with a custom renderer, verify mouse drag selection and clipboard copy in addition to visual rendering and scroll behavior.
- For markdown code fences, prefer plain-text rendering when no language is specified; untyped blocks should not be sent through syntax highlighting if that can introduce false error highlighting for unusual characters.

### Transcript Behavior

- Auto-follow should stay active only while the user is effectively pinned near the bottom.
- For transcript-style views backed by a parent `ScrollableContainer`, prefer Textual's `anchor()` on the scroll container over a custom follow-state machine in child widgets.
- Re-enable transcript auto-follow by re-anchoring the scroll container when a new user turn begins; do not force-scroll on every streamed update once the user has scrolled away.
- After rebuilding transcript content from persisted history, session restore, or rewind, re-anchor after refresh so the restored view opens at the latest message.
- If streaming markdown causes flicker in older visible content, prefer buffering markdown updates while the user is scrolled away from the bottom and flush them on stream completion instead of trying to micro-optimize partial repaints in the renderer.
- Changes to streaming, scrolling, or collapsible tool blocks should be verified with headless Textual tests.
- Prefer a single assistant widget that can start with text or with tool blocks; do not assume text arrives first.

## Documentation

- Keep `README.md` paths and examples aligned with the actual repository layout.
- If you move debugging tools, logs, or workflow files, update both `README.md` and this file in the same change.
- Historical implementation details stay in `CHANGELOG.md`; stable developer rules belong here.
