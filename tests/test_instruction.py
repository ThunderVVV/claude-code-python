"""Tests for instruction loading mechanism."""

import os
import tempfile
from pathlib import Path

import pytest

from cc_code.core.instruction import (
    InstructionConfig,
    InstructionService,
)


@pytest.mark.asyncio
async def test_load_local_instruction_file():
    """Test loading a local instruction file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a CLAUDE.md file
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text("# Test Instructions\n\nThis is a test instruction file.")
        
        # Create service and load instructions
        service = InstructionService()
        instructions = await service.get_system_instructions(tmpdir)
        
        assert len(instructions) == 1
        assert "Test Instructions" in instructions[0]
        assert str(claude_md) in instructions[0]
        
        await service.close()


@pytest.mark.asyncio
async def test_load_agents_md():
    """Test loading AGENTS.md file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create an AGENTS.md file
        agents_md = Path(tmpdir) / "AGENTS.md"
        agents_md.write_text("# Agent Instructions\n\nAgent-specific instructions.")
        
        # Create service and load instructions
        service = InstructionService()
        instructions = await service.get_system_instructions(tmpdir)
        
        assert len(instructions) == 1
        assert "Agent Instructions" in instructions[0]
        assert str(agents_md) in instructions[0]
        
        await service.close()


@pytest.mark.asyncio
async def test_priority_agents_over_claude():
    """Test that AGENTS.md takes priority over CLAUDE.md (first match wins)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create both files
        agents_md = Path(tmpdir) / "AGENTS.md"
        agents_md.write_text("# Agent Instructions")
        
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text("# CC Instructions")
        
        # Create service and load instructions
        service = InstructionService()
        instructions = await service.get_system_instructions(tmpdir)
        
        # Should only load AGENTS.md (first match wins)
        assert len(instructions) == 1
        assert "Agent Instructions" in instructions[0]
        
        await service.close()


@pytest.mark.asyncio
async def test_search_upward():
    """Test searching upward for instruction files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory structure
        root = Path(tmpdir)
        subdir = root / "sub" / "dir"
        subdir.mkdir(parents=True)
        
        # Create CLAUDE.md in root
        claude_md = root / "CLAUDE.md"
        claude_md.write_text("# Root Instructions")
        
        # Load from subdirectory
        service = InstructionService()
        instructions = await service.get_system_instructions(str(subdir))
        
        assert len(instructions) == 1
        assert "Root Instructions" in instructions[0]
        
        await service.close()


@pytest.mark.asyncio
async def test_custom_instructions():
    """Test loading custom instruction files from config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a custom instruction file
        custom_md = Path(tmpdir) / "CUSTOM.md"
        custom_md.write_text("# Custom Instructions\n\nCustom file content.")
        
        # Create config with custom instruction
        config = InstructionConfig(
            custom_instructions=[str(custom_md)],
        )
        
        # Load instructions
        service = InstructionService(config)
        instructions = await service.get_system_instructions(tmpdir)
        
        # Should load the custom file
        found = False
        for inst in instructions:
            if "Custom Instructions" in inst:
                found = True
                break
        
        assert found, "Custom instruction not found"
        
        await service.close()


@pytest.mark.asyncio
async def test_disable_claude_prompt():
    """Test disabling CLAUDE.md loading via config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CLAUDE.md
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text("# CC Instructions")
        
        # Create AGENTS.md
        agents_md = Path(tmpdir) / "AGENTS.md"
        agents_md.write_text("# Agent Instructions")
        
        # Create config that disables CLAUDE.md
        config = InstructionConfig(
            disable_claude_prompt=True,
        )
        
        # Load instructions
        service = InstructionService(config)
        instructions = await service.get_system_instructions(tmpdir)
        
        # Should only load AGENTS.md
        assert len(instructions) == 1
        assert "Agent Instructions" in instructions[0]
        
        await service.close()


@pytest.mark.asyncio
async def test_disable_project_config():
    """Test disabling project-level config loading."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CLAUDE.md in project
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text("# Project Instructions")
        
        # Create config that disables project config
        config = InstructionConfig(
            disable_project_config=True,
        )
        
        # Load instructions
        service = InstructionService(config)
        instructions = await service.get_system_instructions(tmpdir)
        
        # Should not include project-level files
        assert len(instructions) == 0
        
        await service.close()


@pytest.mark.asyncio
async def test_env_config():
    """Test creating config from environment variables."""
    # Test default config
    config = InstructionConfig.from_env()
    assert "AGENTS.md" in config.files
    assert "CLAUDE.md" in config.files
    assert not config.disable_claude_prompt
    assert not config.disable_project_config
    
    # Test with environment variable set
    old_env = os.environ.get("OPENCODE_DISABLE_CC_CODE_PROMPT")
    try:
        os.environ["OPENCODE_DISABLE_CC_CODE_PROMPT"] = "true"
        config = InstructionConfig.from_env()
        assert "CLAUDE.md" not in config.files
        assert config.disable_claude_prompt
    finally:
        if old_env is not None:
            os.environ["OPENCODE_DISABLE_CC_CODE_PROMPT"] = old_env
        else:
            os.environ.pop("OPENCODE_DISABLE_CC_CODE_PROMPT", None)


@pytest.mark.asyncio
async def test_global_config_directory():
    """Test loading from global config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a global config directory structure
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        
        # Create AGENTS.md in config dir
        agents_md = config_dir / "AGENTS.md"
        agents_md.write_text("# Global Instructions")
        
        # Create config with custom config dir
        config = InstructionConfig(
            config_dir=str(config_dir),
        )
        
        # Load instructions
        service = InstructionService(config)
        global_files = service._get_global_files()
        
        # Should include the config dir AGENTS.md
        assert any(str(agents_md) in f for f in global_files)
        
        await service.close()


