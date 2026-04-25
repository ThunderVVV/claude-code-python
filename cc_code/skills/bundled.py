"""Bundled skills that ship with the CLI - aligned with TypeScript src/skills/bundledSkills.ts

Bundled skills are programmatically registered at startup and available to all users.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from cc_code.skills.loader import SkillCommand, _bundled_skills


@dataclass
class BundledSkillDefinition:
    """Definition for a bundled skill."""
    name: str
    description: str
    get_prompt: Callable[[str, Any], str]  # (args, context) -> prompt
    aliases: Optional[List[str]] = None
    when_to_use: Optional[str] = None
    argument_hint: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    model: Optional[str] = None
    disable_model_invocation: bool = False
    user_invocable: bool = True
    is_enabled: Optional[Callable[[], bool]] = None
    hooks: Optional[dict] = None
    context: Optional[str] = None
    agent: Optional[str] = None


def register_bundled_skill(definition: BundledSkillDefinition) -> None:
    """Register a bundled skill.

    Args:
        definition: The bundled skill definition
    """
    skill = SkillCommand(
        name=definition.name,
        description=definition.description,
        source="bundled",
        loaded_from="bundled",
        when_to_use=definition.when_to_use,
        allowed_tools=definition.allowed_tools or [],
        argument_hint=definition.argument_hint,
        model=definition.model,
        disable_model_invocation=definition.disable_model_invocation,
        user_invocable=definition.user_invocable,
        context=definition.context,
        agent=definition.agent,
        hooks=definition.hooks,
        aliases=definition.aliases or [],
        has_user_specified_description=True,
        is_hidden=not definition.user_invocable,
        is_enabled=definition.is_enabled() if definition.is_enabled else True,
    )

    # Store the get_prompt function
    skill._get_prompt_fn = definition.get_prompt

    _bundled_skills.append(skill)


def get_bundled_skills() -> List[SkillCommand]:
    """Get all registered bundled skills."""
    return list(_bundled_skills)


def clear_bundled_skills() -> None:
    """Clear bundled skills registry (for testing)."""
    _bundled_skills.clear()


def init_bundled_skills() -> None:
    """Initialize all bundled skills at startup."""
    # Register built-in bundled skills
    # These are the essential skills that ship with CC Code

    register_bundled_skill(BundledSkillDefinition(
        name="commit",
        description="Create a git commit with a well-formatted message",
        when_to_use="When the user wants to commit changes to git",
        argument_hint="[-m 'optional message']",
        get_prompt=_commit_skill_prompt,
    ))

    register_bundled_skill(BundledSkillDefinition(
        name="review-pr",
        description="Review a pull request for code quality, bugs, and style",
        when_to_use="When the user wants to review a PR or code changes",
        argument_hint="<pr_number>",
        get_prompt=_review_pr_skill_prompt,
    ))

    register_bundled_skill(BundledSkillDefinition(
        name="pdf",
        description="Work with PDF files - extract text, fill forms, etc.",
        when_to_use="When the user mentions PDF files or PDF operations",
        get_prompt=_pdf_skill_prompt,
    ))

    register_bundled_skill(BundledSkillDefinition(
        name="fix",
        description="Diagnose and fix issues with code, tests, or configuration",
        when_to_use="When the user asks to fix an error, bug, or failing test",
        get_prompt=_fix_skill_prompt,
    ))

    register_bundled_skill(BundledSkillDefinition(
        name="explain",
        description="Explain code, architecture, or technical concepts clearly",
        when_to_use="When the user asks to explain something about the codebase",
        argument_hint="<topic>",
        get_prompt=_explain_skill_prompt,
    ))


# ---------------------------------------------------------------------------
# Skill Prompt Generators
# ---------------------------------------------------------------------------

def _commit_skill_prompt(args: str, context: Any = None) -> str:
    workdir = getattr(context, "working_directory", "") if context else ""
    return f"""You are creating a git commit. Follow these steps:

1. Run `git status` and `git diff --staged` to understand the current state
2. If nothing is staged, run `git diff` to see unstaged changes
3. Analyze the changes and create a well-formatted commit message
4. Use conventional commits format: type(scope): description
5. Types: feat, fix, docs, style, refactor, test, chore, perf
6. Run `git add` on the relevant files if not already staged
7. Run `git commit -m "message"` with the crafted message

Keep commit messages concise but descriptive. Focus on WHAT and WHY, not HOW.

{args if args else ''}"""


def _review_pr_skill_prompt(args: str, context: Any = None) -> str:
    workdir = getattr(context, "working_directory", "") if context else ""
    return f"""You are reviewing code changes. Follow these steps:

1. Determine what changes to review (PR number, branch diff, or staged changes)
2. Read all modified files to understand the complete change
3. Check for:
   - Bugs and logic errors
   - Security vulnerabilities (OWASP top 10)
   - Performance issues
   - Code style and clarity
   - Test coverage adequacy
   - Error handling
   - Documentation completeness
4. Provide a structured review with:
   - Summary of changes
   - Critical issues (must fix)
   - Warnings (should fix)
   - Suggestions (nice to have)
   - Any test recommendations

Be constructive and specific. Include code examples for fixes where helpful.

Args: {args if args else 'review current changes'}"""


def _pdf_skill_prompt(args: str, context: Any = None) -> str:
    workdir = getattr(context, "working_directory", "") if context else ""
    return f"""You are working with PDF files. Available approaches:

1. **Read PDF text**: Use Python with PyPDF2 or pdfplumber
   ```python
   import pdfplumber
   with pdfplumber.open('file.pdf') as pdf:
       text = ''.join(page.extract_text() for page in pdf.pages)
   ```

2. **Extract tables**: Use pdfplumber or tabula-py
3. **Fill PDF forms**: Use pdfrw or PyPDF2
4. **Create PDF**: Use reportlab or fpdf2
5. **Convert formats**: Use pandoc or LibreOffice headless
6. **Merge/Split**: Use PyPDF2 or pdftk

Always check if the required Python package is installed before using it.
If not installed, use `pip install` first.

Args: {args if args else ''}"""


def _fix_skill_prompt(args: str, context: Any = None) -> str:
    workdir = getattr(context, "working_directory", "") if context else ""
    return f"""You are diagnosing and fixing an issue. Follow this process:

1. **Reproduce**: Understand the error by reading the error message carefully
2. **Locate**: Find the relevant source files using Grep/Glob
3. **Understand**: Read the surrounding code to understand the context
4. **Diagnose**: Identify the root cause, not just symptoms
5. **Fix**: Make the minimal change that resolves the issue
6. **Verify**: Run tests or validate the fix works

Important:
- Read code BEFORE making any changes
- Check related tests to understand expected behavior
- Make focused, minimal edits
- Run tests after your fix to verify nothing broke
- If the first fix doesn't work, diagnose why before trying again

Args: {args if args else ''}"""


def _explain_skill_prompt(args: str, context: Any = None) -> str:
    workdir = getattr(context, "working_directory", "") if context else ""
    return f"""You are explaining a technical topic. Follow these guidelines:

1. **Understand**: First read and understand the code or concept thoroughly
2. **Start high-level**: Give a brief overview before diving into details
3. **Be concrete**: Reference specific files and line numbers
4. **Use examples**: Show code snippets to illustrate
5. **Explain the why**: Don't just describe what code does, explain why it's designed that way
6. **Connect**: Show how the piece fits into the larger system

Tailor your explanation depth to what's being asked:
- A simple question gets a direct answer
- Complex architecture may need a structured walk-through

Topic: {args if args else 'explain the current codebase structure'}"""
