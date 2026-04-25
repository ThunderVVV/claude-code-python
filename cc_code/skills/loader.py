"""Skills loader - aligned with TypeScript src/skills/loadSkillsDir.ts

Loads skills from:
- ~/.claude/skills/ (user settings)
- .claude/skills/ (project settings, walking up to home)
- Managed/policy path
- Bundled skills (shipped with app)
- Dynamic discovery from file paths
- Legacy .claude/commands/ (for backwards compat)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

import yaml

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Type alias for the source of a skill
LoadedFrom = str  # 'skills' | 'plugin' | 'bundled' | 'commands_DEPRECATED' | 'managed' | 'mcp'

# Skill listing budget: 1% of context window in characters
SKILL_BUDGET_CONTEXT_PERCENT = 0.01
CHARS_PER_TOKEN = 4
DEFAULT_CHAR_BUDGET = 8_000
MAX_LISTING_DESC_CHARS = 250


def _get_claude_config_home() -> str:
    """Get the Claude config home directory."""
    return os.path.expanduser("~/.claude")


def _get_managed_path() -> str:
    """Get the managed/policy path."""
    return os.path.expanduser("~/.claude")


def _get_project_dirs_up_to_home(subdir: str, cwd: str) -> List[str]:
    """Walk up from cwd to home, collecting .claude/subdir directories."""
    dirs = []
    current = os.path.abspath(cwd)
    home = os.path.expanduser("~")

    while True:
        candidate = os.path.join(current, ".claude", subdir)
        if os.path.isdir(candidate):
            dirs.append(candidate)
        if current == home or current == "/" or not current:
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    return dirs


def _parse_frontmatter(content: str, file_path: str = "") -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body_content).
    """
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content

    frontmatter_str = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()

    if not frontmatter_str:
        return {}, body

    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        logger.debug(f"Failed to parse frontmatter in {file_path}")
        return {}, body

    return frontmatter, body


def _extract_description_from_markdown(content: str, fallback_label: str = "Skill") -> str:
    """Extract a description from the first meaningful paragraph of markdown content."""
    lines = content.strip().split("\n")
    description_lines = []

    for line in lines:
        stripped = line.strip()
        # Skip headings, empty lines, horizontal rules
        if stripped.startswith("#") or not stripped or stripped in ("---", "***", "___"):
            if description_lines:
                break  # Stop after we've collected some description
            continue
        description_lines.append(stripped)
        if len(description_lines) >= 3:
            break

    if description_lines:
        return " ".join(description_lines)[:200]
    return f"{fallback_label} command"


def _parse_argument_names(args_field: Optional[Union[str, List[str]]]) -> List[str]:
    """Parse argument names from frontmatter."""
    if args_field is None:
        return []
    if isinstance(args_field, list):
        return [str(a) for a in args_field if a]
    if isinstance(args_field, str):
        return [a.strip() for a in args_field.split(",") if a.strip()]
    return []


def _parse_allowed_tools(tools_field: Any) -> List[str]:
    """Parse allowed-tools from frontmatter."""
    if tools_field is None:
        return []
    if isinstance(tools_field, str):
        return [t.strip() for t in tools_field.split(",") if t.strip()]
    if isinstance(tools_field, list):
        return [str(t) for t in tools_field if t]
    return []


