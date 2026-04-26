# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed - 2026-04-27

#### Vite Web UI Diff Highlighting
- Fixed Vite diff rendering by passing `highlight.js` into `diff2html-ui-base` as the constructor highlighter instead of an ignored config field
- Moved the Highlight.js GitHub theme import into the Vite global stylesheet so diff and markdown code highlighting share the same bundled CSS path
- Updated web frontend source tests to validate the Vite component, composable, utility, and stylesheet layout instead of relying on legacy static HTML internals
- Fixed web-visible file expansion reconstruction so `@web` remains a web-search marker and does not appear as expanded Tavily skill files in restored user messages

### Added - 2026-04-26

#### DeepSeek Reasoning Content Preservation Across Tool Turns
- Added `_get_reasoning_content()` to extract thinking blocks from assistant messages for replay in subsequent API requests
- Added `_is_reasoning_persistent_turn()` to detect tool-using turns where reasoning content must be preserved across multiple assistant messages
- Modified `_convert_messages_to_openai_format()` to include `reasoning_content` in API messages for DeepSeek-style thinking models during ongoing tool turns
- Modified `parse_stream_chunk()` to accept `reasoning` field alias alongside `reasoning_content` for broader OpenAI-compatible provider compatibility
- Added `tests/test_openai_client_reasoning_content.py` with four test cases covering reasoning preservation, boundary dropping, multi-turn tool persistence, and streaming alias parsing

### Fixed - 2026-04-25

#### HTTP Client Proxy Bypass for Localhost
- Set `trust_env=False` on `CCCodeHttpClient` to prevent httpx from reading proxy environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, etc.), allowing frontend-to-backend connections on localhost when a system proxy or Clash is active

### Fixed - 2026-04-14

#### API Server Cleanup on Terminal Close
- Removed `start_new_session=True` from API server subprocess to ensure it terminates when the TUI client exits
- Added signal handlers for `SIGHUP` and `SIGTERM` to properly clean up the API server when terminal closes unexpectedly
- API server now correctly stops when user closes terminal window directly

### Changed - 2026-04-14

#### TUI Input Shortcut Aliases
- Added terminal-style shortcut aliases in `InputTextArea` so `Shift+Left/Right` moves by word, `Shift+Backspace` deletes one word to the left, and `Ctrl+Shift+Backspace` deletes to the start of the line
- Updated the welcome tips text to document the new input shortcuts without overflowing the right-side panel
- Added `tests/test_ui_input_shortcuts.py` to cover the shortcut alias behavior

### Changed - 2026-04-14

#### TUI Transcript Collapsible and Tool Result Responsiveness
- Removed the transcript collapsible title/toggle side effect that cleared all tool-result scroll locks when expanding or collapsing think/tool blocks
- Optimized tool-result scroll lock release to skip inactive widgets instead of scanning and resetting every tool output block
- Added an early return in `ToolResultLogWidget.deactivate_pointer_scroll()` so already-unlocked logs no longer trigger redundant UI work
- Optimized tool output tail refreshes to update only the tail hint text instead of clearing and rewriting the full `RichLog` body
- Updated the active tool-output hint text from `click outside` to `click here` while keeping `Ctrl+E` as the explicit exit shortcut
- Kept collapsible titles selectable while reverting the incomplete `RichLog` text-selection experiment
- Removed inline markdown code background fill so ``code`` spans render without a shaded chip
- Updated TUI scroll-lock tests to reflect the new collapsible and tool-result interaction behavior

### Changed - 2026-04-14

#### TUI Color Variable Consistency
- Changed `$text-muted` to `$text-secondary` in autocomplete popup for consistent theming
- Changed `$text-muted` to `$text-secondary` in diff view ellipsis
- Changed `$text-muted` to `$text-secondary` in rewind modal info text
- Removed excess blank lines in autocomplete.py

#### TUI Thinking Content Style
- Changed thinking content from normal text style to italic for better visual distinction

### Added - 2026-04-14

