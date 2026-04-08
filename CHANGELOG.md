# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed - 2026-04-09

#### Tool Error Status In Transcript
- Fixed `ToolResultEvent.is_error` propagation so tool-specific failures no longer render with a success indicator in the TUI or CLI
- Added per-tool error classification for `Bash`, `Read`, `Write`, `Edit`, `Glob`, and `Grep`
- `Bash` tool now treats non-zero exit codes and timeouts as errors for transcript rendering, even when the shell command returns structured stdout/stderr text
- TUI tool titles now use colored status dots (`●`) instead of textual `[OK]` / `[ERR]` prefixes, while keeping the summary text in the normal foreground color
- Failed tool titles now use action-oriented summaries such as `Failed to run ...` / `Failed to read ...` instead of showing a raw error code or error line as the title
- Added regression coverage for tool error classification in both `QueryEngine` and the TUI

### Changed - 2026-04-09

#### Default TUI Mode and Logging Behavior
- Changed default mode from CLI to TUI when running `claude-code` without flags
- Added `--cli` flag to explicitly use simple CLI mode
- Kept `--tui` flag for compatibility (optional, same as default behavior)
- Disabled automatic debug logging for TUI mode - now only enabled with explicit `--debug` flag
- Updated `resolve_log_path()` to only create log files when `--debug` is set
- Updated CLI help text to reflect new default behavior
- Updated README documentation in both Chinese and English versions

### Added - 2026-04-09

#### TUI Context And Diff Presentation
- Added a context usage line beneath the TUI input showing used tokens / configured max context / percentage
- Added `claude_code/ui/diff_view.py`, adapted from Toad, for inline file diff rendering in the TUI
- `Edit` and `Write` tool results now render inline diffs instead of raw replacement/content payload previews
- Added headless TUI regression coverage for context usage, diff rendering, auto-expand behavior, and markdown fence spacing

#### Reasoning/Thinking Content Support
- Added support for displaying model reasoning/thinking content (chain-of-thought)
- Added `ThinkingContent` dataclass for reasoning content blocks
- Added `ThinkingEvent` for streaming thinking content during responses
- Updated `OpenAIClient.parse_stream_chunk()` to extract `reasoning_content` field (for models like DeepSeek)
- Updated `OpenAIClient.parse_non_stream_response()` to handle thinking content in non-streaming responses
- Added `ThinkingBlockWidget` with collapsible UI for thinking display
- Added CSS styles for thinking blocks (gray italic text, left border)
- Thinking content appears before text/tool output in the transcript
- Thinking block is collapsed by default to keep transcript clean
- Added test `test_query_engine_streams_thinking_before_text` for thinking event flow

### Changed - 2026-04-08

#### TUI Tool Result Summaries
- Tool result titles now collapse file paths to basenames while keeping full paths in the expanded details
- `Write` tool blocks now auto-expand on success, matching `Edit`
- `Glob` and `Grep` result summaries now use tool-specific wording; `Grep` summaries preserve the search pattern when available

#### Bash Tool Parameter Description Enhancement
- Updated `description` parameter description in BashTool to align with TypeScript version
- Added detailed guidance for writing command descriptions:
  - Simple commands: brief descriptions (5-10 words)
  - Complex commands: add context for clarity
  - Examples provided for both cases
- Description length increased from ~50 to ~730 characters
- No functional changes - only parameter documentation improvement

### Removed - 2026-04-08

#### Duplicate Tool Definitions Cleanup
- Removed `claude_code/tools/file_tools.py` (650 lines) - contained duplicate tool definitions
- All tools are already defined in separate files: `read_tool.py`, `write_tool.py`, `edit_tool.py`, `glob_tool.py`, `grep_tool.py`
- Updated imports in `cli.py`, `test_core.py`, and debug scripts to use `from claude_code.tools import ...` instead of `from claude_code.tools.file_tools import ...`
- No functional changes - purely code cleanup to eliminate redundancy

### Changed - 2026-04-08

#### OpenAI Client SDK Migration
- Replaced custom httpx-based HTTP client with official OpenAI Python SDK (`openai>=1.30.0`)
- Migrated from manual POST request construction to SDK's `AsyncOpenAI.chat.completions.create()`
- Removed manual SSE parsing, HTTP/2 configuration, connection pool management, and custom retry logic
- SDK now handles automatic retries, streaming, and error handling internally
- API remains backward compatible - no changes required in calling code
- Fixed import path for `create_default_system_prompt` and `build_context_message` in `services/__init__.py`

