# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Changed - 2026-04-11

#### Architecture Refactor: Pure gRPC Frontend/Backend Separation
- Removed standalone mode; project now uses pure gRPC frontend/backend architecture
- Client (`cc-py`) is now a pure gRPC client that auto-detects and starts server
- Server (`cc-server`) runs independently, managing all session state and tool execution
- Updated README.md to remove standalone mode docs, simplified running instructions

#### Client Simplification
- Removed `--grpc` flag (now the default and only mode)
- Removed `--api-url`, `--api-key`, `--model` and other local-mode parameters
- Client auto-detects server availability and starts it if not running
- Simplified command: `cc-py --host localhost --port 50051`

#### State Management Refactor
- Removed `EngineStateSnapshot` class and related snapshot/rollback mechanism
- Removed `ToolContext.register_undo_operation` and file rollback logic
- Server now handles all session state persistence uniformly
- Interrupt operations sent to server via gRPC

#### Removed Redundant Code
- Deleted `claude_code/client/grpc_engine.py` (no longer needed)
- Removed `RequestStartEvent` (simplified event flow)
- Removed `FrontendSnapshot` class and frontend state capture logic
- Removed `sync_from_message()` method

#### Added Utility Module
- Added `claude_code/utils/logging_config.py` for unified logging configuration
- Provides `setup_server_logging()`, `setup_client_logging()` and `log_exception()` functions

#### Proto Updates
- Removed `python_package` option (using dynamic imports)
- Added `Message.usage` field for token statistics transmission
- `proto/__init__.py` now uses dynamic path import

#### UI Refactor
- `ClaudeCodeApp` now receives `ClaudeCodeClient` instead of `QueryEngine`
- `REPLScreen` completely refactored as stateless frontend, all state managed via gRPC
- `SessionResumeModal` now uses `ClaudeCodeClient` to fetch session list
- Simplified interrupt handling: sends interrupt signal to server instead of local rollback

#### QueryEngine Improvements
- Added `create_from_session_id()` class method to create engine from session ID
- Added `_persist_session()` method to persist on session end
- Added `session_store` parameter for server-side persistence

### Changed - 2025-04-12

#### Code Cleanup
- Removed unused `ToolProtocol` class and `ToolInputSchema.additional_properties` field
- Removed redundant `QueryState.max_turns` field (duplicates `QueryConfig.max_turns`)
- Removed redundant `is_error_result()` implementations in tool classes (now inherit from `BaseTool`)
- Removed unused `Bash = BashTool()` global instance
- Fixed API URL normalization bug in CLI
- Reduced ~50 lines of redundant code

### Changed - 2025-04-11

#### Code Refactoring
- Removed unused `StreamEvent` subclasses and redundant tool helper functions
- Extracted `setup_logging()` function and pagination helpers to reduce code duplication
- Simplified environment variable handling and API URL normalization
- Reduced ~126 lines of redundant code

### Removed - 2025-04-11

#### CLI Mode Removal
- Removed CLI mode (`--cli` flag) - the project now exclusively uses TUI interface
- Removed `run_cli_mode()` function and related CLI-specific helper functions (`print_tool_use_header`, `print_tool_result`)
- Removed `--cli` and `--tui` command-line options (TUI is now the only mode)
- Updated documentation to reflect TUI-only interface
- Simplified entry point logic - no longer needs to choose between CLI and TUI modes

### Added - 2026-04-11

#### Web Search Support
- Added `@web` syntax support for triggering web search capabilities
- `@web` expands to reference `tavily-search` and `tavily-extract` skill files
- Requires optional skills installation in `.claude/skills/` directory
- Updated README with web feature description and skills installation instructions

### Added - 2026-04-10

#### System Prompt Chinese Translation
- Added complete Chinese translation of system prompts in `docs/system_prompt_chinese_translation.md`
- Provides full reference for Chinese-speaking users to understand the agent's behavior and guidelines

#### File Expansion For User Messages
- Implemented file expansion feature allowing users to reference files in messages using `@file_path` syntax
- Created `claude_code/core/file_expansion.py` module with `FileExpander` class for handling file references
- Added automatic file content embedding when user messages contain file references
- TUI now displays expanded files with visual indicators showing file names and line counts
- Added CSS styles for file expansion display in TUI
- Updated session storage to preserve expanded file information for session persistence

#### TUI Session Switcher Command
- Added "/sessions" command in TUI to switch between saved sessions without restarting
- Created `SessionResumeModal` widget for interactive session selection
- Added `_show_session_picker()` method to launch the session picker modal
- Added `_load_session()` method to load and replace current session with selected one
- Added `_restore_session_messages()` to re-render persisted messages after session switch
- Session switcher preserves query engine state, message history, and usage metrics
- Added regression test `test_session_picker_uses_compact_action_buttons` for modal UI

