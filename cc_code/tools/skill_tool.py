"""SkillTool - allows the model to invoke registered skills.

Aligned with TypeScript src/tools/SkillTool/SkillTool.ts
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from cc_code.core.tools import BaseTool, ToolInputSchema, ToolContext
from cc_code.skills.loader import (
    SkillCommand,
    get_all_skills,
    format_commands_within_budget,
)

logger = logging.getLogger(__name__)

SKILL_TOOL_NAME = "Skill"


class SkillTool(BaseTool):
    """Tool that allows the model to invoke slash-command skills.

    Skills are user-defined or bundled prompt expansions that provide
    specialized capabilities and domain knowledge.
    """

    name = SKILL_TOOL_NAME

    def __init__(self, cwd: str = ""):
        self._cwd = cwd
        self.input_schema = ToolInputSchema(
            type="object",
            properties={
                "skill": {
                    "type": "string",
                    "description": 'The skill name. E.g., "commit", "review-pr", or "pdf"',
                },
                "args": {
                    "type": "string",
                    "description": "Optional arguments for the skill",
                },
            },
            required=["skill"],
        )

    @property
    def description(self) -> str:
        return "Execute a skill (slash command) within the main conversation"

    def get_prompt(self) -> str:
        """Return usage guidance for the system prompt.

        Aligned with TypeScript SkillTool/prompt.ts
        """
        return get_skill_tool_prompt(self._cwd)

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        # Skills may modify files, so treat as potentially read/write
        return False

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        """Execute a skill by loading its prompt and returning it.

        The skill's prompt will be injected into the conversation as
        system-reminder context for the next model turn.
        """
        skill_name = input.get("skill", "").strip()
        args = input.get("args", "")

        # Remove leading slash if present
        if skill_name.startswith("/"):
            skill_name = skill_name[1:]

        if not skill_name:
            return "Error: skill name is required"

        cwd = context.working_directory or self._cwd

        # Find the skill
        all_skills = await get_all_skills(cwd)
        skill = None
        for s in all_skills:
            if s.name == skill_name or skill_name in s.aliases:
                skill = s
                break

        if not skill:
            return self._format_unknown_skill(skill_name, all_skills, cwd)

        if skill.disable_model_invocation:
            return f"Error: Skill '{skill_name}' cannot be invoked by the model"

        # Get the skill's prompt - bundled skills use _get_prompt_fn
        if hasattr(skill, '_get_prompt_fn') and callable(skill._get_prompt_fn):
            prompt = skill._get_prompt_fn(args, context)
        else:
            prompt = await skill.get_prompt_for_command(args)

        # Return the expanded skill prompt as a system-reminder
        return f"""<system-reminder>
Skill '{skill_name}' has been loaded. Follow these instructions:

{prompt}

When you're done with this skill, continue with the user's original request.
</system-reminder>"""

    def _format_unknown_skill(
        self,
        skill_name: str,
        all_skills: List[SkillCommand],
        cwd: str,
    ) -> str:
        """Format an error message when a skill is not found."""
        # Find close matches
        import difflib
        available_names = [s.name for s in all_skills if s.user_invocable]
        matches = difflib.get_close_matches(skill_name, available_names, n=3, cutoff=0.5)

        lines = [f"Unknown skill: {skill_name}"]

        if matches:
            lines.append(f"\nDid you mean one of these?")
            for m in matches:
                lines.append(f"  - {m}")
        else:
            # Show available skills
            skill_commands = [s for s in all_skills 
                            if s.has_user_specified_description or s.when_to_use]
            if skill_commands:
                listing = format_commands_within_budget(skill_commands)
                lines.append(f"\nAvailable skills:\n{listing}")

        return "\n".join(lines)


def get_skill_tool_prompt(cwd: str) -> str:
    """Get the SkillTool prompt for the system message.

    Aligned with TypeScript tools/SkillTool/prompt.ts
    """
    return f"""Execute a skill within the main conversation

When users ask you to perform tasks, check if any of the available skills match. Skills provide specialized capabilities and domain knowledge.

When users reference a "slash command" or "/<something>" (e.g., "/commit", "/review-pr"), they are referring to a skill. Use this tool to invoke it.

How to invoke:
- Use this tool with the skill name and optional arguments
- Examples:
  - `skill: "pdf"` - invoke the pdf skill
  - `skill: "commit", args: "-m 'Fix bug'"` - invoke with arguments
  - `skill: "review-pr", args: "123"` - invoke with arguments

Important:
- Available skills are listed in system-reminder messages in the conversation
- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the relevant Skill tool BEFORE generating any other response about the task
- NEVER mention a skill without actually calling this tool
- Do not invoke a skill that is already running
- Do not use this tool for built-in CLI commands (like /help, /clear, etc.)
- If you see a <command-name> tag in the current conversation turn, the skill has ALREADY been loaded - follow the instructions directly instead of calling this tool again
"""
