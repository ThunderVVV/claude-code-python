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
                                        {{ block.result ? (block.isError ? 'Failed' : 'Completed') : 'Waiting for result' }}
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
    gap: 12px;
    margin-bottom: 8px;
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
    padding: 10px 13px;
    border-radius: var(--radius-md) var(--radius-md) 9px var(--radius-md);
    background: #f7f2eb;
    border: 1px solid var(--border-interactive);
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
    border-radius: 11px;
    color: white;
    background: #b89f81;
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
    line-height: 1.68;
    color: #2f3d4f;
}

.thinking-block {
    position: relative;
    padding: 9px 11px 9px 13px;
    border-left: 2px solid rgba(194, 179, 159, 0.28);
    border-radius: 0 14px 14px 0;
    background: rgba(194, 179, 159, 0.09);
}

.thinking-block__body {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.6;
    color: #5f6d82;
    font-style: italic;
}

.tool-block {
    border-radius: var(--radius-md);
    border: 1px solid var(--border-soft);
    background: #fffefd;
    overflow: hidden;
}

.tool-block--pending {
    border-color: rgba(15, 23, 42, 0.1);
}

.tool-block--error {
    border-color: rgba(220, 38, 38, 0.18);
}

.tool-block--read,
.tool-block--patch,
.tool-block--run,
.tool-block--search {
    background: #ffffff;
}

.tool-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 12px;
    cursor: pointer;
}

.tool-header:hover {
    background: #fbf8f3;
}

.tool-header__main {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    min-width: 0;
    flex: 1;
}

.tool-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 52px;
    height: 24px;
    border-radius: 999px;
    padding: 0 8px;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.08em;
}

.tool-badge--read {
    background: rgba(194, 179, 159, 0.15);
    color: #4f5b6c;
}

.tool-badge--patch {
    background: rgba(15, 159, 110, 0.12);
    color: var(--success);
}

.tool-badge--run {
    background: rgba(194, 179, 159, 0.15);
    color: #6f5a45;
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
    font-weight: 680;
    line-height: 1.35;
    overflow-wrap: anywhere;
}

.tool-subtitle {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-top: 2px;
    color: #667487;
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
    transition: max-height 0.3s ease-out;
}

.collapsible-content.expanded {
    max-height: 5000px;
    overflow: visible;
    border-top: 1px solid rgba(194, 179, 159, 0.12);
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
    margin: 0 12px 12px;
    padding: 10px 11px;
    overflow-x: auto;
    white-space: pre-wrap;
    background: #fbf9f5;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: #243041;
    line-height: 1.6;
}

.error-block {
    padding: 14px 16px;
    border-radius: 18px;
    border: 1px solid rgba(220, 38, 38, 0.16);
    background: rgba(220, 38, 38, 0.08);
    color: #991b1b;
}

.diff-message {
    width: 100%;
    min-width: 0;
    padding: 0 0 4px 40px;
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
