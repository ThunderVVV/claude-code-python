"""Instruction loading service - loads CLAUDE.md, AGENTS.md and custom instruction files.

This module implements the instruction loading mechanism similar to opencode's instruction.ts,
automatically finding, reading, and injecting project-level and global-level configuration
instruction files into AI session system prompts.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Default instruction files to search for
DEFAULT_INSTRUCTION_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "CONTEXT.md",
]

# Environment variable names
ENV_CONFIG_DIR = "OPENCODE_CONFIG_DIR"
ENV_DISABLE_CLAUDE_PROMPT = "OPENCODE_DISABLE_CC_CODE_PROMPT"
ENV_DISABLE_PROJECT_CONFIG = "OPENCODE_DISABLE_PROJECT_CONFIG"


@dataclass
class InstructionConfig:
    """Configuration for instruction loading."""

    # Files to search for (in order of priority)
    files: List[str] = field(default_factory=lambda: list(DEFAULT_INSTRUCTION_FILES))

    # Whether to disable CLAUDE.md loading
    disable_claude_prompt: bool = False

    # Whether to disable project-level config loading
    disable_project_config: bool = False

    # Custom config directory (overrides default)
    config_dir: Optional[str] = None

    # Custom instruction files/URLs from config
    custom_instructions: List[str] = field(default_factory=list)

    # Concurrency limits
    max_concurrent_files: int = 8
    max_concurrent_urls: int = 4

    # URL fetch timeout in seconds
    url_timeout: float = 5.0

    @classmethod
    def from_env(cls) -> "InstructionConfig":
        """Create configuration from environment variables."""
        disable_claude_prompt = os.environ.get(
            ENV_DISABLE_CLAUDE_PROMPT, ""
        ).lower() in (
            "1",
            "true",
            "yes",
        )
        disable_project_config = os.environ.get(
            ENV_DISABLE_PROJECT_CONFIG, ""
        ).lower() in (
            "1",
            "true",
            "yes",
        )
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


@dataclass
class LoadedInstruction:
    """Represents a loaded instruction file."""

    path: str
    content: str

    def format(self) -> str:
        """Format instruction for inclusion in system prompt."""
        return f"Instructions from: {self.path}\n{self.content}"


def extract_loaded_paths_from_messages(messages: list) -> Set[str]:
    """Extract paths of already-loaded instruction files from messages.

    This implements the same logic as TypeScript's extract() function,
    looking for Read tool results that have a 'loaded' metadata field.
    """
    paths = set()
    for msg in messages:
        # Check for tool result content with loaded metadata
        for content in getattr(msg, "content", []):
            if hasattr(content, "type") and content.type == "tool_result":
                # Check if this is a Read tool result with loaded metadata
                metadata = getattr(content, "metadata", None)
                if metadata and isinstance(metadata, dict):
                    loaded = metadata.get("loaded", [])
                    if isinstance(loaded, list):
                        for p in loaded:
                            if isinstance(p, str):
                                paths.add(os.path.abspath(p))
    return paths


class InstructionService:
    """Service for loading and managing instruction files.

    This service handles:
    - Project-level instruction file discovery (searching upward from cwd)
    - Global-level instruction file loading
    - Custom instruction file/URL loading from config
    - Deduplication of loaded instructions (per-message tracking)
    - Nearby instruction loading when reading files
    - Concurrent file/URL reading
    """

    def __init__(self, config: Optional[InstructionConfig] = None):
        self.config = config or InstructionConfig.from_env()
        self._loaded_paths: Set[str] = set()
        # Per-message claims tracking for deduplication (like TypeScript's claims Map)
        # Maps message_id -> Set of loaded file paths
        self._claims: dict[str, Set[str]] = {}
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for URL fetching."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.config.url_timeout)
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

    def _get_global_config_dir(self) -> Optional[str]:
        """Get the global configuration directory."""
        # Check for XDG config home
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return os.path.join(xdg_config, "opencode")

        # Default to ~/.config/opencode
        home = os.path.expanduser("~")
        return os.path.join(home, ".config", "opencode")

    def _find_upward(
        self, filename: str, start_dir: str, stop_dir: Optional[str] = None
    ) -> Optional[str]:
        """Search upward from start_dir for a file, stopping at stop_dir or filesystem root.

        Returns the first match found, or None if not found.
        """
        current = os.path.abspath(start_dir)
        stop = os.path.abspath(stop_dir) if stop_dir else None

        while True:
            filepath = os.path.join(current, filename)
            if os.path.isfile(filepath):
                return filepath

            # Check if we've reached the stop directory
            if stop and current == stop:
                break

            # Check if we've reached the filesystem root
            parent = os.path.dirname(current)
            if parent == current:
                break

            current = parent

        return None

    def _find_all_upward(
        self, filename: str, start_dir: str, stop_dir: Optional[str] = None
    ) -> List[str]:
        """Search upward from start_dir for a file, returning all matches.

        This finds files from the start_dir upward to stop_dir or root.
        """
        matches = []
        current = os.path.abspath(start_dir)
        stop = os.path.abspath(stop_dir) if stop_dir else None

        while True:
            filepath = os.path.join(current, filename)
            if os.path.isfile(filepath):
                matches.append(filepath)

            # Check if we've reached the stop directory
            if stop and current == stop:
                break

            # Check if we've reached the filesystem root
            parent = os.path.dirname(current)
            if parent == current:
                break

            current = parent

        return matches

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

    def _resolve_path(self, raw: str, working_directory: str) -> Optional[str]:
        """Resolve a path string to an absolute path.

        Handles:
        - Absolute paths
        - Paths starting with ~ (home directory)
        - Relative paths (searched upward from working_directory)
        """
        if raw.startswith("~/"):
            return os.path.join(os.path.expanduser("~"), raw[2:])
        elif os.path.isabs(raw):
            return raw
        else:
            # Relative path - search upward
            result = self._find_upward(raw, working_directory)
            return result

    async def get_system_paths(
        self,
        working_directory: str,
        stop_dir: Optional[str] = None,
    ) -> Set[str]:
        """Collect all instruction file paths that should be loaded.

        This implements the same logic as opencode's systemPaths():
        1. Project-level: Search upward from working_directory for FILES
        2. Global-level: Check globalFiles() paths
        3. Config-level: Resolve custom instructions from config

        The first project-level match wins (no stacking from ancestors).
        """
        paths: Set[str] = set()

        # 1. Project-level search (first match wins)
        if not self.config.disable_project_config:
            for filename in self.config.files:
                match = self._find_upward(filename, working_directory, stop_dir)
                if match:
                    paths.add(os.path.abspath(match))
                    break  # First match wins, don't stack from ancestors

        # 2. Global-level files
        for global_file in self._get_global_files():
            if os.path.isfile(global_file):
                paths.add(os.path.abspath(global_file))
                break  # First match wins

        # 3. Custom instructions from config
        for raw in self.config.custom_instructions:
            # Skip URLs here (they're handled separately)
            if self._is_url(raw):
                continue

            resolved = self._resolve_path(raw, working_directory)
            if resolved and os.path.isfile(resolved):
                paths.add(os.path.abspath(resolved))

        return paths

    async def get_system_urls(self) -> List[str]:
        """Get all URL-based instructions from config."""
        return [raw for raw in self.config.custom_instructions if self._is_url(raw)]

    async def load_instructions(
        self,
        working_directory: str,
        stop_dir: Optional[str] = None,
    ) -> List[LoadedInstruction]:
        """Load all instruction files and return their contents.

        This is the main entry point for loading instructions.
        It concurrently reads local files and fetches URLs.
        """
        paths = await self.get_system_paths(working_directory, stop_dir)
        urls = await self.get_system_urls()

        instructions: List[LoadedInstruction] = []

        # Load local files concurrently
        if paths:
            semaphore = asyncio.Semaphore(self.config.max_concurrent_files)

            async def read_with_semaphore(filepath: str) -> tuple[str, str]:
                async with semaphore:
                    content = await self._read_file(filepath)
                    return (filepath, content)

            tasks = [read_with_semaphore(p) for p in paths]
            results = await asyncio.gather(*tasks)

            for filepath, content in results:
                if content:
                    instructions.append(
                        LoadedInstruction(path=filepath, content=content)
                    )

        # Fetch URLs concurrently
        if urls:
            semaphore = asyncio.Semaphore(self.config.max_concurrent_urls)

            async def fetch_with_semaphore(url: str) -> tuple[str, str]:
                async with semaphore:
                    content = await self._fetch_url(url)
                    return (url, content)

            tasks = [fetch_with_semaphore(u) for u in urls]
            results = await asyncio.gather(*tasks)

            for url, content in results:
                if content:
                    instructions.append(LoadedInstruction(path=url, content=content))

        return instructions

    async def get_system_instructions(
        self,
        working_directory: str,
        stop_dir: Optional[str] = None,
    ) -> List[str]:
        """Get formatted system instruction strings for injection into system prompt.

        Returns a list of formatted instruction strings like:
        "Instructions from: /path/to/CLAUDE.md\n<content>"
        """
        instructions = await self.load_instructions(working_directory, stop_dir)
        return [inst.format() for inst in instructions]

    def find_in_directory(self, directory: str) -> Optional[str]:
        """Find the first instruction file in a specific directory.

        Used for loading nearby instructions when reading files.
        """
        for filename in self.config.files:
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                return filepath
        return None

    def mark_loaded(self, filepath: str) -> None:
        """Mark a file as having been loaded (for deduplication)."""
        self._loaded_paths.add(os.path.abspath(filepath))

    def is_loaded(self, filepath: str) -> bool:
        """Check if a file has already been loaded."""
        return os.path.abspath(filepath) in self._loaded_paths

    def clear_loaded(self) -> None:
        """Clear the set of loaded paths."""
        self._loaded_paths.clear()

    def clear_claims(self, message_id: str) -> None:
        """Clear claims for a specific message.

        Called when starting a new message to reset per-message tracking.
        """
        if message_id in self._claims:
            del self._claims[message_id]

    def _get_claims(self, message_id: str) -> Set[str]:
        """Get or create claims set for a message."""
        if message_id not in self._claims:
            self._claims[message_id] = set()
        return self._claims[message_id]

    async def resolve_nearby_instructions(
        self,
        messages: list,
        filepath: str,
        message_id: str,
        project_root: str,
    ) -> List[LoadedInstruction]:
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
            List of newly loaded nearby instructions
        """
        # Get system paths (already loaded at startup)
        system_paths = await self.get_system_paths(project_root)

        # Get paths already loaded from previous messages
        already_loaded = extract_loaded_paths_from_messages(messages)

        results: List[LoadedInstruction] = []
        claims = self._get_claims(message_id)

        target = os.path.abspath(filepath)
        root = os.path.abspath(project_root)
        current = os.path.dirname(target)

        # Walk upward from the file being read
        while current.startswith(root) and current != root:
            found = self.find_in_directory(current)
            if found:
                found_abs = os.path.abspath(found)
                # Skip if: same as target, already in system paths, already loaded, or claimed this message
                if (
                    found_abs != target
                    and found_abs not in system_paths
                    and found_abs not in already_loaded
                    and found_abs not in claims
                ):
                    # Mark as claimed for this message
                    claims.add(found_abs)

                    # Read the file
                    content = await self._read_file(found_abs)
                    if content:
                        results.append(
                            LoadedInstruction(path=found_abs, content=content)
                        )
                        logger.debug(f"Loaded nearby instruction: {found_abs}")

            # Move to parent directory
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        return results


# Singleton instance for convenience
_default_service: Optional[InstructionService] = None


def get_instruction_service(
    config: Optional[InstructionConfig] = None,
) -> InstructionService:
    """Get or create the default instruction service instance."""
    global _default_service
    if _default_service is None:
        _default_service = InstructionService(config)
    return _default_service


async def load_system_instructions(
    working_directory: str,
    config: Optional[InstructionConfig] = None,
) -> List[str]:
    """Convenience function to load system instructions.

    This is the simplest way to get instruction strings for the system prompt.
    """
    service = get_instruction_service(config)
    return await service.get_system_instructions(working_directory)