#### TUI Tool Result Scroll Lock and Transcript Collapsible Mode
- Added explicit scroll activation for tool results: click on a tool output to lock scrolling inside it
- Added scroll lock exit: click outside or press Ctrl+E to release scroll lock
- Added visual feedback for active scroll lock (background highlight + status hint)
- Added transcript collapsible mode toggle with Ctrl+O (switch between compact/expanded views)
- Added transient progress modal during transcript mode switches to hide layout flicker
- Added streaming context awareness: Edit/Write blocks stay expanded while assistant is streaming
- Added mode indicator in context usage bar (shows "Mode: compact/expanded (ctrl+o to toggle)")
- Added `cc_code/ui/transcript_mode_modal.py` - ProgressStatusModal for UI operations
- Added `tests/test_ui_tool_result_scroll_lock.py` - Tests for scroll lock and mode switching
- Updated `ToolResultLogWidget` with pointer scroll activation/deactivation logic
- Updated `ThinkingBlockWidget` and `ToolUseWidget` with transcript collapsible mode support

### Changed - 2026-04-14

#### README Cleanup
- Remove duplicate Japanese title from README.md

### Added - 2026-04-14

#### Web Frontend Mobile Responsive Improvements
- Added mobile viewport height handling with --app-height CSS variable using 100dvh
- Added dynamic viewport height update for iOS keyboard visibility changes via visualViewport events
- Added mobile-first responsive layout with Tailwind sm: breakpoints
- Added markdown table horizontal scrolling wrapper (.markdown-table-wrapper)
- Added responsive diff view: side-by-side on desktop, line-by-line on mobile (< 768px)
- Added compact diff view on mobile: hide line numbers, file tags, and other UI elements
- Added iOS input zoom prevention: set composer input font-size: 16px !important
- Added word-break and overflow-wrap guards for long text/content
- Added @media (max-width: 767px) CSS section with mobile-specific styles
- Added responsive padding: p-3 on mobile, p-4 sm:p-6 md:p-6 on larger screens
- Updated renderMarkdown() to automatically wrap tables in scrollable container
- Added prefersCompactDiff() helper to detect mobile viewport
- Added syncViewportMetrics() to handle resize and visualViewport events
- Added 8 new tests in test_web_frontend_source.py for mobile features

### Fixed - 2026-04-14

#### TUI Markdown First Block Top Margin
- Fixed transcript messages starting with extra blank line by setting first markdown block top_margin = 0
- Removed hardcoded top_margin = 1 for first block in Markdown.render()
- Added `test_streaming_markdown_first_block_has_no_top_margin()` test
- Updated existing spacing test assertions

#### TUI Bug Fixes and Improvements
- Fixed `InputTextArea` cursor_blink compatibility with different Textual versions
- Fixed tool title prefix to show "● " before tool summary
- Fixed `Markdown._total_lines` calculation (removed +1 bottom spacing)
- Updated `tests/test_ui_streaming_markdown_layout.py` test assertion

### Added - 2026-04-14

#### Session Compaction (/compact command)
- Added `/compact` and `/summarize` commands to compress conversation history
- Implemented compaction logic in `cc_code/core/compaction.py` with message summarization
- Added `_filter_compacted_messages()` and `_handle_compact()` methods in `QueryEngine`
- Added `CompactRequest` and `compact_stream()` in server API
- Added `stream_compact()` method in HTTP client
- Added `_chat_completion_raw()` in OpenAI client for internal API calls
- Compaction preserves ALL history messages, adds summary marked as `is_compact_summary`
- Added `tests/test_compaction.py` - Unit tests for compaction functionality

#### TUI Theme Support and UI Layout Improvements
- Added `FlushCollapsible` and `FlushCollapsibleTitle` widgets for cleaner collapsible UI without leading spacing
- Added tree-like output branch decoration for tool results (│ and ╰ characters)
- Added output line count summary with scroll hint for long tool outputs
- Added `TranscriptContainer` with FOCUS_ON_CLICK=False to prevent scroll area from stealing focus
- Added AUTO_FOCUS="#user-input" to REPLScreen to keep composer focused
- Added focus management to keep input focused after toggling transcript collapsibles
- Added `markdown-host` container to own horizontal padding for markdown content
- Updated `ToolResultLogWidget` to disable syntax highlighting and focus-on-click
- Updated markdown spacing: reduced heading top margins, hr margins, and code fence padding
- Updated styles to make scrollbars fully transparent
- Updated message block padding for cleaner layout
- Added `tests/test_ui_markdown_spacing.py` - Tests for markdown spacing improvements
- Updated existing UI tests to cover new autofocus and output branch behavior

