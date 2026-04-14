"""Tests for session compaction functionality."""

from cc_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    Usage,
)
from cc_code.core.compaction import (
    SessionCompaction,
    CompactionResult,
    DEFAULT_COMPACTION_PROMPT,
    is_context_overflow,
)


def test_compaction_result():
    """Test CompactionResult dataclass."""
    result = CompactionResult(success=True, summary="Test summary", tokens_saved=100)
    assert result.success is True
    assert result.summary == "Test summary"
    assert result.tokens_saved == 100
    assert result.error is None

    error_result = CompactionResult(success=False, error="Test error")
    assert error_result.success is False
    assert error_result.error == "Test error"


def test_session_compaction_init():
    """Test SessionCompaction initialization."""
    messages = [
        Message.user_message("Hello"),
        Message.assistant_message([TextContent(text="Hi there")]),
    ]
    compaction = SessionCompaction(messages, model_name="test-model", context_window=100000)

    assert compaction.messages == messages
    assert compaction.model_name == "test-model"
    assert compaction.context_window == 100000


def test_get_messages_for_compaction():
    """Test filtering messages for compaction."""
    messages = [
        Message.user_message("Hello"),
        Message.assistant_message([TextContent(text="Hi")]),
        Message.user_message("How are you?"),
    ]
    # Mark one as compact summary
    messages[1].is_compact_summary = True

    compaction = SessionCompaction(messages)
    eligible = compaction.get_messages_for_compaction()

    # Should exclude compact summaries
    assert len(eligible) == 2
    assert eligible[0].get_text() == "Hello"
    assert eligible[1].get_text() == "How are you?"


def test_estimate_tokens():
    """Test token estimation."""
    compaction = SessionCompaction([])

    # Empty string
    assert compaction.estimate_tokens("") == 0

    # Simple text (roughly 4 chars per token)
    text = "Hello world"
    estimate = compaction.estimate_tokens(text)
    assert estimate == len(text) // 4


def test_should_compact():
    """Test compaction threshold check."""
    # Few messages - should not compact
    messages = [Message.user_message(f"Message {i}") for i in range(10)]
    compaction = SessionCompaction(messages)
    assert compaction.should_compact() is False

    # Many messages - should compact
    messages = [Message.user_message(f"Message {i}") for i in range(25)]
    compaction = SessionCompaction(messages)
    assert compaction.should_compact() is True


def test_create_compaction_prompt():
    """Test compaction prompt creation."""
    compaction = SessionCompaction([])

    # Default prompt
    prompt = compaction.create_compaction_prompt()
    assert "Goal" in prompt
    assert "Instructions" in prompt
    assert "Discoveries" in prompt

    # Custom prompt
    custom = "Custom prompt for testing"
    prompt = compaction.create_compaction_prompt(custom_prompt=custom)
    assert prompt == custom

    # Additional context
    prompt = compaction.create_compaction_prompt(additional_context=["Extra info"])
    assert "Extra info" in prompt


def test_build_messages_for_summary():
    """Test building messages for summary generation."""
    messages = [
        Message.user_message("Hello"),
        Message.assistant_message([TextContent(text="Hi there")]),
        Message.user_message("How are you?"),
    ]

    compaction = SessionCompaction(messages)
    summary_messages = compaction.build_messages_for_summary()

    # Should exclude last user message by default
    assert len(summary_messages) == 2
    assert summary_messages[0]["role"] == "user"
    assert summary_messages[1]["role"] == "assistant"


def test_create_summary_message():
    """Test creating a summary message."""
    compaction = SessionCompaction([])
    summary_msg = compaction.create_summary_message("This is a summary", parent_message_id="test-id")

    assert summary_msg.is_compact_summary is True
    assert summary_msg.uuid == "test-id"
    assert summary_msg.get_text() == "This is a summary"
    assert summary_msg.type == MessageRole.ASSISTANT


