from __future__ import annotations

from pathlib import Path


WEB_FRONTEND_SOURCE = Path("claude_code/web/static/index.html").read_text(
    encoding="utf-8"
)


def test_web_frontend_contains_auto_follow_hooks():
    assert '@scroll="handleMessagesScroll"' in WEB_FRONTEND_SOURCE
    assert "const autoFollowOutput = ref(true);" in WEB_FRONTEND_SOURCE
    assert "const handleMessagesScroll = () => {" in WEB_FRONTEND_SOURCE
    assert (
        "if (messagesContainer.value && (force || autoFollowOutput.value))"
        in WEB_FRONTEND_SOURCE
    )


def test_web_frontend_contains_user_context_and_web_indicator_hooks():
    assert "if (data.type === 'message_complete')" in WEB_FRONTEND_SOURCE
    assert "applyServerUserMessage(data.message);" in WEB_FRONTEND_SOURCE
    assert (
        "const currentInputHasWeb = computed(() => hasWebReference(inputText.value));"
        in WEB_FRONTEND_SOURCE
    )
    assert "@web 已启用" in WEB_FRONTEND_SOURCE


def test_web_frontend_contains_keyboard_parity_hooks():
    assert "e.key === 'Escape' && isStreaming.value" in WEB_FRONTEND_SOURCE
    assert (
        "document.addEventListener('keydown', handleGlobalKeydown);"
        in WEB_FRONTEND_SOURCE
    )
    assert "navigator.clipboard?.writeText" in WEB_FRONTEND_SOURCE
    assert (
        "if (inputHistory.value.length > 1000) inputHistory.value.shift();"
        in WEB_FRONTEND_SOURCE
    )
    assert "if (!abortController.value) return;" in WEB_FRONTEND_SOURCE
    assert "if (sessionId.value) {" in WEB_FRONTEND_SOURCE


def test_web_frontend_uses_atom_one_dark_theme_tokens():
    assert "atom-one-dark.min.css" in WEB_FRONTEND_SOURCE
    assert "highlight.min.js" in WEB_FRONTEND_SOURCE
    assert "--color-blue-primary: #61afef;" in WEB_FRONTEND_SOURCE
    assert "langPrefix: 'hljs language-'" in WEB_FRONTEND_SOURCE
    assert "class=\"app-mark" in WEB_FRONTEND_SOURCE
    assert "class=\"composer-input" in WEB_FRONTEND_SOURCE