#### Instruction Loading (CLAUDE.md, AGENTS.md)
- Added `cc_code/core/instruction.py` - Instruction loading service for CLAUDE.md, AGENTS.md, and custom instruction files
- Added automatic discovery and loading of project-level instruction files (searching upward from cwd)
- Added global-level instruction loading from `~/.config/opencode/` and `~/.claude/`
- Added support for custom instruction files/URLs via settings.json
- Added nearby instruction loading when reading files (walks upward from the file being read)
- Added per-message deduplication tracking to avoid loading the same instruction multiple times
- Added concurrent file/URL reading for improved performance
- Added `docs/INSTRUCTION_LOADING.md` - Design documentation for the instruction loading feature
- Added `tests/test_instruction.py` - Unit tests for instruction loading functionality
- Updated `QueryEngine` to support async system prompt building with instructions
- Updated `Read` tool to append nearby instructions when reading files
- Updated `ToolResultContent` to support metadata tracking for loaded instruction files
- Updated `ToolContext` to pass instruction service and message context
- Updated settings system to support custom instructions list

### Fixed - 2026-04-13

#### TUI Session Restore Auto-Follow
- Fixed TUI session restore so loading a long persisted conversation stays pinned to the latest message while history widgets are being rebuilt
- Restored incremental bottom anchoring during `_render_messages()` instead of waiting for a single final anchor after the full session render completes
- Re-anchored tool-result updates during history reconstruction so assistant tool blocks do not break restore-time auto-follow
- Added `tests/test_ui_session_restore_autofollow.py` to cover the session-load auto-follow regression

### Changed - 2025-01-15

#### TUI Model Management Refactoring
- Refactored TUI to fetch model information from server API instead of local settings
- Added `GET /api/models` endpoint to list all available models from server
- Added `CCCodeHttpClient.list_models()` method for fetching model list
- `ModelSelectModal` now receives models from server response instead of local `AppSettings`
- Chat requests now include optional `model` parameter to specify model per request
- Model info is fetched on TUI startup and after session switches
- Context usage display now shows initial state (0 tokens) before first message
- Usage stats are reset after model switch for accurate context display
- Added `settings.json` to `.gitignore` to prevent accidental commit of user configs

### Fixed - 2025-01-14

#### Session Persistence
- Fixed session persistence to skip saving empty sessions (no user messages)
- Added validation to prevent saving sessions without any user-authored messages
- Sessions with only system messages or no messages at all will not be persisted to disk
- This prevents cluttering the session list with empty/meaningless sessions

### Removed - 2025-01-14

#### API Cleanup - Removed Unused Endpoints
- Removed `GET /api/revert_state/{session_id}` endpoint - not used by any frontend (TUI or Web)
- Removed `POST /api/unrevert` endpoint - not used by any frontend (TUI or Web)
- Removed `UnrevertRequest` model from API server
- Removed `CCCodeHttpClient.get_revert_state()` method
- Removed `CCCodeHttpClient.unrevert()` method
- Removed `SessionRevertService.unrevert()` method from core revert service
- Kept internal `QueryEngine` revert state methods (`get_revert_state`, `set_revert_state`, `clear_revert_state`) as they are used by the revert workflow
- Total code reduction: ~87 lines of unused code

### Added - 2026-04-13

#### High-Performance TUI Markdown Renderer
- Added `cc_code/ui/patched_markdown.py`, a virtualized Markdown renderer for the TUI transcript based on the implementation direction from `0x7c13/textual#2`
- Replaced the heavier widget-tree markdown path with a `ScrollView` / Line API based renderer for better large-output performance
- Preserved core Textual markdown behavior including headings, lists, blockquotes, tables, code fences, links, and table of contents integration
- Source reference: https://github.com/0x7c13/textual/pull/2/changes

### Fixed - 2026-04-13

#### TUI Markdown Text Selection
- Fixed `cc_code/ui/patched_markdown.py` so virtualized markdown text can be selected and copied again
- Added Textual selection offset metadata in `render_line()` via `Strip.apply_offsets(...)` so the compositor can map mouse drags to text coordinates
- Added markdown-specific `get_selection()` and `selection_updated()` handling for the custom `ScrollView` renderer
- Added selection highlight rendering for the custom markdown line pipeline so drag selection is visible in the transcript
- Root cause: the optimized custom markdown widget bypassed Textual's standard `Static`/`Content` selection path but did not re-implement the required Line API selection hooks
- Changed untyped fenced code blocks to render as plain text instead of passing through syntax highlighting, avoiding false red error backgrounds from lexer misclassification of unusual characters

