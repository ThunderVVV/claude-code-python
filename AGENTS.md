# Important Notes for Developers

## TUI Development

### Layout Debugging

If a Textual transcript area appears blank while scrollbars still move, inspect **layout and widget sizing** before assuming a color or markup bug.

- Use `VerticalGroup` for dynamic content that should fit its content
- Use `Container`/`Vertical` only when you need expanding behavior
- Avoid mounting empty streaming placeholders (creates false blank rows)

### Tool-Only Response Path

The TUI must handle the case where the assistant emits tool calls **without preceding text**:

1. User submits prompt
2. Assistant emits `ToolUseEvent`
3. Assistant emits `ToolResultEvent`
4. No preceding normal assistant text

This path previously appeared as a black screen. Tests must cover this explicitly.

### Dynamic Text Rendering

Always use `markup=False` when rendering dynamic content (tool output, user input) to prevent markup injection issues.

## Prompt Alignment

All prompts (tool descriptions, system prompts) must match the TypeScript version exactly. See `CHANGELOG.md` for alignment details.
