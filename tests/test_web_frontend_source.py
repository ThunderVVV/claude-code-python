from __future__ import annotations

from pathlib import Path


WEB_FRONTEND_SOURCE = Path("cc_code/web/static/index.html").read_text(
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


def test_web_frontend_generates_complete_unified_diffs_for_diff2html():
    assert "Diff.createTwoFilesPatch(" in WEB_FRONTEND_SOURCE
    assert "context: Number.MAX_SAFE_INTEGER" in WEB_FRONTEND_SOURCE


def test_web_frontend_contains_mobile_overflow_guards():
    assert "overflow-x: hidden;" in WEB_FRONTEND_SOURCE
    assert "--app-height: 100dvh;" in WEB_FRONTEND_SOURCE
    assert "min-height: var(--app-height);" in WEB_FRONTEND_SOURCE
    assert "const prefersCompactDiff = () => window.matchMedia('(max-width: 767px)').matches;" in WEB_FRONTEND_SOURCE
    assert "outputFormat: compactDiff ? 'line-by-line' : 'side-by-side'" in WEB_FRONTEND_SOURCE


def test_web_frontend_wraps_markdown_tables_for_horizontal_scrolling():
    assert "wrapper.className = 'markdown-table-wrapper';" in WEB_FRONTEND_SOURCE
    assert ".markdown-table-wrapper {" in WEB_FRONTEND_SOURCE
    assert "width: max-content;" in WEB_FRONTEND_SOURCE


def test_web_frontend_uses_responsive_mobile_layout_classes():
    assert 'class="app-shell mx-auto flex min-h-[100dvh] flex-col p-3 sm:p-4 md:p-6"' in WEB_FRONTEND_SOURCE
    assert 'class="editor-scroll flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain p-3 sm:p-4 md:p-6 space-y-4"' in WEB_FRONTEND_SOURCE
    assert 'class="flex flex-col items-stretch gap-3 sm:flex-row sm:items-end"' in WEB_FRONTEND_SOURCE


def test_web_frontend_updates_height_for_ios_keyboard_viewport_changes():
    assert "const updateAppViewportHeight = () => {" in WEB_FRONTEND_SOURCE
    assert "window.visualViewport?.height || window.innerHeight" in WEB_FRONTEND_SOURCE
    assert "document.documentElement.style.setProperty('--app-height'" in WEB_FRONTEND_SOURCE
    assert "const syncViewportMetrics = () => {" in WEB_FRONTEND_SOURCE
    assert "window.visualViewport?.addEventListener('resize', syncViewportMetrics);" in WEB_FRONTEND_SOURCE
    assert "window.visualViewport?.addEventListener('scroll', syncViewportMetrics);" in WEB_FRONTEND_SOURCE


def test_web_frontend_prevents_ios_input_zoom_on_focus():
    assert "font-size: 16px !important;" in WEB_FRONTEND_SOURCE


def test_web_frontend_uses_short_mobile_placeholder():
    assert ':placeholder="inputPlaceholder"' in WEB_FRONTEND_SOURCE
    assert "const inputPlaceholder = computed(() =>" in WEB_FRONTEND_SOURCE
    assert "isCompactViewport.value ? '输入消息...' : '输入消息... (Shift+Enter 换行, ↑↓ 历史)'" in WEB_FRONTEND_SOURCE


def test_web_frontend_optimizes_mobile_diff_view():
    assert ".diff-container .d2h-code-linenumber," in WEB_FRONTEND_SOURCE
    assert ".diff-container .d2h-code-side-linenumber" in WEB_FRONTEND_SOURCE
    assert ".diff-container .d2h-tag," in WEB_FRONTEND_SOURCE
    assert ".diff-container .d2h-changed-tag" in WEB_FRONTEND_SOURCE
    assert ".diff-container .d2h-code-line," in WEB_FRONTEND_SOURCE
    assert ".diff-container .d2h-code-side-line" in WEB_FRONTEND_SOURCE