#### Transcript Auto-Follow
- Reworked TUI transcript auto-follow to use Textual's scroll anchoring on `#content-area` instead of a custom follow-state implementation in `MessageList`
- Auto-follow now stays active while the transcript is pinned near the bottom and stops when the user scrolls away, matching Textual's intended behavior for scrollable widgets
- New requests explicitly re-anchor the transcript so fresh streaming output starts from a pinned-to-bottom state
- Restored bottom anchoring after loading a historical session or rebuilding transcript history during rewind so restored conversations open at the latest message instead of the first page
- Paused live markdown flushes while the user is scrolled away from the bottom, then flushed buffered markdown when the stream finishes, preventing visible table flicker in older transcript content during continued streaming

### Changed - 2026-04-13

#### Configuration System Migration
- Migrated from `.env` file to unified `~/.claude-code-python/settings.json` for all configuration
- Created `cc_code/core/settings.py` - Centralized settings management with model profiles
- Settings now support multiple model configurations with unique IDs
- Added automatic migration from legacy `.env` to `settings.json` on first run
- Removed environment variable dependencies (`CLAUDE_CODE_API_URL`, `CLAUDE_CODE_API_KEY`, `CLAUDE_CODE_MODEL`, `CLAUDE_CODE_THEME`)
- Updated `cc-api` CLI to use `SettingsStore` instead of environment variables
- Updated TUI app to read theme from settings instead of environment
- Context window tokens now read from model settings instead of environment variable

### Added - 2026-04-13

#### Real-time Model Switching
- Added `/model` command in TUI to display current model and available models
- Added `/model <model_id>` command to switch model in real-time during session
- Created `cc_code/ui/model_select_modal.py` - Modal for selecting models
- Added API endpoint `POST /api/model` for model switching
- Session persistence now includes `model_id` to remember model choice per session
- Added `switch_model()` method to `QueryEngine` for dynamic model reconfiguration
- TUI context bar now displays current model name
- Welcome widget updates model name when model is switched

#### Command Autocomplete
- Created `cc_code/ui/autocomplete.py` - Autocomplete system for TUI input
- Added autocomplete popup for slash commands (`/help`, `/model`, `/rewind`, `/sessions`, `/clear`, `/exit`)
- Added autocomplete popup for `@` references (`@web` and file paths)
- Implemented keyboard navigation (↑/↓/Enter/Tab/Esc) in autocomplete popup
- Added smart scroll adjustment when autocomplete popup expands input area
- InputTextArea now supports autocomplete mode with special key handling

### Changed - 2026-04-13

#### UI Style Improvements
- Made all scrollbars transparent for cleaner visual appearance
- Adjusted padding and margins across message blocks, tool blocks, and widgets
- Simplified modal styles (removed borders, adjusted padding)
- Updated system message styling (changed from warning to success color)
- Improved message layout consistency with transcript-block class
- Reduced visual clutter by removing unnecessary borders and margins

### Changed - 2026-04-13

#### Documentation Updates
- Updated `README.md` with new settings.json configuration format and examples
- Added documentation for `/model` command in TUI
- Added TUI logging guidelines in `AGENTS.md` - all TUI debug logs must use `tui_log()` function
- Removed completed TODO item for model real-time switching

#### Test Updates
- Added `tests/test_settings.py` - Unit tests for settings management
- Added `tests/test_ui_autocomplete.py` - Unit tests for autocomplete functionality
- Removed obsolete `tests/test_ui_app.py` - Tests for deprecated environment variable theme configuration

#### File Rewind/Revert Feature
- Added `/rewind` command in TUI to revert file changes to a previous conversation point
- Created `cc_code/core/snapshot.py` - Git-based independent snapshot system for tracking file changes during tool execution
- Created `cc_code/core/revert.py` - Session revert service supporting undo/redo of file changes
- Created `cc_code/ui/rewind_modal.py` - TUI modal for selecting a message to rewind to
- Added `PatchContent` and `StepStartContent` message blocks for tracking file modifications
- Added API endpoints: `/revert`, `/unrevert`, `/revert_state/{session_id}`, `/snapshot_status/{session_id}`
- Session persistence now includes `revert_state` and `total_diff` for tracking file change history
- TUI context bar now shows file modification stats (additions/deletions/files) when files have been modified

