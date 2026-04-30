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
