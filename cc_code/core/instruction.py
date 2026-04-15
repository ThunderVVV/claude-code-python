"""Instruction loading service - loads CLAUDE.md, AGENTS.md and custom instruction files.

This module implements the instruction loading mechanism similar to opencode's instruction.ts,
automatically finding, reading, and injecting project-level and global-level configuration
instruction files into AI session system prompts.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Set
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Default instruction files to search for
DEFAULT_INSTRUCTION_FILES = ["AGENTS.md", "CLAUDE.md", "CONTEXT.md"]

# Environment variable names
ENV_CONFIG_DIR = "OPENCODE_CONFIG_DIR"
ENV_DISABLE_CLAUDE_PROMPT = "OPENCODE_DISABLE_CC_CODE_PROMPT"
ENV_DISABLE_PROJECT_CONFIG = "OPENCODE_DISABLE_PROJECT_CONFIG"


class InstructionConfig:
    """Configuration for instruction loading."""

    def __init__(
        self,
        files: Optional[List[str]] = None,
        disable_claude_prompt: bool = False,
        disable_project_config: bool = False,
        config_dir: Optional[str] = None,
        custom_instructions: Optional[List[str]] = None,
    ):
        self.files = files or list(DEFAULT_INSTRUCTION_FILES)
        self.disable_claude_prompt = disable_claude_prompt
        self.disable_project_config = disable_project_config
        self.config_dir = config_dir
        self.custom_instructions = custom_instructions or []

    @classmethod
    def from_env(cls) -> "InstructionConfig":
        """Create configuration from environment variables."""
        disable_claude_prompt = os.environ.get(
            ENV_DISABLE_CLAUDE_PROMPT, ""
        ).lower() in ("1", "true", "yes")
        disable_project_config = os.environ.get(
            ENV_DISABLE_PROJECT_CONFIG, ""
        ).lower() in ("1", "true", "yes")
        config_dir = os.environ.get(ENV_CONFIG_DIR)

        files = list(DEFAULT_INSTRUCTION_FILES)
        if disable_claude_prompt and "CLAUDE.md" in files:
            files.remove("CLAUDE.md")

        return cls(
            files=files,
            disable_claude_prompt=disable_claude_prompt,
            disable_project_config=disable_project_config,
            config_dir=config_dir,
        )


class InstructionService:
    """Service for loading and managing instruction files."""

    def __init__(self, config: Optional[InstructionConfig] = None):
        self.config = config or InstructionConfig.from_env()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for URL fetching."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "InstructionService":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _find_upward(
        self, filename: str, start_dir: str, stop_dir: Optional[str] = None
    ) -> Optional[str]:
        """Search upward from start_dir for a file, stopping at stop_dir or filesystem root."""
        current = os.path.abspath(start_dir)
        stop = os.path.abspath(stop_dir) if stop_dir else None

        while True:
            filepath = os.path.join(current, filename)
            if os.path.isfile(filepath):
                return filepath

            if stop and current == stop:
                break

            parent = os.path.dirname(current)
            if parent == current:
                break

            current = parent

        return None

    async def _read_file(self, filepath: str) -> str:
        """Read a local file, returning empty string on error."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.debug(f"Failed to read instruction file {filepath}: {e}")
            return ""

    async def _fetch_url(self, url: str) -> str:
        """Fetch content from a URL, returning empty string on error."""
        try:
            client = await self._get_http_client()
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.debug(f"Failed to fetch instruction URL {url}: {e}")
            return ""

    def _is_url(self, path: str) -> bool:
        """Check if a path is a URL."""
        try:
            result = urlparse(path)
            return result.scheme in ("http", "https")
        except Exception:
            return False

    def _get_global_config_dir(self) -> Optional[str]:
        """Get the global configuration directory."""
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return os.path.join(xdg_config, "opencode")

        home = os.path.expanduser("~")
        return os.path.join(home, ".config", "opencode")

    def _get_global_files(self) -> List[str]:
        """Get list of global instruction file paths."""
        files = []

        # OPENCODE_CONFIG_DIR takes priority
        if self.config.config_dir:
            files.append(os.path.join(self.config.config_dir, "AGENTS.md"))

        # Default global config directory
        global_config_dir = self._get_global_config_dir()
        if global_config_dir:
            files.append(os.path.join(global_config_dir, "AGENTS.md"))

        # User's home .claude directory for CLAUDE.md
        if not self.config.disable_claude_prompt:
            home = os.path.expanduser("~")
            files.append(os.path.join(home, ".claude", "CLAUDE.md"))

        return files

    async def get_system_instructions(
        self,
        working_directory: str,
        stop_dir: Optional[str] = None,
    ) -> List[str]:
        """Load all instruction files and return formatted strings for system prompt.

        This is the main entry point for loading instructions.
        Returns a list of formatted instruction strings like:
        "Instructions from: /path/to/CLAUDE.md\n<content>"
        """
        instructions = []

        # 1. Project-level search (first match wins)
        if not self.config.disable_project_config:
            for filename in self.config.files:
                match = self._find_upward(filename, working_directory, stop_dir)
                if match:
                    content = await self._read_file(match)
                    if content:
                        instructions.append(f"Instructions from: {match}\n{content}")
                    break

        # 2. Global-level files (first match wins)
        for global_file in self._get_global_files():
            if os.path.isfile(global_file):
                content = await self._read_file(global_file)
                if content:
                    instructions.append(f"Instructions from: {global_file}\n{content}")
                break

        # 3. Custom instructions from config
        for raw in self.config.custom_instructions:
            if self._is_url(raw):
                content = await self._fetch_url(raw)
                if content:
                    instructions.append(f"Instructions from: {raw}\n{content}")
            else:
                # Resolve path
                if raw.startswith("~/"):
                    resolved = os.path.join(os.path.expanduser("~"), raw[2:])
                elif os.path.isabs(raw):
                    resolved = raw
                else:
                    # Relative path - search upward
                    resolved = self._find_upward(raw, working_directory, stop_dir)

                if resolved and os.path.isfile(resolved):
                    content = await self._read_file(resolved)
                    if content:
                        instructions.append(f"Instructions from: {resolved}\n{content}")

        return instructions

    def find_in_directory(self, directory: str) -> Optional[str]:
        """Find the first instruction file in a specific directory."""
        for filename in self.config.files:
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                return filepath
        return None

    async def resolve_nearby_instructions(
        self,
        messages: list,
        filepath: str,
        message_id: str,
        project_root: str,
    ) -> List[str]:
        """Load instruction files near the file being read.

        This implements the TypeScript resolve() function that walks upward
        from the file being read and attaches nearby instruction files
        once per message.

        Args:
            messages: Current conversation messages (to check what's already loaded)
            filepath: The file being read
            message_id: ID of the current assistant message
            project_root: Project root directory

        Returns:
            List of formatted nearby instruction strings
        """
        # Get paths already loaded from previous messages
        already_loaded = extract_loaded_paths_from_messages(messages)

        results = []
        target = os.path.abspath(filepath)
        root = os.path.abspath(project_root)
        current = os.path.dirname(target)

        # Walk upward from the file being read
        while current.startswith(root) and current != root:
            found = self.find_in_directory(current)
            if found:
                found_abs = os.path.abspath(found)
                # Skip if already loaded or same as target
                if found_abs != target and found_abs not in already_loaded:
                    content = await self._read_file(found_abs)
                    if content:
                        results.append(f"Instructions from: {found_abs}\n{content}")
                        logger.debug(f"Loaded nearby instruction: {found_abs}")

            # Move to parent directory
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        return results


def extract_loaded_paths_from_messages(messages: list) -> Set[str]:
    """Extract paths of already-loaded instruction files from messages.

    This implements the same logic as TypeScript's extract() function,
    looking for Read tool results that have a 'loaded' metadata field.
    """
    paths = set()
    for msg in messages:
        for content in getattr(msg, "content", []):
            if hasattr(content, "type") and content.type == "tool_result":
                metadata = getattr(content, "metadata", None)
                if metadata and isinstance(metadata, dict):
                    loaded = metadata.get("loaded", [])
                    if isinstance(loaded, list):
                        for p in loaded:
                            if isinstance(p, str):
                                paths.add(os.path.abspath(p))
    return paths


async def load_system_instructions(
    working_directory: str,
    config: Optional[InstructionConfig] = None,
) -> List[str]:
    """Load system instructions for the given working directory.

    This is the main entry point for loading instructions.
    """
    service = InstructionService(config)
    return await service.get_system_instructions(working_directory)