### Changed - 2026-04-13

#### Browser UI Consolidation
- Removed the standalone browser UI entry point and its package modules
- Moved browser UI startup into `cc-api`, which now serves the Vue frontend and FastAPI API from one process
- Updated README, startup output, and tests to point to `cc-api` only

### Fixed - 2026-04-12

#### Web UI / API Mount Compatibility
- Added `create_app(api_prefix=...)` in `cc_code.api.server` so the FastAPI backend can run directly or be mounted under `/api`
- Fixed browser UI startup by mounting the unprefixed API app without double-prefixing browser routes
- Restored `web_enabled` serialization from `@web` in `message_to_dict()` so web-enabled messages serialize correctly
- Added tests for direct and mounted API route layouts plus `@web` serialization

#### Documentation Alignment
- Updated `README.md` to distinguish the TUI HTTP path from the browser UI FastAPI path

### Changed - 2026-04-12

#### Logging Tag Standardization
- Standardized log output to use source-based tags: `[FASTAPI]`, `[ENGINE]`, `[CLIENT]`, and `[TUI]`
- Removed stale `[SERVER]` prefixes from API server logs so the emitted format now reflects the actual module source

#### HTTP API Runtime Migration
- Replaced the old gRPC client/server stack with `CCCodeHttpClient` and the standalone `cc-api` FastAPI server for the TUI path
- Refactored the browser UI to share the same FastAPI API layer while serving the Vue frontend from one process
- Added/updated CLI entry points and package metadata to match the HTTP-based runtime
- Fully removed the obsolete gRPC proto/client/server implementation and generation script from the active codebase

#### Web Frontend UX Improvements
- Added `@web` reference detection with visual indicator showing when web search is enabled
- Improved auto-scroll behavior: output now auto-follows only when user is near bottom
- Fixed history navigation: added proper buffer management for Up/Down arrow navigation
- Added global keyboard shortcuts: Escape to close modal or send interrupt, Ctrl/Cmd+C to copy selection
- Refactored message creation logic with `createUserMessage()` helper for consistency
- Server now includes full message data in `message_complete` event for proper user message display

#### Web Server Improvements
- Added `has_web_reference()` for detecting `@web` syntax in user input
- Added `build_visible_file_expansions()` for reconstructing file references in frontend
- Added `create_app(api_prefix=...)` so the shared API app can run directly or be mounted under `/api`
- Refactored `message_to_dict()` and `event_to_dict()` to include working directory context and `@web` inference

#### Test Additions
- Added `tests/test_web_server.py` for web server unit tests and route-prefix regression coverage
- Added `tests/test_web_frontend_source.py` for frontend source validation

#### Miscellaneous
- Added `.omx/` to `.gitignore`

### Added - 2026-04-12

#### Web UI with Vue 3 (FastAPI-based)
- Refactored `web` module with FastAPI backend and Vue 3 frontend
- Browser UI is served by `cc-api` at `/`
- Single-file Vue 3 frontend (`index.html`) with Tailwind CSS styling
- Added dependencies: FastAPI, uvicorn, pydantic to `pyproject.toml`
- Features:
  - Real-time streaming with SSE
  - Session management (list, load, new)
  - Tool block rendering with collapsible UI
  - Diff visualization for Edit/Write tools
  - Markdown rendering with syntax highlighting
  - Input history navigation (↑/↓)
  - Token usage display
  - Dark theme with glass-morphism design

### Fixed - 2026-04-12

#### Web UI Markdown File Diff Display Issue
- Fixed sticky line numbers in diff display for markdown files not scrolling properly
- Root cause: diff2html library uses `position: sticky` for line numbers, which breaks when parent container has `overflow: auto`
- Fix: Removed `overflow: auto` from `.diff-container` and forced `position: relative` on line number elements
- Line numbers now scroll normally with content instead of being "stuck" at the top

