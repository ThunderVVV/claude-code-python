# AGENTS Notes

## TUI Tool Output Incident

Date: 2026-04-08

### Symptom

In `claude-code --tui`, tool calls were clearly producing output because the right scrollbar kept moving, but the transcript area looked like a black / blank block and no tool result text was visible.

### Why Earlier Fixes Did Not Solve It

The earlier fixes mostly targeted rendering safety:

- stripping ANSI and control sequences
- forcing `markup=False`
- changing tool result colors
- replacing raw tool dumps with compact summaries

Those changes were reasonable hardening, but they did not address the real failure mode. The issue was not primarily color or terminal escape corruption. It was layout.

### Real Root Cause

Textual's expanding containers such as `Container` / `Vertical` default to consuming remaining space (`height: 1fr`), while `VerticalGroup` fits to content height.

The TUI was using expanding containers in the dynamic message path:

- assistant message widgets
- tool use widgets
- tool result widgets
- the message list itself
- the streaming text wrapper

That created a bad interaction when the model emitted a tool call before normal assistant text:

1. an empty or near-empty streaming area still expanded and consumed vertical space
2. the message list height calculation became wrong
3. tool result widgets were mounted below the visible viewport
4. the scroll container showed movement, but its effective visible range did not expose the hidden tool content

This looked like a color problem, but was actually a content-sizing and scroll-range bug.

### What Finally Fixed It

The durable fix was to switch the dynamic transcript widgets from expanding containers to content-fitting containers:

- use `VerticalGroup` for `ToolUseWidget`
- use `VerticalGroup` for `AssistantMessageWidget`
- use `VerticalGroup` for `ToolResultWidget`
- use `VerticalGroup` for `MessageList`
- replace the streaming wrapper `Container` with a direct `Static`

This made the transcript grow by actual rendered content, so:

- tool results became visible
- scroll height matched real content height
- auto-scroll landed on the latest output correctly

### Keep These Safeguards

These are still worth keeping even though they were not the root cause:

- sanitize ANSI / control characters before rendering tool output
- render dynamic text with `markup=False`
- summarize large tool results instead of dumping huge raw blocks

### Regression Coverage

The TUI test suite must continue to cover the tool-only path:

- user submits a prompt
- assistant emits `ToolUseEvent`
- assistant emits `ToolResultEvent`
- no preceding normal assistant text is required
- screenshot / rendered transcript must contain the tool summary and preview lines

This exact path is the one that previously appeared as a black screen.

### Rule Of Thumb For Future TUI Work

If a Textual transcript area appears blank while scrollbars still move, inspect layout and widget sizing before assuming a color or markup bug.

## TUI Iteration Summary

Date: 2026-04-08

### Scope

This iteration turned the Python TUI from a blocked / partially broken prototype into a usable agent-style transcript UI with streaming, merged tool output, and tighter message layout.

### Functional Changes

- removed the `Send` button and standardized on Enter-to-submit
- moved prompt handling to a background worker so the input clears immediately and the UI does not freeze while waiting for the model
- enabled live assistant streaming instead of waiting for the full reply before repainting
- added transcript auto-follow that only stays active while the user is already near the bottom
- stopped forced snap-back when the user manually scrolls upward during generation
- added a visible in-progress state in the input area with a loading indicator and status text

### Tool Rendering Changes

- fixed the tool-only / tool-first transcript path that previously appeared as a black or blank area
- merged tool calls and tool results into a single tool block instead of rendering them as separate message blocks
- added `Collapsible` sections for tool input details and output preview
- kept ANSI / control-character sanitization and `markup=False` rendering on dynamic tool text
- kept compact tool-result summaries instead of dumping raw output inline

### Visual Changes

- repaired the welcome layout and reduced the welcome panel height
- removed the footer shortcut hints and the extra `Claude` / `You` labels from transcript messages
- removed decorative left borders from user / assistant / tool blocks
- changed the user message background from green to a muted gray tone
- aligned user messages, assistant messages, tool blocks, and the input area to the same left edge
- tightened message spacing and then normalized it so the gap between assistant text and the first tool block matches the gap between later tool blocks

### Important Layout Lesson

Irregular spacing was not just a CSS margin issue. In mixed assistant-text + tool sequences, spacing became inconsistent when the assistant wrapper and the inner streaming text both contributed vertical separation.

The stable pattern is:

- keep the outer assistant wrapper visually neutral
- let assistant text own the gap before the first tool block
- let each tool block own its own bottom spacing
- avoid mounting empty streaming placeholders, because they create false blank rows in tool-only turns

### Regression Coverage Added

The TUI tests now explicitly cover:

- submit clears input immediately and hides the welcome panel
- tool-only responses render visible tool summaries and previews
- multi-tool sequences do not duplicate tool blocks
- manual upward scrolling during streaming is respected
- control sequences are stripped from tool output
- follow-up tool-only turns keep the same spacing rhythm as earlier tool blocks
