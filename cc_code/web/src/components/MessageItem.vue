<template>
    <div v-if="message.type === 'user'" class="message-row message-row--user fade-in">
        <div class="message-user-wrap">
            <div class="message-user-bubble">
                <p>{{ message.text }}</p>
            </div>
        </div>
    </div>

    <div v-else-if="message.type === 'assistant'" class="message-row message-row--assistant fade-in">
        <div class="assistant-avatar">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.9" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M4 13h16M6 17h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v9a2 2 0 002 2z"></path>
            </svg>
        </div>

        <div class="assistant-column">
            <div class="assistant-content">
                <template v-for="(block, idx) in message.content" :key="idx">
                    <div
                        v-if="block.type === 'text'"
                        class="text-container markdown-body"
                        v-html="renderMarkdown(block.text)"
                    ></div>

                    <div v-else-if="block.type === 'thinking'" class="thinking-block">
                        <div class="thinking-block__body">{{ block.thinking }}</div>
                    </div>

                    <div v-else-if="block.type === 'tool_block'" class="tool-block" :class="toolBlockClasses(block)">
                        <div class="tool-header" @click="$emit('toggle-collapse', block.collapseId)">
                            <div class="tool-header__main">
                                <span class="tool-badge" :class="toolBadgeClass(block.toolName)">{{ toolBadgeLabel(block.toolName) }}</span>
                                <div class="tool-title-group">
                                    <div class="tool-summary">{{ block.summary }}</div>
                                    <div class="tool-subtitle">
                                        <span :class="['tool-state', block.result ? (block.isError ? 'tool-state--error' : 'tool-state--success') : 'tool-state--pending']"></span>
                                        {{ block.result ? (block.isError ? 'Failed' : 'Done') : 'Running' }}
                                    </div>
                                </div>
                            </div>
                            <svg class="collapse-icon h-4 w-4" :class="{ rotated: block.expanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                            </svg>
                        </div>

                        <div :id="block.collapseId" class="collapsible-content" :class="{ expanded: block.expanded }">
                            <pre v-if="block.result" class="tool-result-frame mono">{{ resultPreview(block.result) }}</pre>
                        </div>
                    </div>

                    <div v-else-if="block.type === 'error'" class="error-block">
                        {{ block.error }}
                    </div>
                </template>
            </div>
        </div>
    </div>

    <div v-else-if="message.type === 'diff'" class="diff-message fade-in">
        <div class="diff-message__header">
            <span class="diff-message__label">Diff</span>
            <span class="diff-message__path">{{ message.filePath }}</span>
        </div>
        <div :id="message.diffId" class="cc-diff-viewer"></div>
    </div>
</template>

<script setup>
import { watch, nextTick } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { renderDiff } from '@/utils/diffViewer'
import { getNonEmptyLines } from '@/utils/format'

const props = defineProps({
    message: {
        type: Object,
        required: true
    }
})

defineEmits(['toggle-collapse'])

const resultPreview = (result) => {
    const lines = getNonEmptyLines(result)
    const preview = lines.slice(0, 6).join('\n')
    return preview + (lines.length > 6 ? '\n...' : '')
}

const toolKind = (toolName = '') => {
    const normalized = toolName.toLowerCase()
    if (['edit', 'write'].includes(normalized)) return 'patch'
    if (normalized === 'read') return 'read'
    if (normalized === 'bash') return 'run'
    if (['grep', 'glob'].includes(normalized)) return 'search'
    return 'default'
}

const toolBadgeLabel = (toolName = '') => {
    const normalized = toolName.toLowerCase()
    if (normalized === 'bash') return 'RUN'
    if (normalized === 'read') return 'READ'
    if (normalized === 'edit') return 'EDIT'
    if (normalized === 'write') return 'WRITE'
    if (normalized === 'grep') return 'GREP'
    if (normalized === 'glob') return 'GLOB'
    return (toolName || 'TOOL').slice(0, 6).toUpperCase()
}

const toolBadgeClass = (toolName = '') => `tool-badge--${toolKind(toolName)}`

const toolBlockClasses = (block) => [
    `tool-block--${toolKind(block.toolName)}`,
    {
        'tool-block--error': block.isError,
        'tool-block--pending': !block.result
    }
]

const renderDiffBlock = () => {
    nextTick(() => {
        if (props.message.type === 'diff' && props.message.diffData) {
            const container = document.getElementById(props.message.diffId)
            if (container && !container.hasChildNodes()) {
                try {
                    renderDiff(container, props.message.diffData)
                } catch (e) {
                    console.error('Diff render error:', e)
                }
            }
        }
    })
}

watch(() => props.message, renderDiffBlock, { deep: true, immediate: true })
</script>

<style scoped>
.message-row {
    display: flex;
    gap: 10px;
    margin-bottom: 7px;
    min-width: 0;
}

.message-row--user {
    justify-content: flex-end;
}

.message-row--assistant {
    align-items: flex-start;
}