#### TUI Clear Command For New Session
- Added "/clear" command in TUI to start a fresh session without restarting the app
- Typing "/clear" in the input now resets the session ID, clears all messages, and shows the welcome widget
- `QueryEngine.clear()` now generates a new session ID to ensure a clean slate
- Added `_start_new_session()` method in REPLScreen to handle session reset
- Added regression test `test_clear_command_starts_new_session` to verify clear behavior

### Changed - 2026-04-10

#### Test Suite Consolidation
- Removed redundant test files from root directory (`test_cli.py`, `test_core.py`, `test_tui.py`)
- Moved essential test logic into `claude_code/core/query_engine.py` and `claude_code/ui/screens.py` as inline methods
- Reduced test code by 3374 lines while preserving core functionality testing

#### Session Timestamp Timezone
- Changed session timestamps from UTC to local system timezone
- Renamed `_utc_now()` to `_local_now()` in `SessionStore`
- Timestamps now use `datetime.now().isoformat()` instead of `datetime.now(timezone.utc).isoformat()`

### Added - 2026-04-09

#### TUI Session Persistence And Resume
- Added persistent TUI session storage under `~/.claude-code-python/sessions/`
- Each new TUI conversation now gets a unique session ID and a default title derived from the first user prompt
- Added `--resume <session_id>` to resume a saved TUI session
- Added `--sessions` to choose a saved TUI session from an interactive terminal picker before launch
- TUI session snapshots now save at the same stable rollback boundaries used by `Escape`, so interrupted partial turns do not become resumable history
- Resume now reconstructs prior assistant/tool transcript structure so each tool call still renders as a single collapsible block after reload
- Added regression coverage for session save boundaries, resume transcript rebuild, and session-picker helpers

### Fixed - 2026-04-10

#### TUI Command Consistency
- Updated TUI session commands to include leading slashes for consistency (`/sessions`, `/clear`)
- Fixed command option naming in CLI help text for better clarity

#### Project Name Consistency
- Updated all references from 'claude-code' to 'claude-code-python' across documentation and code
- Updated README files to reflect the correct project name
- Cleaned up outdated content in README_EN.md

#### Welcome Message Clarity
- Updated welcome message in `WelcomeWidget` to clearly explain session commands

#### System Prompt Guidelines
- Refined guidelines in `get_simple_doing_tasks_section` for clarity on when to ask for user confirmation
- Refined guidelines in `get_simple_tone_and_style_section` for more specific communication style instructions

#### History Navigation Direction
- Corrected navigation direction description in `_navigate_history` method (Up for older, Down for newer)

### Fixed - 2026-04-09

#### Escape Rollback And Tool Undo
- Fixed `Escape` turn rewind in the TUI so interrupted turns now restore the last stable transcript boundary instead of leaving the UI in a partial thinking or partial message state
- When `Escape` semantically undoes the latest submit, the prompt returns to an editable draft and the just-added prompt history entry is removed
- Finished tool batches now become the rollback boundary only after the batch completes, so rewinding from a later thinking phase preserves the last completed assistant/tool result state
- `Bash` tool cancellation now terminates the in-flight subprocess immediately when a turn is interrupted
- `Write` and `Edit` tool side effects are now rolled back on interrupted turns by restoring overwritten file contents or deleting newly created files
- Added regression coverage for TUI rollback boundaries, transcript/backend message alignment after resend, and file restoration for interrupted `Write` / `Edit` tool calls

#### Tool Error Status In Transcript
- Fixed `ToolResultEvent.is_error` propagation so tool-specific failures no longer render with a success indicator in the TUI or CLI
- Added per-tool error classification for `Bash`, `Read`, `Write`, `Edit`, `Glob`, and `Grep`
- `Bash` tool now treats non-zero exit codes and timeouts as errors for transcript rendering, even when the shell command returns structured stdout/stderr text
- TUI tool titles now use colored status dots (`●`) instead of textual `[OK]` / `[ERR]` prefixes, while keeping the summary text in the normal foreground color
- Failed tool titles now use action-oriented summaries such as `Failed to run ...` / `Failed to read ...` instead of showing a raw error code or error line as the title
- Added regression coverage for tool error classification in both `QueryEngine` and the TUI

### Changed - 2026-04-09

#### Default TUI Mode and Logging Behavior
- Changed default mode from CLI to TUI when running `claude-code-python` (or `cc-py`) without flags
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
- Added persistent in-session prompt history navigation on Up/Down, with history saved to `~/.claude-code-python/input_history.json`.
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

**Symptom**: In `claude-code-python --tui` (or `cc-py --tui`), tool calls were producing output (scrollbar moving), but the transcript area appeared as a black/blank block.

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
