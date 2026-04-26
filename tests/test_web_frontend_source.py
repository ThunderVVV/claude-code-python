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
VITE_APP_SOURCE = Path("cc_code/web/src/App.vue").read_text(encoding="utf-8")
VITE_MESSAGE_ITEM_SOURCE = Path("cc_code/web/src/components/MessageItem.vue").read_text(
    encoding="utf-8"
)
VITE_CHAT_SOURCE = Path("cc_code/web/src/composables/useChat.js").read_text(
    encoding="utf-8"
)
VITE_FORMAT_SOURCE = Path("cc_code/web/src/utils/format.js").read_text(
    encoding="utf-8"
)
VITE_MARKDOWN_SOURCE = Path("cc_code/web/src/utils/markdown.js").read_text(
    encoding="utf-8"
)
VITE_DIFF_VIEWER_SOURCE = Path("cc_code/web/src/utils/diffViewer.js").read_text(
    encoding="utf-8"
)
VITE_STYLE_SOURCE = Path("cc_code/web/src/style.css").read_text(encoding="utf-8")


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
    assert "@import 'highlight.js/styles/github.min.css';" in VITE_STYLE_SOURCE
    assert "@import 'diff2html/bundles/css/diff2html.min.css';" in VITE_STYLE_SOURCE
    assert "@import '../static/diff-viewer.css';" in VITE_STYLE_SOURCE
    assert "max-width: 64rem;" in VITE_STYLE_SOURCE
    assert 'class="messages-area flex-1 overflow-y-auto overflow-x-hidden"' in VITE_APP_SOURCE
    assert ".messages-area,\n.messages-area * {" in VITE_STYLE_SOURCE
    assert "font-size: var(--font-size-base) !important;" in VITE_STYLE_SOURCE
    assert "--font-size-code: 12px;" in VITE_STYLE_SOURCE
    assert ".messages-area code," in VITE_STYLE_SOURCE
    assert "font-size: var(--font-size-code) !important;" in VITE_STYLE_SOURCE
    assert 'class="chat-container py-6 space-y-1 px-4"' in VITE_APP_SOURCE
    assert 'class="composer-shell bg-white px-4 pb-6"' in VITE_APP_SOURCE
    assert "padding: 1rem 0 1.5rem;" in VITE_STYLE_SOURCE
    assert (
        'class="message-assistant min-w-0 flex-1 rounded-2xl '
        'rounded-tl-sm px-0 py-1 mb-0"'
    ) in VITE_MESSAGE_ITEM_SOURCE
    assert (
        'class="message-assistant min-w-0 flex-1 rounded-2xl '
        'rounded-tl-sm px-4 py-1 mb-0"'
    ) not in VITE_MESSAGE_ITEM_SOURCE
    assert 'class="cc-diff-viewer"' in VITE_MESSAGE_ITEM_SOURCE
    assert 'class="assistant-content min-w-0 break-words mb-0"' in VITE_MESSAGE_ITEM_SOURCE
    assert 'class="assistant-content markdown-body' not in VITE_MESSAGE_ITEM_SOURCE
    assert (
        'class="text-container markdown-body min-w-0 break-words"'
        in VITE_MESSAGE_ITEM_SOURCE
    )
    assert "message.type === 'diff'" in VITE_MESSAGE_ITEM_SOURCE
    assert 'class="diff-message fade-in w-full"' in VITE_MESSAGE_ITEM_SOURCE
    assert "appendDiffMessage(" in VITE_CHAT_SOURCE
    assert "const removeToolBlock = (assistantMessage, toolUseId) => {" in VITE_CHAT_SOURCE
    assert "if (blockIndex < 0) return false" in VITE_CHAT_SOURCE
    assert "removeToolBlock(targetMessage, block.tool_use_id)" in VITE_CHAT_SOURCE
    assert "const diffData = !block.is_error && isFileEditTool(toolName)" in VITE_CHAT_SOURCE
    assert "if (!targetMsg) continue" in VITE_CHAT_SOURCE
    assert "inputDetails" not in VITE_MESSAGE_ITEM_SOURCE
    assert 'v-html="block.inputDetails"' not in VITE_MESSAGE_ITEM_SOURCE
    assert "Object.entries(toolInput || {})" not in VITE_CHAT_SOURCE
    assert "renderDiff(container, props.message.diffData)" in VITE_MESSAGE_ITEM_SOURCE
    assert "block.diffData" not in VITE_MESSAGE_ITEM_SOURCE
    assert "DIFF_HIGHLIGHT_LANGUAGES" not in VITE_DIFF_VIEWER_SOURCE
    assert "langPrefix: 'hljs language-'" in VITE_MARKDOWN_SOURCE
    assert "drawFileList: false" in VITE_DIFF_VIEWER_SOURCE
    assert "fileListToggle: false" in VITE_DIFF_VIEWER_SOURCE
    assert "drawFileList: true" not in VITE_DIFF_VIEWER_SOURCE
    assert (
        "container.querySelectorAll('.d2h-file-list-wrapper').forEach((element) => {"
        in VITE_DIFF_VIEWER_SOURCE
    )
    assert "element.remove()" in VITE_DIFF_VIEWER_SOURCE
    assert "matching: 'words'" in VITE_DIFF_VIEWER_SOURCE
    assert "outputFormat: 'line-by-line'" in VITE_DIFF_VIEWER_SOURCE
    assert "highlightLanguages: HIGHLIGHT_LANGUAGES" in VITE_DIFF_VIEWER_SOURCE
    assert "py: 'python'" in VITE_DIFF_VIEWER_SOURCE
    assert "html: 'xml'" in VITE_DIFF_VIEWER_SOURCE
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
    assert "@import 'highlight.js/styles/github.min.css';" in VITE_STYLE_SOURCE


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


def test_vite_diff_viewer_passes_highlightjs_to_diff2html_base():
    assert "@import 'highlight.js/styles/github.min.css';" in VITE_STYLE_SOURCE
    assert (
        "import { Diff2HtmlUI } from 'diff2html/lib/ui/js/diff2html-ui-base'"
        in VITE_DIFF_VIEWER_SOURCE
    )
    assert "import hljs from 'highlight.js'" in VITE_DIFF_VIEWER_SOURCE
    assert (
        "new Diff2HtmlUI(\n        container,\n        diffData,"
        in VITE_DIFF_VIEWER_SOURCE
    )
    assert "\n        hljs\n    )" in VITE_DIFF_VIEWER_SOURCE
    assert "hljs: hljs" not in VITE_DIFF_VIEWER_SOURCE


def test_web_frontend_contains_mobile_overflow_guards():
    assert "overflow-x: hidden;" in VITE_STYLE_SOURCE
    assert "min-height: var(--app-height);" in VITE_STYLE_SOURCE
    assert (
        "export const prefersCompactDiff = () => "
        "window.matchMedia('(max-width: 767px)').matches"
    ) in VITE_FORMAT_SOURCE
    assert "outputFormat: 'line-by-line'" in VITE_DIFF_VIEWER_SOURCE
    assert "synchronisedScroll: true" in VITE_DIFF_VIEWER_SOURCE


def test_web_frontend_wraps_markdown_tables_for_horizontal_scrolling():
    assert "wrapper.className = 'markdown-table-wrapper'" in VITE_MARKDOWN_SOURCE
    assert ".markdown-table-wrapper {" in VITE_STYLE_SOURCE
    assert "overflow-x: auto;" in VITE_STYLE_SOURCE


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
    assert "font-size: 16px !important;" in VITE_STYLE_SOURCE


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
