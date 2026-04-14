"""Ripgrep integration for Python - aligned with TypeScript version"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


VCS_DIRECTORIES_TO_EXCLUDE = [
    ".git",
    ".svn",
    ".hg",
    ".bzr",
    ".jj",
    ".sl",
]

DEFAULT_HEAD_LIMIT = 250
MAX_BUFFER_SIZE = 20 * 1024 * 1024


class RipgrepTimeoutError(Exception):
    """Custom error for ripgrep timeouts"""

    def __init__(self, message: str, partial_results: List[str]):
        super().__init__(message)
        self.partial_results = partial_results


def _get_ripgrep_path() -> Tuple[str, List[str]]:
    """Get ripgrep path and args - default to system rg"""
    env_use_builtin = os.environ.get("USE_BUILTIN_RIPGREP")
    user_wants_builtin = env_use_builtin is not None and env_use_builtin.lower() in (
        "1",
        "true",
        "yes",
    )

    if not user_wants_builtin:
        try:
            result = subprocess.run(
                ["which", "rg"], capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                return ("rg", [])
        except Exception:
            pass

    project_root = Path(__file__).parent.parent.parent
    vendor_dir = project_root / "vendor" / "ripgrep"

    if not vendor_dir.exists():
        return ("rg", [])

    system = platform.system().lower()
    arch = platform.machine().lower()

    if arch == "x86_64":
        arch = "x86_64"
    elif arch == "arm64" or arch == "aarch64":
        arch = "aarch64"

    if system == "windows":
        rg_path = vendor_dir / f"{arch}-win32" / "rg.exe"
    elif system == "darwin":
        rg_path = vendor_dir / f"{arch}-apple-darwin" / "rg"
    else:
        rg_path = vendor_dir / f"{arch}-unknown-linux-gnu" / "rg"

    if rg_path.exists():
        return (str(rg_path), [])

    return ("rg", [])


def ripgrep_command() -> Tuple[str, List[str]]:
    """Get ripgrep command and base args"""
    return _get_ripgrep_path()


def apply_head_limit(
    items: List[str], limit: Optional[int], offset: int = 0
) -> Tuple[List[str], Optional[int]]:
    """Apply head limit to results - aligned with TypeScript version"""
    if limit == 0:
        return (items[offset:], None)

    effective_limit = limit or DEFAULT_HEAD_LIMIT
    sliced = items[offset : offset + effective_limit]
    was_truncated = len(items) - offset > effective_limit

    return (sliced, effective_limit if was_truncated else None)


def rip_grep(args: List[str], target: str, timeout: Optional[int] = None) -> List[str]:
    """Run ripgrep and return results - aligned with TypeScript version"""
    rg_path, rg_args = ripgrep_command()

    full_args = rg_args + args + [target]

    if timeout is None:
        timeout = 60000 if "wsl" in platform.release().lower() else 20000

    try:
        result = subprocess.run(
            [rg_path] + full_args,
            capture_output=True,
            text=True,
            timeout=timeout / 1000,
        )

        if result.returncode == 0 or result.returncode == 1:
            lines = result.stdout.strip().split("\n")
            lines = [line.rstrip("\r") for line in lines if line]
            return lines

        stderr = result.stderr.strip()
        if result.returncode == 2:
            return []

        if "EAGAIN" in stderr or "Resource temporarily unavailable" in stderr:
            return []

        return []

    except subprocess.TimeoutExpired:
        raise RipgrepTimeoutError(
            f"Ripgrep search timed out after {timeout / 1000} seconds. "
            f"The search may have matched files but did not complete in time. "
            f"Try searching a more specific path or pattern.",
            [],
        )
    except FileNotFoundError:
        return []
    except Exception:
        return []