### Changed - 2026-04-08

#### Query Limits
- Raised the default `max_turns` limit from `20` to `1000000` across CLI and query state defaults.
- Updated the CLI `--max-turns` help text to match the new default.

### Refactored - 2026-04-08

#### TUI Module Split
- Split 1349-line `claude_code/ui/app.py` into multiple modules for better maintainability:
  - `claude_code/ui/constants.py` - Theme colors (CLAUDE_ORANGE, etc.)
  - `claude_code/ui/styles.py` - TUI CSS definitions
  - `claude_code/ui/utils.py` - Text sanitization and tool summarization functions
  - `claude_code/ui/widgets.py` - Clawd and WelcomeWidget
  - `claude_code/ui/message_widgets.py` - MessageList, MessageWidget, AssistantMessageWidget, ToolUseWidget, StreamingTextWidget
  - `claude_code/ui/screens.py` - REPLScreen
  - `claude_code/ui/app.py` - ClaudeCodeApp (simplified main app)
- Added proper `__init__.py` exports for backwards compatibility
- **No functional changes** - purely structural refactoring

### Fixed - 2026-04-08

#### TUI Input And Clipboard
- Replaced the single-line `Input` prompt with a dedicated `InputTextArea`.
- Added Enter-to-submit and Shift+Enter newline handling in the prompt widget.
- Added persistent in-session prompt history navigation on Up/Down, with history saved to `~/.claude_code_history.json`.
- Reset the prompt document cleanly after submit so follow-up prompts do not inherit stray newlines.
- Collapse the prompt to a stable single-line height while a turn is processing, then restore automatic height afterward.
- Added app-level copy bindings for `Ctrl+C`, `Ctrl+Shift+C`, and `Cmd+C` when the terminal forwards it.
- Route copy through Textual clipboard handling and show a native toast: `Copied to clipboard`.
- Updated the prompt placeholder to document the in-app copy shortcut.

#### TUI Tool Blocks
- Collapsed tool invocation and tool result rendering into a single `Collapsible` per tool call.
- Updated tool result handling to replace the existing tool title in place instead of adding a second summary row.
- Merged tool parameters and `Output:` content into the same expanded body and removed the extra "Output Preview" collapsible from the normal path.
- Reused `ToolUseWidget` for fallback tool-result rendering and removed the separate `ToolResultWidget` path.
- Normalized compact tool summaries so titles do not end with a trailing colon.

#### Tool Descriptions (aligned with TypeScript version)

- **Read tool**: Updated description to match TypeScript `FileReadTool/prompt.ts`
  - Added complete usage instructions
  - Added file path requirements (must be absolute)
  - Added line number format specification
  - Added screenshot handling instructions

- **Write tool**: Updated description to match TypeScript `FileWriteTool/prompt.ts`
  - Added pre-read requirement for existing files
  - Added preference for Edit tool over Write for modifications
  - Added documentation file creation restrictions

- **Edit tool**: Updated description to match TypeScript `FileEditTool/prompt.ts`
  - Added pre-read requirement
  - Added indentation preservation instructions
  - Added uniqueness requirements for `old_string`
  - Added `replace_all` usage guidance

- **Glob tool**: Updated description to match TypeScript `GlobTool/prompt.ts`
  - Added glob pattern examples
  - Added modification time sorting info
  - Added Agent tool recommendation for complex searches

- **Grep tool**: Updated description to match TypeScript `GrepTool/prompt.ts`
  - Added ripgrep usage instructions
  - Added regex syntax support
  - Added output mode descriptions
  - Added multiline matching instructions

- **Bash tool**: Updated description to match TypeScript `BashTool/prompt.ts`
  - Added tool preference guidance (use Read/Write/Edit/Glob/Grep instead of shell commands)
  - Added working directory persistence info
  - Added timeout specifications
  - Added background execution instructions
  - Added multi-command handling (parallel vs sequential)
  - Added git command guidelines

#### System Prompt (aligned with TypeScript version)

