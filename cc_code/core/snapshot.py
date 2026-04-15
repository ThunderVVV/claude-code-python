"""Snapshot system for file revert mechanism - aligned with OpenCode snapshot/index.ts

This module implements an independent Git-based snapshot system that:
- Uses a separate Git repository to manage file snapshots
- Creates tree objects (not commits) for lightweight versioning
- Supports non-Git projects
- Tracks file changes during tool execution
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_BASE_DIR = Path.home() / ".cc-py" / "snapshot"
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB - skip files larger than this

DEFAULT_TRACK_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".php",
    ".swift",
    ".vue",
    ".svelte",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".sh",
    ".bash",
    ".sql",
    ".md",
    "Dockerfile",
    "Makefile",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "package.json",
}


def build_snapshot_project_id(
    working_directory: str,
    session_id: Optional[str] = None,
) -> str:
    """Compute snapshot project ID.

    Legacy format uses only working_directory. Session-scoped format includes
    session_id to isolate snapshot repositories across sessions.
    """
    normalized_cwd = os.path.abspath(working_directory)
    if session_id:
        seed = f"{normalized_cwd}::session::{session_id}"
    else:
        seed = normalized_cwd
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


@dataclass
class Patch:
    """Represents a file change patch"""

    hash: str  # Git tree hash after changes
    prev_hash: str = ""  # Git tree hash before changes
    files: List[str] = field(default_factory=list)  # Absolute paths of changed files


@dataclass
class DiffSummary:
    """Summary of file differences"""

    additions: int = 0
    deletions: int = 0
    files: int = 0
    file_paths: Set[str] = field(default_factory=set)


class SnapshotManager:
    """Manages independent Git snapshots for file tracking.

    Each project gets its own snapshot repository under:
    ~/.cc-py/snapshot/{project_hash}/

    The snapshot repo is independent from the user's project Git repo.
    """

    def __init__(self, working_directory: str, project_id: Optional[str] = None):
        self.working_directory = os.path.abspath(working_directory)
        self.project_id = project_id or build_snapshot_project_id(self.working_directory)
        self.snapshot_dir = DEFAULT_SNAPSHOT_BASE_DIR / self.project_id
        self.gitdir = self.snapshot_dir / "git"
        self._initialized = False
        self._lock = asyncio.Lock()

    def _compute_project_id(self) -> str:
        """Compute a unique project ID from working directory (legacy behavior)."""
        return build_snapshot_project_id(self.working_directory)

    def _run_git(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        check: bool = False,
        input: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        """Run a git command with the snapshot repo configuration"""
        git_args = [
            "git",
            "--git-dir",
            str(self.gitdir),
            "--work-tree",
            self.working_directory,
        ] + args

        env = os.environ.copy()
        env["GIT_DIR"] = str(self.gitdir)
        env["GIT_WORK_TREE"] = self.working_directory

        result = subprocess.run(
            git_args,
            cwd=cwd or self.working_directory,
            capture_output=True,
            text=True,
            env=env,
            input=input,
        )
        if check and result.returncode != 0:
            logger.warning(f"Git command failed: {' '.join(git_args)}\n{result.stderr}")
        return result

    def _ensure_initialized(self) -> None:
        """Initialize the snapshot repository if needed"""
        if self._initialized:
            return

        if not self.gitdir.exists():
            self.gitdir.mkdir(parents=True, exist_ok=True)

            self._run_git(["init"])
            self._run_git(["config", "core.autocrlf", "false"])
            self._run_git(["config", "core.longpaths", "true"])
            self._run_git(["config", "core.symlinks", "true"])
            self._run_git(["config", "core.fsmonitor", "false"])

            logger.info(f"Initialized snapshot repo at {self.gitdir}")

        self._setup_excludes()

        self._initialized = True

    def _setup_excludes(self) -> None:
        """Setup exclude rules from user's .gitignore"""
        exclude_file = self.gitdir / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)

        user_gitignore = Path(self.working_directory) / ".gitignore"
        content = ""

        if user_gitignore.exists():
            try:
                content = user_gitignore.read_text(encoding="utf-8")
            except Exception:
                pass

        exclude_file.write_text(content, encoding="utf-8")

    def _get_changed_files(self) -> List[str]:
        """Get list of changed files (modified and untracked)"""
        self._ensure_initialized()

        result = self._run_git(["diff-files", "--name-only", "-z", "--", "."])
        tracked = [f for f in result.stdout.split("\0") if f]

        result = self._run_git(
            ["ls-files", "--others", "--exclude-standard", "-z", "--", "."]
        )
        untracked = [f for f in result.stdout.split("\0") if f]

        all_files = list(set(tracked + untracked))
        return [os.path.join(self.working_directory, f) for f in all_files]

    def _filter_ignored_files(self, files: List[str]) -> List[str]:
        """Filter files based on gitignore or default track extensions.

        First try git check-ignore (uses .gitignore via exclude file).
        If no gitignore, fallback to tracking common code files only.
        """
        if not files:
            return []

        rel_paths = [os.path.relpath(f, self.working_directory) for f in files]

        result = self._run_git(
            ["check-ignore", "--"] + rel_paths,
        )

        if result.returncode == 0 and result.stdout.strip():
            ignored = set(result.stdout.strip().split("\n"))
            filtered = [f for f, rel in zip(files, rel_paths) if rel not in ignored]
            if filtered:
                return filtered

        result = []
        for f in files:
            basename = os.path.basename(f)
            ext = os.path.splitext(f)[1].lower()

            if basename in DEFAULT_TRACK_EXTENSIONS or ext in DEFAULT_TRACK_EXTENSIONS:
                result.append(f)

        return result

    def _filter_large_files(self, files: List[str]) -> List[str]:
        """Filter out files larger than MAX_FILE_SIZE"""
        result = []
        for f in files:
            try:
                if os.path.getsize(f) <= MAX_FILE_SIZE:
                    result.append(f)
            except OSError:
                pass
        return result

    def _sync_large_files_to_gitignore(self, large_files: List[str]) -> None:
        """Add large files to a sparse checkout exclude list"""
        if not large_files:
            return

        sparse_file = self.gitdir / "info" / "sparse-checkout"
        sparse_file.parent.mkdir(parents=True, exist_ok=True)

        existing = set()
        if sparse_file.exists():
            existing = set(sparse_file.read_text().splitlines())

        rel_paths = [os.path.relpath(f, self.working_directory) for f in large_files]
        for rel in rel_paths:
            existing.add(f"!/{rel}")

        sparse_file.write_text("\n".join(sorted(existing)) + "\n")

    def track(self) -> str:
        """Create a snapshot of the current file state.

        Returns the git tree hash of the snapshot.
        """
        self._ensure_initialized()

        changed_files = self._get_changed_files()
        changed_files = self._filter_ignored_files(changed_files)

        # Safely find large files (skip deleted files)
        large_files = []
        for f in changed_files:
            try:
                if os.path.getsize(f) > MAX_FILE_SIZE:
                    large_files.append(f)
            except OSError:
                pass

        changed_files = self._filter_large_files(changed_files)

        if large_files:
            self._sync_large_files_to_gitignore(large_files)

        if changed_files:
            rel_paths = [
                os.path.relpath(f, self.working_directory) for f in changed_files
            ]
            self._run_git(["add", "--sparse", "--"] + rel_paths)

        result = self._run_git(["write-tree"])
        tree_hash = result.stdout.strip()

        if not tree_hash:
            empty_result = self._run_git(["mktree"], input="")
            tree_hash = empty_result.stdout.strip()

        logger.debug(f"Created snapshot: {tree_hash[:8]} ({len(changed_files)} files)")
        return tree_hash

    def patch(self, prev_hash: str) -> Patch:
        """Compute the patch between prev_hash and current state.

        Returns a Patch containing the current tree hash, prev_hash, and list of changed files.
        """
        current_hash = self.track()

        if current_hash == prev_hash:
            return Patch(hash=current_hash, prev_hash=prev_hash, files=[])

        result = self._run_git(
            [
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                prev_hash,
                current_hash,
            ]
        )

        changed_rel = [f for f in result.stdout.strip().split("\n") if f]
        changed_files = [os.path.join(self.working_directory, f) for f in changed_rel]

        return Patch(hash=current_hash, prev_hash=prev_hash, files=changed_files)

    def restore(self, tree_hash: str) -> None:
        """Restore all files to the state in the given tree"""
        self._ensure_initialized()

        result = self._run_git(["checkout", tree_hash, "--", "."])
        if result.returncode != 0:
            logger.warning(
                f"Failed to restore snapshot {tree_hash[:8]}: {result.stderr}"
            )

        logger.info(f"Restored snapshot: {tree_hash[:8]}")

    def revert_files(self, patches: List[Patch]) -> None:
        """Revert files to their state as recorded in the patches.

        For each file in the patches, restore it to the version in the patch's hash.
        If a file doesn't exist in the snapshot, delete it.
        """
        self._ensure_initialized()

        ops: List[dict] = []
        seen: Set[str] = set()

        for patch in reversed(patches):
            for file_path in patch.files:
                if file_path in seen:
                    continue
                seen.add(file_path)
                rel_path = os.path.relpath(file_path, self.working_directory)
                ops.append(
                    {
                        "hash": patch.hash,
                        "file": file_path,
                        "rel": rel_path,
                    }
                )

        for op in ops:
            self._revert_single_file(op["hash"], op["file"], op["rel"])

    def _revert_single_file(
        self, tree_hash: str, file_path: str, rel_path: str
    ) -> None:
        """Revert a single file to the version in the given tree"""
        result = self._run_git(["checkout", tree_hash, "--", file_path])

        if result.returncode == 0:
            logger.debug(f"Reverted {rel_path} to {tree_hash[:8]}")
            return

        tree_result = self._run_git(["ls-tree", tree_hash, "--", rel_path])

        if tree_result.returncode == 0 and tree_result.stdout.strip():
            logger.warning(
                f"File {rel_path} exists in snapshot {tree_hash[:8]} but checkout failed"
            )
            return

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.debug(f"Deleted {rel_path} (not in snapshot {tree_hash[:8]})")
            except OSError as e:
                logger.warning(f"Failed to delete {rel_path}: {e}")

    def diff(self, tree_hash1: str, tree_hash2: Optional[str] = None) -> DiffSummary:
        """Compute diff summary between two trees (or tree and current state)"""
        if tree_hash2 is None:
            tree_hash2 = self.track()

        result = self._run_git(["diff-tree", "--numstat", tree_hash1, tree_hash2])

        additions = 0
        deletions = 0
        file_paths: Set[str] = set()

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                try:
                    add = int(parts[0]) if parts[0] != "-" else 0
                    delete = int(parts[1]) if parts[1] != "-" else 0
                    additions += add
                    deletions += delete
                    file_paths.add(parts[2])
                except ValueError:
                    pass

        return DiffSummary(
            additions=additions,
            deletions=deletions,
            files=len(file_paths),
            file_paths=file_paths,
        )


# Revert state models (previously in revert.py)


@dataclass
class RevertState:
    """State tracking for a revert operation"""

    message_id: str  # Message ID where revert started
    part_id: Optional[str] = None  # Specific part ID (if reverting partial message)
    snapshot: Optional[str] = None  # Snapshot hash before revert (for unrevert)
    diff: Optional[DiffSummary] = None  # Diff summary of reverted changes


@dataclass
class RevertResult:
    """Result of a revert or unrevert operation"""

    success: bool
    message: str
    revert_state: Optional[RevertState] = None
    summary: Optional[DiffSummary] = None