.message-user-wrap {
    max-width: min(74%, 720px);
}

.message-user-bubble {
    padding: 8px 11px;
    border-radius: var(--radius-md);
    background: var(--accent-soft);
}

.message-user-bubble p {
    margin: 0;
    color: var(--text-strong);
    white-space: pre-wrap;
    line-height: 1.64;
    overflow-wrap: anywhere;
}

.assistant-avatar {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    color: #475569;
    background: #f1f5f9;
    border: 1px solid var(--border-subtle);
    flex-shrink: 0;
}

.assistant-column {
    min-width: 0;
    flex: 1;
}

.assistant-content {
    min-width: 0;
    max-width: min(100%, 900px);
    color: var(--text-main);
}

.assistant-content > * + * {
    margin-top: 6px;
}

.text-container {
    font-size: 0.95rem;
    line-height: 1.64;
    color: var(--text-main);
}

.thinking-block {
    position: relative;
    padding: 8px 10px 8px 12px;
    border-left: 2px solid rgba(100, 116, 139, 0.24);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    background: #f8fafc;
}

.thinking-block__body {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.6;
    color: #5f6d82;
    font-style: italic;
}

.tool-block {
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-soft);
    border-left-width: 3px;
    background: #ffffff;
    overflow: hidden;
}

.tool-block--pending {
    border-color: rgba(15, 23, 42, 0.1);
    border-left-color: #94a3b8;
}

.tool-block--error {
    border-color: rgba(220, 38, 38, 0.18);
    border-left-color: var(--danger);
}

.tool-block--read {
    border-left-color: #64748b;
}

.tool-block--patch {
    border-left-color: var(--success);
}

.tool-block--run {
    border-left-color: var(--accent);
}

.tool-block--search {
    border-left-color: var(--warning);
}

.tool-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 10px;
    cursor: pointer;
}

.tool-header:hover {
    background: #f8fafc;
}

.tool-header__main {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    min-width: 0;
    flex: 1;
}

.tool-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 52px;
    height: 22px;
    border-radius: var(--radius-xs);
    padding: 0 7px;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.04em;
}

.tool-badge--read {
    background: #f1f5f9;
    color: #4f5b6c;
}

.tool-badge--patch {
    background: rgba(15, 159, 110, 0.12);
    color: var(--success);
}

.tool-badge--run {
    background: var(--accent-soft);
    color: var(--accent-strong);
}

.tool-badge--search {
    background: rgba(183, 110, 0, 0.12);
    color: var(--warning);
}

.tool-badge--default {
    background: rgba(100, 116, 139, 0.12);
    color: #475569;
}

.tool-title-group {
    min-width: 0;
    flex: 1;
    padding-top: 1px;
}

.tool-summary {
    color: var(--text-strong);
    font-size: 0.88rem;
    font-weight: 650;
    line-height: 1.3;
    overflow-wrap: anywhere;
}

.tool-subtitle {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-top: 2px;
    color: var(--text-muted);
    font-size: 0.74rem;
}

.tool-state {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    flex-shrink: 0;
}

.tool-state--pending {
    background: #94a3b8;
}

.tool-state--success {
    background: var(--success);
}

.tool-state--error {
    background: var(--danger);
}

.collapsible-content {
    max-height: 0;
    overflow: hidden;
    border-top: 1px solid transparent;
    transition: max-height 0.3s ease-out, border-top-color 0.3s ease-out;
}

.collapsible-content.expanded {
    max-height: 5000px;
    overflow: hidden;
    border-top-color: var(--border-subtle);
}

.collapse-icon {
    color: var(--text-faint);
    transition: transform 0.2s ease;
    flex-shrink: 0;
}

.collapse-icon.rotated {
    transform: rotate(90deg);
}

.tool-result-frame {
    margin: 0 10px 10px;
    padding: 9px 10px;
    overflow-x: auto;
    white-space: pre-wrap;
    color: #243041;
    line-height: 1.52;
}

.error-block {
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid rgba(220, 38, 38, 0.16);
    background: rgba(220, 38, 38, 0.08);
    color: #991b1b;
}

.diff-message {
    width: 100%;
    min-width: 0;
    padding: 0 0 8px 38px;
}

.diff-message__header {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    height: 30px;
    padding: 0 9px;
    border: 1px solid var(--border-soft);
    border-bottom: 0;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    background: #f8fafc;
}

.diff-message__label {
    display: inline-flex;
    align-items: center;
    height: 18px;
    padding: 0 6px;
    border-radius: var(--radius-xs);
    background: rgba(15, 159, 110, 0.1);
    color: var(--success);
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.diff-message__path {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-main);
    font-family: var(--font-mono);
    font-size: 0.75rem;
}

@media (max-width: 767px) {
    .message-row {
        gap: 10px;
    }

    .message-user-wrap {
        max-width: 92%;
    }

    .diff-message {
        padding-left: 0;
    }
}
</style>