#### Tool Use Duplicate Rendering in Web UI
- Fixed duplicate tool blocks appearing in web frontend
- Root cause: Backend sent `ToolUseEvent` twice (preview phase + before execution)
- Fix: Check `previewed_tool_use_ids` before emitting duplicate event
- Fixed `loadSession` in web to:
  - Handle `tool` role messages correctly
  - Reset `sessionToolUses` between user messages
  - Track `lastAssistantMsg` for proper message association

### Changed - 2026-04-12

#### Web UI Refactoring and Bug Fixes
- Extracted inline CSS and JavaScript from `index.html` to separate files (`styles.css`, `app.js`)
- Added routes in `server.py` to serve static CSS and JS files
- Fixed message ordering issue: thinking content now appears in correct order (FIFO)
- Fixed code diff not displaying during real-time streaming:
  - Store tool name and input in DOM data attributes for later retrieval
  - Always save tool info to `pendingToolUses` even if block already exists
  - Use `updateToolResult` consistently for diff rendering
- Marked browser UI as experimental feature in README

### Changed - 2026-04-11

#### UI Utils Simplification - Remove Over-engineering
- Merged 12 over-abstracted helper functions into `summarize_tool_result()` internal nested functions
- Eliminated unnecessary function chain: `_normalize_summary_text`, `_compact_file_path_in_summary`, `_basename_from_tool_input`, `_quote_search_pattern`, `_prefix_tool_name`, `_append_matching_pattern`, `_summarize_glob_result`, `_summarize_grep_result`, `_summarize_tool_error`
- Kept identical functionality while reducing cognitive overhead
- Code reduction: 287 lines → 191 lines (~33% reduction)

### Changed - 2026-04-11

#### Message Widgets Refactoring - Remove Over-engineering and Redundancy
- Merged `ThinkingWidget` into `ThinkingBlockWidget` - eliminated unnecessary class layer
- Merged `AssistantMessageWidget` into `MessageWidget` with `streaming=True` parameter
- Simplified `ToolUseWidget` state management:
  - Reduced from 7 state variables to 4
  - Consolidated `_result_summary`, `_result_output_lines`, `_result_is_error` into single `_result` tuple
  - Removed `_pending_result_render` flag and its complex logic
- Extracted configuration constants to `utils.py`:
  - `TOOL_RESULT_TRUNCATE_LENGTH = 500`
  - `PREVIEW_LINE_MAX_WIDTH = 88`
  - `COMMAND_PREVIEW_MAX_WIDTH = 64`
  - `DETAIL_LINE_MAX_WIDTH = 104`
- Added `ROLE_CONFIG` dictionary as single source of truth for role mappings
- Renamed `MessageList.create_assistant_widget()` to `create_streaming_widget()`
- Removed `_tool_widgets` list from `MessageWidget` (was unused, only `_tool_widgets_by_id` needed)
- Code reduction: 664 lines → 604 lines (~9% reduction)

### Changed - 2026-04-11

#### Tool Result Display Refactor with Log Widget
- Replaced manual text truncation with Textual's `Log` widget for tool results
- Tool results (Read, Bash, Glob, Grep, etc.) now use `ToolResultLogWidget` instead of multiple `Static` widgets
- File expansion display also uses `ToolResultLogWidget` for consistent behavior
- Removed all horizontal and vertical truncation - Log widget handles scrolling natively
- Log widget configuration:
  - `height: auto` - automatically shrinks for small content
  - `min-height: 1` - minimum 1 line
  - `max-height: 10` - maximum 10 lines with scrolling
  - `scrollbar-visibility: hidden` - cleaner UI while maintaining scroll functionality
  - Syntax highlighting enabled
  - Auto-scroll to bottom enabled
- Benefits:
  - Full content display without truncation
  - Native horizontal and vertical scrolling
  - Space-efficient for small outputs (auto-shrink)
  - Clean UI without visible scrollbars
  - Better readability with syntax highlighting

### Changed - 2026-04-11

#### Refactor Streaming Markdown Component
- Renamed `TranscriptMarkdownWidget` to `StreamingMarkdownWidget` for clarity
- Removed redundant `StreamingTextWidget` class (was just a thin wrapper)
- Removed unnecessary alias methods `append_text()` and `update_text()` (over-engineering)
- Updated all call sites to use `append_text()` and `set_markdown_text()` directly
- Simplified API by consolidating to single class with clear method names

