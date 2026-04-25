"""Skills system - aligned with TypeScript src/skills/ and src/commands.ts"""

from cc_code.skills.loader import (
    LoadedFrom,
    SkillCommand,
    load_skills_from_dir,
    get_all_skills,
    get_skill_tool_commands,
    clear_skill_caches,
    get_dynamic_skills,
    add_skill_directories,
    discover_skill_dirs_for_paths,
)
from cc_code.skills.bundled import (
    init_bundled_skills,
    get_bundled_skills,
    register_bundled_skill,
    BundledSkillDefinition,
)

__all__ = [
    "LoadedFrom",
    "SkillCommand",
    "load_skills_from_dir",
    "get_all_skills",
    "get_skill_tool_commands",
    "clear_skill_caches",
    "get_dynamic_skills",
    "add_skill_directories",
    "discover_skill_dirs_for_paths",
    "init_bundled_skills",
    "get_bundled_skills",
    "register_bundled_skill",
    "BundledSkillDefinition",
]