- Created new `claude_code/core/prompts.py` module with complete system prompt sections:
  - `get_simple_intro_section()` - Introduction with security guidelines
  - `get_simple_system_section()` - System behavior description
  - `get_simple_doing_tasks_section()` - Task execution guidelines
  - `get_actions_section()` - Action execution with care
  - `get_using_your_tools_section()` - Tool usage preferences
  - `get_simple_tone_and_style_section()` - Communication style
  - `get_output_efficiency_section()` - Output efficiency guidelines
  - `compute_env_info()` - Environment information

- Updated `QueryEngine` to use new system prompt module
- Updated imports in `openai_client.py` to use new prompts module

### Added

- `claude_code/core/prompts.py` - New module containing all system prompt definitions
- `.gitignore` - Standard Python gitignore (excluding `__pycache__/`, `.env`, etc.)
- `CHANGELOG.md` - This file

### Tests - 2026-04-08

#### Test Suite Cleanup
- Consolidated TUI regression coverage into `tests/test_tui.py`.
- Removed redundant root-level `test_*.py` scripts that duplicated TUI checks.
- Renamed the manual TUI launcher from `test_tui.py` to `debug_tui.py` to avoid pytest collection conflicts.
- Added pytest `testpaths = ["tests"]` so the automated suite only collects the formal test directory.
- Expanded TUI regression coverage for clipboard notifications, input collapse/reset behavior, cursor-line styling, and prompt history navigation.

## [0.1.0] - Initial Release

### Added

- Core message types and data models (`claude_code/core/messages.py`)
- Tool system base classes (`claude_code/core/tools.py`)
- Query engine with streaming support (`claude_code/core/query_engine.py`)
- OpenAI-compatible API client (`claude_code/services/openai_client.py`)
- File tools: Read, Write, Edit, Glob, Grep (`claude_code/tools/file_tools.py`)
- Bash tool with sandbox support (`claude_code/tools/bash_tool.py`)
- CLI interface with Click (`claude_code/cli.py`)
- TUI interface with Textual (`claude_code/ui/app.py`)
- Configuration via environment variables and `.env` files
- Basic test suite (`tests/`)

---

## Development History

### TUI Tool Output Incident - 2026-04-08

**Symptom**: In `claude-code --tui`, tool calls were producing output (scrollbar moving), but the transcript area appeared as a black/blank block.

**Root Cause**: Textual's expanding containers (`Container`/`Vertical`) default to consuming remaining space (`height: 1fr`), while `VerticalGroup` fits to content height. The TUI was using expanding containers in the dynamic message path, creating a layout bug where:
1. Empty streaming area expanded and consumed vertical space
2. Message list height calculation became incorrect
3. Tool result widgets were mounted below the visible viewport
4. Scroll container showed movement but content was hidden

**Fix**: Switched dynamic transcript widgets from expanding containers to content-fitting containers:
- Use `VerticalGroup` for `ToolUseWidget`, `AssistantMessageWidget`, `ToolResultWidget`, `MessageList`
- Replace streaming wrapper `Container` with direct `Static`

**Retained Safeguards** (not the root cause but still valuable):
- Sanitize ANSI/control characters before rendering tool output
- Render dynamic text with `markup=False`
- Summarize large tool results instead of dumping raw blocks

### TUI Iteration Summary - 2026-04-08

**Functional Changes**:
- Removed `Send` button, standardized on Enter-to-submit
- Moved prompt handling to background worker for responsive UI
- Enabled live assistant streaming
- Added auto-follow transcript (only active when user near bottom)
- Added visible in-progress state with loading indicator

**Tool Rendering Changes**:
- Fixed tool-only/tool-first transcript path (previously black screen)
- Merged tool calls and results into single tool block
- Kept a single `Collapsible` per tool block and rendered parameters plus `Output:` in the same expanded body
- Kept ANSI sanitization and compact summaries

**Visual Changes**:
- Repaired welcome layout, reduced panel height
- Removed footer shortcuts and extra labels
- Removed decorative left borders
- Changed user message background to muted gray
- Aligned all elements to same left edge
- Normalized message spacing

**Layout Lesson**: Irregular spacing in mixed assistant-text + tool sequences was caused by both outer wrapper and inner streaming text contributing vertical separation. Stable pattern:
- Keep outer assistant wrapper visually neutral
- Let assistant text own gap before first tool block
- Let each tool block own its bottom spacing
- Avoid mounting empty streaming placeholders