#### Extract Streaming Markdown Component to Separate Module
- Created new `cc_code/ui/streaming_markdown.py` module for streaming markdown widgets
- Moved `TranscriptMarkdownWidget` and `StreamingTextWidget` from `message_widgets.py` to dedicated module
- Updated `message_widgets.py` to import from new module
- Updated `ui/__init__.py` to export markdown components from new location
- Improved code organization by isolating markdown rendering logic into standalone component
- No functional changes - purely structural refactoring for better maintainability

#### Tooltip Global Disable via Monkey Patch
- Added monkey patch in `cc_code/__init__.py` to override `textual.widget.Widget.with_tooltip` method
- All tooltip calls now set `self.tooltip = None` globally, effectively disabling all tooltips
- Removed `_clear_tooltips()` and `_schedule_tooltip_cleanup()` methods from `TranscriptMarkdownWidget` as they are no longer needed
- Simplified tooltip management by using a single global patch instead of per-instance cleanup

### Changed - 2026-04-11

#### UI Code Cleanup
- Removed unused variables: `_current_thinking`, `_current_text`, `_tool_use_context`
- Removed unused local variable `tool_use_context` in `_render_messages` method
- Removed redundant `_text` variable in `StreamingTextWidget` (duplicate of `_markdown_text`)
- Refactored tool context reset logic into `_reset_tool_contexts()` method
- Consolidated 6 duplicate reset blocks into single method call
- Extracted duplicate mouse event handlers into `_focus_input_if_needed()` method
- Reduced code duplication by eliminating redundant state variables
- Improved code maintainability by removing 15 lines of unused/redundant code

### Changed - 2026-04-11

#### gRPC Interface Simplification
- Simplified `StreamChat` RPC from streaming request to unary request
- Removed `StreamChatRequest` wrapper message, now using `ChatRequest` directly
- Removed unused RPC methods: `GetState`, `DeleteSession`, `ClearSession`
- Removed unused message types: `GetStateRequest`, `GetStateResponse`, `DeleteSessionRequest`, `DeleteSessionResponse`, `ClearSessionRequest`, `ClearSessionResponse`

#### Client API Cleanup
- Removed unused client methods: `get_state()`, `delete_session()`, `clear_session()`
- Simplified `stream_chat()` to use unary request instead of generator
- Added debug logging for all gRPC requests (session creation, chat, interrupt, etc.)
- Removed `delete-session` CLI command

#### Server Implementation Simplification
- Added port availability check to prevent duplicate server instances
- Removed unused RPC implementations: `GetState`, `DeleteSession`, `ClearSession`
- Simplified `StreamChat` to handle unary request
- Added comprehensive debug/info logging for all incoming requests
- Improved error handling with `log_full_exception`

#### Query Engine Refactoring
- Removed unused `QueryResult` dataclass
- Removed unused `ask()` convenience function
- Removed unused `run()` method with callbacks
- Simplified error handling: removed `APINetworkError`, using unified `APIError`
- Added debug logging for tool use preview and execution
- Auto-save session on API errors

#### Logging Configuration Improvements
- Renamed `log_exception()` to `log_full_exception()` for clarity
- Reorganized logging setup: file logging only enabled in debug mode
- Non-debug mode: console logging at INFO level only
- Debug mode: both file and console logging at DEBUG level
- Improved exception logging format

#### UI/UX Improvements
- Improved command history navigation with proper buffer management
- Added `Shift+Up/Down` shortcuts for cursor navigation in input area
- Simplified session initialization: removed `initial_session` parameter
- Improved session resume: handle pending user text correctly
- Removed unused UI methods: `truncate()`, `add_tool_result()`, `get_message()`, etc.
- Fixed error handling to use `log_full_exception`
- Added debug logging for file expansions
- Cleaned up message rendering logic

#### API Client Error Handling
- Removed `APINetworkError`, using unified `APIError` for all errors
- Added `log_full_exception` for better error diagnostics
- Improved tool call logging with truncated args preview
- Simplified exception handling in chat completion stream

### Fixed - 2026-04-11