@pytest.mark.asyncio
async def test_empty_directory():
    """Test loading from directory with no instruction files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        service = InstructionService()
        instructions = await service.get_system_instructions(tmpdir)
        
        # Should return empty list
        assert len(instructions) == 0
        
        await service.close()


@pytest.mark.asyncio
async def test_system_prompt_integration():
    """Test that instructions are integrated into system prompt."""
    from cc_code.core.prompts import create_default_system_prompt
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CLAUDE.md
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text("# Project Instructions\n\nAlways use type hints.")
        
        # Load instructions
        service = InstructionService()
        instructions = await service.get_system_instructions(tmpdir)
        
        # Create system prompt with instructions
        system_prompt = create_default_system_prompt(
            cwd=tmpdir,
            model_name="test-model",
            instructions=instructions,
        )
        
        # Should contain the instruction content
        assert "Instructions from:" in system_prompt
        assert "Always use type hints" in system_prompt
        
        await service.close()


@pytest.mark.asyncio
async def test_nearby_instruction_loading():
    """Test loading nearby instruction files when reading a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory structure
        root = Path(tmpdir)
        src_dir = root / "src"
        components_dir = src_dir / "components"
        components_dir.mkdir(parents=True)
        
        # Create root AGENTS.md (system-level, loaded at startup)
        root_agents = root / "AGENTS.md"
        root_agents.write_text("# Root Instructions\n\nRoot level rules.")
        
        # Create src/AGENTS.md (nearby to files in src/)
        src_agents = src_dir / "AGENTS.md"
        src_agents.write_text("# Src Instructions\n\nSource code rules.")
        
        # Create components/AGENTS.md (nearby to files in components/)
        components_agents = components_dir / "AGENTS.md"
        components_agents.write_text("# Component Instructions\n\nComponent rules.")
        
        # Create a file to read
        button_file = components_dir / "Button.tsx"
        button_file.write_text("export const Button = () => <button />;")
        
        # Create service and load system instructions (root level only)
        service = InstructionService()
        system_instructions = await service.get_system_instructions(str(root))
        
        # Should only have root AGENTS.md in system instructions
        assert len(system_instructions) == 1
        assert str(root_agents) in system_instructions[0]
        
        # Now test nearby loading when reading Button.tsx
        nearby = await service.resolve_nearby_instructions(
            messages=[],
            filepath=str(button_file),
            message_id="test-msg-1",
            project_root=str(root),
        )
        
        # Should load both src/AGENTS.md and components/AGENTS.md
        assert len(nearby) == 2
        assert str(src_agents) in nearby[0] or str(src_agents) in nearby[1]
        assert str(components_agents) in nearby[0] or str(components_agents) in nearby[1]
        
        # Root AGENTS.md should NOT be in nearby (already in system paths)
        assert str(root_agents) not in nearby[0] and str(root_agents) not in nearby[1]
        
        await service.close()


@pytest.mark.asyncio
async def test_nearby_instruction_from_previous_messages():
    """Test that instructions from previous messages are not reloaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        src_dir = root / "src"
        src_dir.mkdir(parents=True)
        
        # Create src/AGENTS.md
        src_agents = src_dir / "AGENTS.md"
        src_agents.write_text("# Src Instructions")
        
        # Create a file
        file1 = src_dir / "file1.ts"
        file1.write_text("export const a = 1;")
        
        service = InstructionService()
        
        # Simulate a previous message that loaded the instruction
        from cc_code.core.messages import Message
        prev_msg = Message.tool_result_message(
            tool_use_id="prev-tool",
            content="file content",
            metadata={"loaded": [str(src_agents)]},
        )
        
        # Read file1 - should NOT load nearby instruction (already in messages)
        nearby = await service.resolve_nearby_instructions(
            messages=[prev_msg],
            filepath=str(file1),
            message_id="msg-2",
            project_root=str(root),
        )
        assert len(nearby) == 0
        
        await service.close()
