# Release Notes

This document reconstructs early version milestones (`0.1.0`, `0.2.0`, `0.3.0`) from git history.

## Evidence Summary

- No git tags exist for `v0.1.0`, `v0.2.0`, or `v0.3.0`.
- Version boundaries are identified from `pyproject.toml` version bump commits.
- `0.3.0` is additionally confirmed by the first `package.json` introduction at version `0.3.0`.

| Version | Boundary Commit | Date | Evidence |
|---|---|---|---|
| 0.1.0 | `82235e7` | 2026-04-08 | Initial commit with `pyproject.toml` version `0.1.0`; `CHANGELOG.md` contains `## [0.1.0] - Initial Release` |
| 0.2.0 | `1c9208d` | 2026-04-11 | `pyproject.toml`: `0.1.0 -> 0.2.0` |
| 0.3.0 | `d9ac9a7` | 2026-04-12 | `pyproject.toml`: `0.2.0 -> 0.3.0`; later commit `50adb35` adds `package.json` with `0.3.0` |

## 0.1.0 (Initial Baseline)

### Position

- Start of repository (`82235e7`, 2026-04-08).
- Canonical section exists in changelog: `## [0.1.0] - Initial Release`.

### Key Capabilities

- Core query engine and message/tool abstractions.
- OpenAI-compatible client.
- File tools and bash tool.
- CLI + Textual TUI baseline.
- Basic tests.

### Representative Commits (0.1.0 era)

- `82235e7` Initial commit.
- `1b3238f` Migrate OpenAI client from `httpx` to official SDK.
- `5665a51` Add TUI session persistence/resume.

## 0.2.0 (gRPC Architecture Phase)

### Position

- Version bump at `1c9208d` (2026-04-11):
  - `version = "0.1.0" -> "0.2.0"`
  - Description updated to include gRPC support.

### Core Changes vs 0.1.0

- Introduced gRPC client/server split and proto definitions.
- Added gRPC runtime dependencies (`grpcio`, `grpcio-tools`, `protobuf`).
- Added dedicated scripts/entry points for server/client (`cc-server`, `cc-client`).
- Continued TUI/internal refactors around streaming and tool rendering.

### Representative Commits (0.2.x window)

- `1c9208d` Implement gRPC client and server.
- `39eaae5` Migrate to pure gRPC frontend/backend architecture.
- `721de65` Add web server integration during gRPC phase.
- `c8c561f` Web frontend iteration (Vue 3 replacement).

## 0.3.0 (HTTP/FastAPI Architecture Phase)

### Position

- Version bump at `d9ac9a7` (2026-04-12):
  - `version = "0.2.0" -> "0.3.0"`
  - Description changed to FastAPI backend.
- Later `50adb35` keeps `0.3.0` while introducing `cc_code` package rename and `package.json` (`0.3.0`).

### Core Changes vs 0.2.0

- Shifted from gRPC runtime to HTTP/FastAPI stack.
- Removed gRPC dependencies from project runtime.
- Added/solidified API service path (`cc-api`) and HTTP client flow.
- Added and evolved web frontend and runtime alignment docs.
- Entered feature-rich TUI phase: rewind/snapshot, settings migration (`settings.json`), model switching, autocomplete, transcript and markdown performance work.

### Representative Commits (0.3.0 window)

- `d9ac9a7` Align runtime/docs with HTTP API stack and bump to `0.3.0`.
- `02c4c7a` Add git-based rewind/revert snapshot capability.
- `ba7f8e5` Migrate configuration to unified `settings.json`.
- `26d2b02` Add real-time model switching.
- `50adb35` Rename package to `cc_code` and add build/package configs (still `0.3.0`).

## Notes After 0.3.0

- First explicit tags start from `v0.3.1` (`56b0428`) onward.
- Existing tags in repository: `v0.3.1`, `v0.3.2`, `v0.3.3`, `v0.3.4`, `v0.3.5`, `v0.3.6`.