#### gRPC Verbose Log Suppression
- Added `suppress_grpc_logs()` function to suppress verbose gRPC C++ core library logs
- Fixed "FD from fork parent still in poll list" warnings appearing in stderr when executing bash commands
- Set `GRPC_VERBOSITY=ERROR` and `GRPC_TRACE=none` environment variables to suppress INFO-level internal logs
- These logs come from gRPC's internal event polling mechanism and are not controlled by Python's logging system

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
- Deleted `cc_code/client/grpc_engine.py` (no longer needed)
- Removed `RequestStartEvent` (simplified event flow)
- Removed `FrontendSnapshot` class and frontend state capture logic
- Removed `sync_from_message()` method

#### Added Utility Module
- Added `cc_code/utils/logging_config.py` for unified logging configuration
- Provides `setup_server_logging()`, `setup_client_logging()` and `log_full_exception()` functions

#### Proto Updates
- Removed `python_package` option (using dynamic imports)
- Added `Message.usage` field for token statistics transmission
- `proto/__init__.py` now uses dynamic path import

#### UI Refactor
- `CCCodeApp` now receives `CCCodeClient` instead of `QueryEngine`
- `REPLScreen` completely refactored as stateless frontend, all state managed via gRPC
- `SessionResumeModal` now uses `CCCodeClient` to fetch session list
- Simplified interrupt handling: sends interrupt signal to server instead of local rollback

#### QueryEngine Improvements
- Added `create_from_session_id()` class method to create engine from session ID
- Added `_persist_session()` method to persist on session end
- Added `session_store` parameter for server-side persistence

### Changed - 2026-04-11

#### Code Cleanup
- Removed unused `ToolProtocol` class and `ToolInputSchema.additional_properties` field
- Removed redundant `QueryState.max_turns` field (duplicates `QueryConfig.max_turns`)
- Removed redundant `is_error_result()` implementations in tool classes (now inherit from `BaseTool`)
- Removed unused `Bash = BashTool()` global instance
- Fixed API URL normalization bug in CLI
- Reduced ~50 lines of redundant code

### Changed - 2026-04-11

#### Code Refactoring
- Removed unused `StreamEvent` subclasses and redundant tool helper functions
- Extracted `setup_logging()` function and pagination helpers to reduce code duplication
- Simplified environment variable handling and API URL normalization
- Reduced ~126 lines of redundant code

### Removed - 2026-04-11

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
- Created `cc_code/core/file_expansion.py` module with `FileExpander` class for handling file references
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
- Moved essential test logic into `cc_code/core/query_engine.py` and `cc_code/ui/screens.py` as inline methods
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
- Added `cc_code/ui/diff_view.py`, adapted from Toad, for inline file diff rendering in the TUI
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
- Removed `cc_code/tools/file_tools.py` (650 lines) - contained duplicate tool definitions
- All tools are already defined in separate files: `read_tool.py`, `write_tool.py`, `edit_tool.py`, `glob_tool.py`, `grep_tool.py`
- Updated imports in `cli.py`, `test_core.py`, and debug scripts to use `from cc_code.tools import ...` instead of `from cc_code.tools.file_tools import ...`
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
- Split 1349-line `cc_code/ui/app.py` into multiple modules for better maintainability:
  - `cc_code/ui/constants.py` - Theme colors (CLAUDE_ORANGE, etc.)
  - `cc_code/ui/styles.py` - TUI CSS definitions
  - `cc_code/ui/utils.py` - Text sanitization and tool summarization functions
  - `cc_code/ui/widgets.py` - Clawd and WelcomeWidget
  - `cc_code/ui/message_widgets.py` - MessageList, MessageWidget, AssistantMessageWidget, ToolUseWidget, StreamingTextWidget
  - `cc_code/ui/screens.py` - REPLScreen
  - `cc_code/ui/app.py` - CCCodeApp (simplified main app)
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

- Created new `cc_code/core/prompts.py` module with complete system prompt sections:
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

- `cc_code/core/prompts.py` - New module containing all system prompt definitions
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

- Core message types and data models (`cc_code/core/messages.py`)
- Tool system base classes (`cc_code/core/tools.py`)
- Query engine with streaming support (`cc_code/core/query_engine.py`)
- OpenAI-compatible API client (`cc_code/services/openai_client.py`)
- File tools: Read, Write, Edit, Glob, Grep (`cc_code/tools/file_tools.py`)
- Bash tool with sandbox support (`cc_code/tools/bash_tool.py`)
- CLI interface with Click (`cc_code/cli.py`)
- TUI interface with Textual (`cc_code/ui/app.py`)
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