def _parse_boolean(value: Any, default: bool = False) -> bool:
    """Parse a boolean frontmatter value."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1")
    if isinstance(value, (int, float)):
        return bool(value)
    return default


@dataclass
class SkillCommand:
    """Represents a loaded skill command - aligned with TypeScript Command type."""

    name: str
    description: str
    source: str  # 'projectSettings' | 'userSettings' | 'policySettings' | 'plugin' | 'bundled'
    loaded_from: LoadedFrom  # 'skills' | 'plugin' | 'bundled' | 'commands_DEPRECATED' | 'managed' | 'mcp'
    skill_root: Optional[str] = None  # Base directory for the skill
    markdown_content: str = ""
    display_name: Optional[str] = None
    allowed_tools: List[str] = field(default_factory=list)
    argument_hint: Optional[str] = None
    arg_names: Optional[List[str]] = None
    when_to_use: Optional[str] = None
    version: Optional[str] = None
    model: Optional[str] = None
    disable_model_invocation: bool = False
    user_invocable: bool = True
    context: Optional[str] = None  # 'inline' | 'fork'
    agent: Optional[str] = None
    effort: Optional[Any] = None
    paths: Optional[List[str]] = None
    hooks: Optional[dict] = None
    aliases: List[str] = field(default_factory=list)
    has_user_specified_description: bool = False
    is_enabled: bool = True
    is_hidden: bool = False
    content_length: int = 0

    @property
    def type(self) -> str:
        return "prompt"

    async def get_prompt_for_command(self, args: str, base_dir: Optional[str] = None) -> str:
        """Get the expanded prompt content for this skill."""
        content = self.markdown_content

        if base_dir or self.skill_root:
            directory = base_dir or self.skill_root or ""
            content = f"Base directory for this skill: {directory}\n\n{content}"

        # Substitute $ARGUMENTS or positional args
        if args:
            arg_parts = args.strip().split()
            if self.arg_names and len(self.arg_names) > 0:
                for i, arg_name in enumerate(self.arg_names):
                    if i < len(arg_parts):
                        placeholder = f"${arg_name.upper()}"
                        content = content.replace(placeholder, arg_parts[i])
                        # Also try $ARGUMENTS
                        if i == 0 and not self.arg_names:
                            content = content.replace("$ARGUMENTS", args.strip())

        content = content.replace("$ARGUMENTS", args.strip() if args else "")
        content = content.replace("${CLAUDE_SKILL_DIR}", directory if (base_dir or self.skill_root) else "")
        content = content.replace("${CLAUDE_SESSION_ID}", "")

        return content


# ---------------------------------------------------------------------------
# Skills Directory Loading
# ---------------------------------------------------------------------------

async def _load_skills_from_skills_dir(
    base_path: str,
    source: str,
) -> List[SkillCommand]:
    """Load skills from a /skills/ directory (skill-name/SKILL.md format).

    Args:
        base_path: Path to the skills directory
        source: Source identifier ('projectSettings', 'userSettings', 'policySettings')

    Returns:
        List of SkillCommand instances
    """
    if not os.path.isdir(base_path):
        return []

    skills = []

    try:
        entries = sorted(os.listdir(base_path))
    except OSError as e:
        logger.debug(f"Cannot read skills directory {base_path}: {e}")
        return []

    for entry_name in entries:
        entry_path = os.path.join(base_path, entry_name)

        # Only support directory format: skill-name/SKILL.md
        if not os.path.isdir(entry_path) and not os.path.islink(entry_path):
            continue

        skill_md_path = os.path.join(entry_path, "SKILL.md")
        if not os.path.isfile(skill_md_path):
            continue

        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
        except OSError as e:
            logger.debug(f"Failed to read {skill_md_path}: {e}")
            continue

        frontmatter, body = _parse_frontmatter(raw_content, skill_md_path)

        skill = _create_skill_from_frontmatter(
            skill_name=entry_name,
            frontmatter=frontmatter,
            markdown_content=body,
            source=source,
            loaded_from="skills",
            skill_root=entry_path,
        )
        skills.append(skill)

    return skills


async def _load_skills_from_commands_dir(cwd: str) -> List[SkillCommand]:
    """Load skills from legacy .claude/commands/ directories.

    Supports both SKILL.md (directory format) and .md file format.
    """
    skills = []
    commands_dirs = _get_project_dirs_up_to_home("commands", cwd)

    for commands_dir in commands_dirs:
        if not os.path.isdir(commands_dir):
            continue

        try:
            entries = sorted(os.listdir(commands_dir))
        except OSError:
            continue

        for entry_name in entries:
            entry_path = os.path.join(commands_dir, entry_name)

            if os.path.isdir(entry_path):
                # Directory format: dir_name/SKILL.md
                skill_md = os.path.join(entry_path, "SKILL.md")
                if os.path.isfile(skill_md):
                    try:
                        with open(skill_md, "r", encoding="utf-8") as f:
                            raw_content = f.read()
                    except OSError:
                        continue

                    frontmatter, body = _parse_frontmatter(raw_content, skill_md)
                    # Namespace from relative path
                    rel_path = os.path.relpath(entry_path, commands_dir)
                    namespace = rel_path.replace(os.sep, ":") if rel_path != "." else ""
                    skill_name = f"{namespace}:{entry_name}" if namespace else entry_name

                    skills.append(_create_skill_from_frontmatter(
                        skill_name=skill_name,
                        frontmatter=frontmatter,
                        markdown_content=body,
                        source="projectSettings",
                        loaded_from="commands_DEPRECATED",
                        skill_root=entry_path,
                        fallback_label="Custom command",
                    ))

            elif entry_name.endswith(".md"):
                # Single .md file format
                try:
                    with open(entry_path, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                except OSError:
                    continue

                frontmatter, body = _parse_frontmatter(raw_content, entry_path)
                base_name = entry_name[:-3]  # Remove .md
                rel_path = os.path.relpath(os.path.dirname(entry_path), commands_dir)
                namespace = rel_path.replace(os.sep, ":") if rel_path != "." else ""
                skill_name = f"{namespace}:{base_name}" if namespace else base_name

                skills.append(_create_skill_from_frontmatter(
                    skill_name=skill_name,
                    frontmatter=frontmatter,
                    markdown_content=body,
                    source="projectSettings",
                    loaded_from="commands_DEPRECATED",
                    fallback_label="Custom command",
                ))

    return skills


def _create_skill_from_frontmatter(
    skill_name: str,
    frontmatter: dict,
    markdown_content: str,
    source: str,
    loaded_from: LoadedFrom,
    skill_root: Optional[str] = None,
    fallback_label: str = "Skill",
) -> SkillCommand:
    """Create a SkillCommand from parsed frontmatter and content."""

    # Description: use frontmatter if available, otherwise extract from content
    fm_description = frontmatter.get("description")
    has_user_specified = fm_description is not None
    if fm_description is not None and isinstance(fm_description, str) and fm_description.strip():
        description = fm_description.strip()
    elif isinstance(fm_description, str):
        # Empty or whitespace-only string in frontmatter = user explicitly set it
        description = fm_description
    else:
        description = _extract_description_from_markdown(markdown_content, fallback_label)

    # Parse fields
    allowed_tools = _parse_allowed_tools(frontmatter.get("allowed-tools"))
    arg_names = _parse_argument_names(frontmatter.get("arguments"))
    when_to_use = frontmatter.get("when_to_use")
    model = frontmatter.get("model")
    if isinstance(model, str) and model.lower() == "inherit":
        model = None

    disable_model_invocation = _parse_boolean(frontmatter.get("disable-model-invocation"), False)
    user_invocable = _parse_boolean(frontmatter.get("user-invocable"), True)
    context = frontmatter.get("context")  # 'fork' or 'inline'

    # Parse paths for conditional skills
    paths_raw = frontmatter.get("paths")
    paths = None
    if paths_raw:
        if isinstance(paths_raw, str):
            paths = [p.strip() for p in paths_raw.split(",") if p.strip()]
        elif isinstance(paths_raw, list):
            paths = [str(p) for p in paths_raw if p]

    # Parse effort
    effort = frontmatter.get("effort")

    return SkillCommand(
        name=skill_name,
        description=description,
        source=source,
        loaded_from=loaded_from,
        skill_root=skill_root,
        markdown_content=markdown_content,
        display_name=frontmatter.get("name") if isinstance(frontmatter.get("name"), str) else None,
        allowed_tools=allowed_tools,
        argument_hint=frontmatter.get("argument-hint") if isinstance(frontmatter.get("argument-hint"), str) else None,
        arg_names=arg_names if arg_names else None,
        when_to_use=when_to_use,
        version=frontmatter.get("version") if isinstance(frontmatter.get("version"), str) else None,
        model=model,
        disable_model_invocation=disable_model_invocation,
        user_invocable=user_invocable,
        context=context,
        agent=frontmatter.get("agent") if isinstance(frontmatter.get("agent"), str) else None,
        effort=effort,
        paths=paths,
        hooks=frontmatter.get("hooks") if isinstance(frontmatter.get("hooks"), dict) else None,
        aliases=frontmatter.get("aliases", []) if isinstance(frontmatter.get("aliases", []), list) else [],
        has_user_specified_description=has_user_specified,
        is_hidden=not user_invocable,
        content_length=len(markdown_content),
    )


# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------

# Dynamically discovered skills
_dynamic_skill_dirs: set[str] = set()
_dynamic_skills: Dict[str, SkillCommand] = {}

# Conditional skills (with paths frontmatter)
_conditional_skills: Dict[str, SkillCommand] = {}
_activated_conditional_skill_names: set[str] = set()

# Cache
_cached_skill_dir_commands: Optional[List[SkillCommand]] = None
_cached_commands_dir_commands: Optional[List[SkillCommand]] = None


def clear_skill_caches() -> None:
    """Clear all skill caches."""
    global _cached_skill_dir_commands, _cached_commands_dir_commands
    _cached_skill_dir_commands = None
    _cached_commands_dir_commands = None
    _conditional_skills.clear()
    _activated_conditional_skill_names.clear()


async def load_skills_from_dir(cwd: str) -> List[SkillCommand]:
    """Load all skills from user, project, managed, and legacy commands directories.

    Args:
        cwd: Current working directory for project traversal
    """
    global _cached_skill_dir_commands

    if _cached_skill_dir_commands is not None:
        return _cached_skill_dir_commands

    user_skills_dir = os.path.join(_get_claude_config_home(), "skills")
    managed_skills_dir = os.path.join(_get_managed_path(), ".claude", "skills")
    project_skills_dirs = _get_project_dirs_up_to_home("skills", cwd)

    # Load from all sources
    managed_skills = await _load_skills_from_skills_dir(managed_skills_dir, "policySettings")
    user_skills = await _load_skills_from_skills_dir(user_skills_dir, "userSettings")

    project_skills = []
    for d in project_skills_dirs:
        project_skills.extend(await _load_skills_from_skills_dir(d, "projectSettings"))

    legacy_commands = await _load_skills_from_commands_dir(cwd)

    all_skills = managed_skills + user_skills + project_skills + legacy_commands

    # Deduplicate by name (first wins)
    seen = set()
    deduped = []
    for skill in all_skills:
        if skill.name not in seen:
            seen.add(skill.name)
            deduped.append(skill)

    # Separate conditional skills
    unconditional = []
    for skill in deduped:
        if skill.paths and len(skill.paths) > 0 and skill.name not in _activated_conditional_skill_names:
            _conditional_skills[skill.name] = skill
        else:
            unconditional.append(skill)

    _cached_skill_dir_commands = unconditional
    logger.debug(
        f"Loaded {len(unconditional)} skills from dirs "
        f"(managed={len(managed_skills)}, user={len(user_skills)}, "
        f"project={len(project_skills)}, legacy={len(legacy_commands)}, "
        f"conditional={len(_conditional_skills)})"
    )

    return unconditional


async def get_all_skills(cwd: str) -> List[SkillCommand]:
    """Get all available skills (dir-based + dynamic)."""
    dir_skills = await load_skills_from_dir(cwd)
    all_skills = list(dir_skills)

    seen = {s.name for s in all_skills}

    # Add dynamic skills
    for ds in _dynamic_skills.values():
        if ds.name not in seen:
            seen.add(ds.name)
            all_skills.append(ds)

    return all_skills


async def get_skill_tool_commands(cwd: str) -> List[SkillCommand]:
    """Get commands suitable for the SkillTool - skills with descriptions.

    Filters to 'prompt' type commands that the model should know about.
    """
    all_commands = await get_all_skills(cwd)
    return [
        cmd for cmd in all_commands
        if (cmd.has_user_specified_description or cmd.when_to_use)
        and not (cmd.loaded_from == "commands_DEPRECATED" and not cmd.has_user_specified_description)
    ]


def get_dynamic_skills() -> List[SkillCommand]:
    """Get dynamically discovered skills."""
    return list(_dynamic_skills.values())


async def discover_skill_dirs_for_paths(file_paths: List[str], cwd: str) -> List[str]:
    """Discover skill directories by walking up from file paths to cwd.

    Args:
        file_paths: File paths to check
        cwd: Current working directory (upper bound for discovery)

    Returns:
        Newly discovered skill directories, sorted deepest first
    """
    resolved_cwd = os.path.abspath(cwd)
    new_dirs = []

    for file_path in file_paths:
        current_dir = os.path.dirname(os.path.abspath(file_path))
        cwd_prefix = resolved_cwd + os.sep

        while current_dir.startswith(cwd_prefix) and current_dir != resolved_cwd:
            skill_dir = os.path.join(current_dir, ".claude", "skills")

            if skill_dir not in _dynamic_skill_dirs:
                _dynamic_skill_dirs.add(skill_dir)
                if os.path.isdir(skill_dir):
                    new_dirs.append(skill_dir)

            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent

    # Sort deepest first
    return sorted(new_dirs, key=lambda d: d.count(os.sep), reverse=True)


async def add_skill_directories(dirs: List[str]) -> None:
    """Load skills from the given directories and merge into dynamic skills."""
    if not dirs:
        return

    for skill_dir in dirs:
        skills = await _load_skills_from_skills_dir(skill_dir, "projectSettings")
        for skill in skills:
            _dynamic_skills[skill.name] = skill

    if skills:
        logger.debug(f"Dynamically loaded {len(skills)} skills from {len(dirs)} dirs")


def activate_conditional_skills_for_paths(
    file_paths: List[str],
    cwd: str,
) -> List[str]:
    """Activate conditional skills whose path patterns match the given file paths."""
    if not _conditional_skills:
        return []

    activated = []
    resolved_cwd = os.path.abspath(cwd)

    for name, skill in list(_conditional_skills.items()):
        if not skill.paths:
            continue

        for file_path in file_paths:
            abs_path = os.path.abspath(file_path) if not os.path.isabs(file_path) else file_path
            try:
                rel_path = os.path.relpath(abs_path, resolved_cwd)
            except ValueError:
                continue

            if rel_path.startswith(".."):
                continue

            # Simple glob matching
            for pattern in skill.paths:
                clean_pattern = pattern.rstrip("/**")
                if _matches_skill_path(rel_path, clean_pattern):
                    _dynamic_skills[name] = skill
                    _activated_conditional_skill_names.add(name)
                    del _conditional_skills[name]
                    activated.append(name)
                    logger.debug(f"Activated conditional skill '{name}' (matched: {rel_path})")
                    break
            else:
                continue
            break

    return activated


def _matches_skill_path(file_path: str, pattern: str) -> bool:
    """Simple gitignore-style pattern matching."""
    import fnmatch
    if pattern == "**":
        return True
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return file_path.startswith(base + "/") or file_path == base
    if "/**/" in pattern:
        # Handle ** in the middle (e.g., src/**/*.ts)
        return fnmatch.fnmatch(file_path, pattern)
    if pattern.startswith("/"):
        pattern = pattern[1:]
    return fnmatch.fnmatch(file_path, pattern)


# ---------------------------------------------------------------------------
# Skill Listing Formatting
# ---------------------------------------------------------------------------

def _get_command_description(cmd: SkillCommand) -> str:
    """Get the description text for a skill command in listings."""
    desc = f"{cmd.description} - {cmd.when_to_use}" if cmd.when_to_use else cmd.description
    if len(desc) > MAX_LISTING_DESC_CHARS:
        return desc[:MAX_LISTING_DESC_CHARS - 1] + "\u2026"
    return desc


def _format_command_description(cmd: SkillCommand) -> str:
    """Format a single command entry for the skill listing."""
    return f"- {cmd.name}: {_get_command_description(cmd)}"


def get_char_budget(context_window_tokens: Optional[int] = None) -> int:
    """Get the character budget for skill listings."""
    env_budget = os.environ.get("SLASH_COMMAND_TOOL_CHAR_BUDGET")
    if env_budget:
        try:
            return int(env_budget)
        except ValueError:
            pass
    if context_window_tokens:
        return int(context_window_tokens * CHARS_PER_TOKEN * SKILL_BUDGET_CONTEXT_PERCENT)
    return DEFAULT_CHAR_BUDGET


def format_commands_within_budget(
    commands: List[SkillCommand],
    context_window_tokens: Optional[int] = None,
) -> str:
    """Format skill commands to fit within a character budget."""
    if not commands:
        return ""

    budget = get_char_budget(context_window_tokens)

    # Try full descriptions first
    full_entries = [_format_command_description(cmd) for cmd in commands]
    full_total = sum(len(e) for e in full_entries) + (len(full_entries) - 1)

    if full_total <= budget:
        return "\n".join(full_entries)

    # Truncate all descriptions proportionally
    name_overhead = sum(len(cmd.name) + 4 for cmd in commands) + len(commands) - 1
    max_desc_len = max(20, (budget - name_overhead) // len(commands))

    result_parts = []
    for cmd in commands:
        desc = _get_command_description(cmd)
        truncated = desc[:max_desc_len] + "\u2026" if len(desc) > max_desc_len else desc
        result_parts.append(f"- {cmd.name}: {truncated}")

    return "\n".join(result_parts)
