# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed - 2026-04-08

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
- Added `Collapsible` sections for tool input/output
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
