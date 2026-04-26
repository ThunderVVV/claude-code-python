from __future__ import annotations

from pathlib import Path


WEB_FRONTEND_SOURCE = Path("cc_code/web/static/index.html").read_text(
    encoding="utf-8"
)
DIFF_VIEWER_SOURCE = Path("cc_code/web/static/diff-viewer.js").read_text(
    encoding="utf-8"
)
DIFF_VIEWER_CSS_SOURCE = Path("cc_code/web/static/diff-viewer.css").read_text(
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
    assert "const webSearchEnabled = ref(false);" in WEB_FRONTEND_SOURCE
    assert "const sessionHasUsedWebSearch = ref(false);" in WEB_FRONTEND_SOURCE
    assert "text = '@web ' + text;" in WEB_FRONTEND_SOURCE
    assert "联网搜索" in WEB_FRONTEND_SOURCE
    assert "@web" in WEB_FRONTEND_SOURCE


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


def test_web_frontend_preserves_thinking_line_breaks():
    assert "const lastBlock = content[content.length - 1];" in WEB_FRONTEND_SOURCE
    assert "if (lastBlock?.type === 'thinking') {" in WEB_FRONTEND_SOURCE
    assert "lastBlock.thinking += data.thinking;" in WEB_FRONTEND_SOURCE
    assert 'class="text-gray-500 italic thinking-block whitespace-pre-wrap break-words"' in WEB_FRONTEND_SOURCE
    assert '<span v-else-if="block.type === \'thinking\'"' not in WEB_FRONTEND_SOURCE


def test_web_frontend_uses_floating_footer_info_popovers():
    assert '@click="toggleWorkspaceDetails"' in WEB_FRONTEND_SOURCE
    assert '@click="toggleTokenDetails"' in WEB_FRONTEND_SOURCE
    assert "data-info-popover-trigger" in WEB_FRONTEND_SOURCE
    assert "data-info-popover" in WEB_FRONTEND_SOURCE
    assert "absolute bottom-full left-0 z-40 mb-2" in WEB_FRONTEND_SOURCE
    assert "const closeInfoPopovers = () => {" in WEB_FRONTEND_SOURCE
    assert "const toggleWorkspaceDetails = () => {" in WEB_FRONTEND_SOURCE
    assert "const toggleTokenDetails = () => {" in WEB_FRONTEND_SOURCE
    assert "!target.closest('[data-info-popover]')" in WEB_FRONTEND_SOURCE
    assert "!target.closest('[data-info-popover-trigger]')" in WEB_FRONTEND_SOURCE
    assert 'class="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm"' not in WEB_FRONTEND_SOURCE


def test_web_frontend_uses_official_diff2html_demo_viewer():
    assert "github.min.css" in WEB_FRONTEND_SOURCE
    assert "highlight.min.js" in WEB_FRONTEND_SOURCE
    assert '<link rel="stylesheet" href="/static/diff-viewer.css?v=20260426-5">' in WEB_FRONTEND_SOURCE
    assert WEB_FRONTEND_SOURCE.index("</style>") < WEB_FRONTEND_SOURCE.index('/static/diff-viewer.css')
    assert '<script src="/static/diff-viewer.js?v=20260426-4"></script>' in WEB_FRONTEND_SOURCE
    assert "max-width: 64rem;" in WEB_FRONTEND_SOURCE
    assert 'class="messages-area flex-1 overflow-y-auto overflow-x-hidden"' in WEB_FRONTEND_SOURCE
    assert ".messages-area,\n        .messages-area * {" in WEB_FRONTEND_SOURCE
    assert "font-size: var(--font-size-base) !important;" in WEB_FRONTEND_SOURCE
    assert "--font-size-code: 12px;" in WEB_FRONTEND_SOURCE
    assert ".messages-area code," in WEB_FRONTEND_SOURCE
    assert "font-size: var(--font-size-code) !important;" in WEB_FRONTEND_SOURCE
    assert 'class="chat-container py-6 space-y-1 px-0"' in WEB_FRONTEND_SOURCE
    assert 'class="composer-shell bg-white px-0 pb-6"' in WEB_FRONTEND_SOURCE
    assert 'class="chat-container px-0"' in WEB_FRONTEND_SOURCE
    assert "padding: 1rem 0 1.5rem;" in WEB_FRONTEND_SOURCE
    assert 'class="message-assistant min-w-0 flex-1 rounded-2xl rounded-tl-sm px-0 py-1 mb-0"' in WEB_FRONTEND_SOURCE
    assert 'class="message-assistant min-w-0 flex-1 rounded-2xl rounded-tl-sm px-4 py-1 mb-0"' not in WEB_FRONTEND_SOURCE
    assert 'class="chat-container py-6 space-y-1 px-4"' not in WEB_FRONTEND_SOURCE
    assert 'class="chat-container px-4"' not in WEB_FRONTEND_SOURCE
    assert 'class="cc-diff-viewer"' in WEB_FRONTEND_SOURCE
    assert 'class="assistant-content min-w-0 break-words mb-0"' in WEB_FRONTEND_SOURCE
    assert 'class="assistant-content markdown-body' not in WEB_FRONTEND_SOURCE
    assert 'class="text-container markdown-body min-w-0 break-words"' in WEB_FRONTEND_SOURCE
    assert 'message.type === \'diff\'' in WEB_FRONTEND_SOURCE
    assert 'class="diff-message fade-in w-full"' in WEB_FRONTEND_SOURCE
    assert "appendDiffMessage(" in WEB_FRONTEND_SOURCE
    assert "const removeToolBlock = (assistantMessage, toolUseId) => {" in WEB_FRONTEND_SOURCE
    assert "if (blockIndex < 0) return false;" in WEB_FRONTEND_SOURCE
    assert "removeToolBlock(currentAssistantMessage.value, data.tool_use_id);" in WEB_FRONTEND_SOURCE
    assert "removeToolBlock(assistantMsg, block.tool_use_id);" in WEB_FRONTEND_SOURCE
    assert "if (assistantMsg.content.length > 0) {" in WEB_FRONTEND_SOURCE
    assert "const diffData = !data.is_error && isFileEditTool(toolName)" in WEB_FRONTEND_SOURCE
    assert "const diffData = !block.is_error && isFileEditTool(toolName)" in WEB_FRONTEND_SOURCE
    assert "if (!targetMsg) continue;" in WEB_FRONTEND_SOURCE
    assert "inputDetails" not in WEB_FRONTEND_SOURCE
    assert 'v-html="block.inputDetails"' not in WEB_FRONTEND_SOURCE
    assert "Object.entries(toolInput || {})" not in WEB_FRONTEND_SOURCE
    assert "CCCodeDiffViewer.render(container, props.message.diffData);" in WEB_FRONTEND_SOURCE
    assert "block.diffData" not in WEB_FRONTEND_SOURCE
    assert "new Diff2HtmlUI" not in WEB_FRONTEND_SOURCE
    assert "DIFF_HIGHLIGHT_LANGUAGES" not in WEB_FRONTEND_SOURCE
    assert "langPrefix: 'hljs language-'" in WEB_FRONTEND_SOURCE
    assert "drawFileList: false" in DIFF_VIEWER_SOURCE
    assert "fileListToggle: false" in DIFF_VIEWER_SOURCE
    assert "drawFileList: true" not in DIFF_VIEWER_SOURCE
    assert "container.querySelectorAll('.d2h-file-list-wrapper').forEach((element) => {" in DIFF_VIEWER_SOURCE
    assert "element.remove();" in DIFF_VIEWER_SOURCE
    assert "matching: 'words'" in DIFF_VIEWER_SOURCE
    assert "outputFormat: 'line-by-line'" in DIFF_VIEWER_SOURCE
    assert "highlightLanguages: HIGHLIGHT_LANGUAGES" in DIFF_VIEWER_SOURCE
    assert "py: 'python'" in DIFF_VIEWER_SOURCE
    assert "html: 'xml'" in DIFF_VIEWER_SOURCE
    assert "font-family: 'Menlo', 'Consolas', monospace !important;" in DIFF_VIEWER_CSS_SOURCE
    assert "font-size: 12px !important;" in DIFF_VIEWER_CSS_SOURCE
    assert "font-size: 13px !important;" not in DIFF_VIEWER_CSS_SOURCE
    assert "font-size: 14px;" in DIFF_VIEWER_CSS_SOURCE
    assert ".cc-diff-viewer .d2h-tag," in DIFF_VIEWER_CSS_SOURCE
    assert ".cc-diff-viewer .d2h-file-collapse {" in DIFF_VIEWER_CSS_SOURCE
    assert "font-size: 14px !important;" in DIFF_VIEWER_CSS_SOURCE
    assert "font-size: 15px;" not in DIFF_VIEWER_CSS_SOURCE
    assert ".cc-diff-viewer .d2h-diff-table *" in DIFF_VIEWER_CSS_SOURCE
    assert "border: 0;" in DIFF_VIEWER_CSS_SOURCE
    assert "padding: 0;" in DIFF_VIEWER_CSS_SOURCE
    assert "position: relative;" in DIFF_VIEWER_CSS_SOURCE
    assert "left: 0;" in DIFF_VIEWER_CSS_SOURCE
    assert "z-index: 2;" in DIFF_VIEWER_CSS_SOURCE
    assert "display: inline-block !important;" in DIFF_VIEWER_CSS_SOURCE
    assert "background-color: var(--d2h-bg-color) !important;" not in DIFF_VIEWER_CSS_SOURCE
    assert ".cc-diff-viewer .hljs-keyword" in DIFF_VIEWER_CSS_SOURCE
    assert "color: #d73a49;" in DIFF_VIEWER_CSS_SOURCE


def test_web_frontend_generates_complete_unified_diffs_for_diff2html():
    assert "CCCodeDiffViewer.createDiff(oldString, newString, filePath)" in WEB_FRONTEND_SOURCE
    assert "CCCodeDiffViewer.createDiff('', content, filePath)" in WEB_FRONTEND_SOURCE
    assert "Diff.createTwoFilesPatch(" in DIFF_VIEWER_SOURCE
    assert "const normalizedPath = normalizeDiffPath(filePath);" in DIFF_VIEWER_SOURCE
    assert "const displayPath = getDiffDisplayPath(filePath);" in DIFF_VIEWER_SOURCE
    assert "return normalizedPath.split('/').filter(Boolean).pop() || normalizedPath || 'file';" in DIFF_VIEWER_SOURCE
    assert "const getRenderedDisplayName = (fileName) => {" in DIFF_VIEWER_SOURCE
    assert "container.querySelectorAll('.d2h-file-name').forEach((element) => {" in DIFF_VIEWER_SOURCE
    assert "element.textContent = getRenderedDisplayName(element.textContent);" in DIFF_VIEWER_SOURCE
    assert "`a/${displayPath}`" in DIFF_VIEWER_SOURCE
    assert "`diff --git a/${displayPath} b/${displayPath}\\n${patch}`" in DIFF_VIEWER_SOURCE
    assert "undefined,\n            undefined," in DIFF_VIEWER_SOURCE
    assert "replace(/^\\/+/, '')" in DIFF_VIEWER_SOURCE
    assert "context: Number.MAX_SAFE_INTEGER" in DIFF_VIEWER_SOURCE


def test_web_frontend_contains_mobile_overflow_guards():
    assert "overflow-x: hidden;" in WEB_FRONTEND_SOURCE
    assert "--app-height: 100dvh;" in WEB_FRONTEND_SOURCE
    assert "min-height: var(--app-height);" in WEB_FRONTEND_SOURCE
    assert "const prefersCompactDiff = () => window.matchMedia('(max-width: 767px)').matches;" in WEB_FRONTEND_SOURCE
    assert "outputFormat: 'line-by-line'" in DIFF_VIEWER_SOURCE
    assert "synchronisedScroll: true" in DIFF_VIEWER_SOURCE


def test_web_frontend_wraps_markdown_tables_for_horizontal_scrolling():
    assert "wrapper.className = 'markdown-table-wrapper';" in WEB_FRONTEND_SOURCE
    assert ".markdown-table-wrapper {" in WEB_FRONTEND_SOURCE
    assert "width: max-content;" in WEB_FRONTEND_SOURCE


def test_web_frontend_uses_responsive_mobile_layout_classes():
    assert 'class="app-shell flex h-screen flex-row overflow-hidden"' in WEB_FRONTEND_SOURCE
    assert 'class="w-64 h-full bg-gray-50 border-r border-gray-200 flex flex-col hidden md:flex"' in WEB_FRONTEND_SOURCE
    assert '@click="showMobileSidebar = true" class="md:hidden' in WEB_FRONTEND_SOURCE
    assert 'v-if="showMobileSidebar" class="fixed inset-0 z-50 md:hidden"' in WEB_FRONTEND_SOURCE


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
    assert "diff-container" not in WEB_FRONTEND_SOURCE
    assert ".d2h-code-linenumber" not in WEB_FRONTEND_SOURCE
    assert ".d2h-code-line-prefix" not in WEB_FRONTEND_SOURCE
    assert ".cc-diff-viewer .d2h-file-header" in DIFF_VIEWER_CSS_SOURCE
    assert "height: 35px;" in DIFF_VIEWER_CSS_SOURCE
    assert ".cc-diff-viewer .d2h-file-wrapper" in DIFF_VIEWER_CSS_SOURCE
    assert "border: 1px solid var(--d2h-border-color);" in DIFF_VIEWER_CSS_SOURCE
    assert ".cc-diff-viewer .d2h-code-line del" in DIFF_VIEWER_CSS_SOURCE
    assert "background-color: var(--d2h-del-highlight-bg-color);" in DIFF_VIEWER_CSS_SOURCE
    assert "display: none !important;" not in DIFF_VIEWER_CSS_SOURCE