def test_compact_messages():
    """Test compacting messages with a summary."""
    messages = [
        Message.user_message("Message 1"),
        Message.assistant_message([TextContent(text="Response 1")]),
        Message.user_message("Message 2"),
        Message.assistant_message([TextContent(text="Response 2")]),
        Message.user_message("Message 3"),
    ]

    compaction = SessionCompaction(messages)
    compacted = compaction.compact_messages("Summary text", keep_last_n=2)

    # Should have summary + last 2 messages
    assert len(compacted) == 3
    assert compacted[0].is_compact_summary is True
    assert compacted[0].get_text() == "Summary text"


def test_is_context_overflow():
    """Test context overflow detection."""
    # No overflow
    usage = Usage(input_tokens=50000, output_tokens=10000)
    assert is_context_overflow(usage, context_window=100000) is False

    # Near overflow (90% threshold)
    usage = Usage(input_tokens=85000, output_tokens=10000)
    assert is_context_overflow(usage, context_window=100000) is True

    # No context window
    assert is_context_overflow(usage, context_window=None) is False


def test_prompt_matches_typescript():
    """Verify that DEFAULT_COMPACTION_PROMPT matches TypeScript version exactly."""
    # This is the exact prompt from TypeScript session/compaction.ts
    ts_prompt = """Provide a detailed prompt for continuing our conversation above.
Focus on information that would be helpful for continuing the conversation, including what we did, what we're doing, which files we're working on, and what we're going to do next.
The summary that you construct will be used so that another agent can read it and continue the work.
Do not call any tools. Respond only with the summary text.
Respond in the same language as the user's messages in the conversation.

When constructing the summary, try to stick to this template:
---
## Goal

[What goal(s) is the user trying to accomplish?]

## Instructions

- [What important instructions did the user give you that are relevant]
- [If there is a plan or spec, include information about it so next agent can continue using it]

## Discoveries

[What notable things were learned during this conversation that would be useful for the next agent to know when continuing the work]

## Accomplished

[What work has been completed, what work is still in progress, and what work is left?]

## Relevant files / directories

[Construct a structured list of relevant files that have been read, edited, or created that pertain to the task at hand. If all the files in a directory are relevant, include the path to the directory.]
---"""
    
    assert DEFAULT_COMPACTION_PROMPT == ts_prompt, "Prompt must match TypeScript version exactly"


def test_filter_compacted_messages():
    """Test filtering messages after compaction summary."""
    # Create messages simulating a conversation with compaction
    user1 = Message.user_message("Hello")
    user1.uuid = "user-1"
    
    asst1 = Message.assistant_message([TextContent(text="Hi there")])
    asst1.uuid = "asst-1"
    
    user2 = Message.user_message("/compact")
    user2.uuid = "user-2"
    user2.is_meta = True
    
    # Summary message - marks user2 as completed
    summary = Message.assistant_message([TextContent(text="## Goal\nTest summary")])
    summary.uuid = "summary-1"
    summary.is_compact_summary = True
    summary.parent_id = "user-2"
    summary.stop_reason = "stop"
    
    user3 = Message.user_message("Continue conversation")
    user3.uuid = "user-3"
    
    asst3 = Message.assistant_message([TextContent(text="Sure!")])
    asst3.uuid = "asst-3"
    
    messages = [user1, asst1, user2, summary, user3, asst3]
    
    # Simulate the filtering logic from QueryEngine
    completed_parent_ids = set()
    for msg in messages:
        if (msg.type == MessageRole.ASSISTANT and 
            msg.is_compact_summary and 
            msg.stop_reason and
            not msg.stop_reason.startswith("error")):
            if msg.parent_id:
                completed_parent_ids.add(msg.parent_id)
    
    assert "user-2" in completed_parent_ids
    
    # Filter messages: start from compaction boundary
    # The logic clears result when encountering the user message that triggered compaction
    # Then continues adding, so summary is included
    result = []
    for msg in messages:
        if msg.type == MessageRole.USER and msg.uuid in completed_parent_ids:
            result = []  # Clear previous messages
            continue
        result.append(msg)
    
    # Should include summary and messages after it
    assert len(result) == 3
    assert result[0].uuid == "summary-1"
    assert result[1].uuid == "user-3"
    assert result[2].uuid == "asst-3"
