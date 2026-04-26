<template>
    <!-- User Message -->
    <div v-if="message.type === 'user'" class="flex justify-end fade-in">
        <div class="max-w-[85%] min-w-0">
            <div class="message-user max-w-full rounded-2xl rounded-tr-sm px-4 py-2">
                <p class="text-gray-900 whitespace-pre-wrap leading-relaxed">{{ message.text }}</p>
            </div>
        </div>
    </div>

    <!-- Assistant Message -->
    <div v-else-if="message.type === 'assistant'" class="flex justify-start fade-in w-full mb-0 -my-3">
        <div class="message-assistant min-w-0 flex-1 rounded-2xl rounded-tl-sm px-0 py-1 mb-0">
            <div class="assistant-content min-w-0 break-words mb-0">
                <template v-for="(block, idx) in message.content" :key="idx">
                    <div v-if="block.type === 'text'" class="text-container markdown-body min-w-0 break-words" v-html="renderMarkdown(block.text)"></div>
                    <div v-else-if="block.type === 'thinking'" class="text-gray-500 italic thinking-block whitespace-pre-wrap break-words">{{ block.thinking }}</div>
                    <div v-else-if="block.type === 'tool_block'" class="tool-block my-0.5 max-w-full rounded-lg p-2.5 bg-transparent border border-transparent">
                        <div class="collapsible-header flex items-center justify-between rounded -m-2.5 p-2.5" @click="$emit('toggle-collapse', block.collapseId)">
                            <div class="min-w-0 pr-3 text-sm font-medium tool-summary flex items-center gap-2 text-gray-700">
                                <span v-if="block.result">
                                    {{ block.isError ? '✗' : '✓' }}
                                </span>
                                {{ block.summary }}
                            </div>
                            <svg class="w-4 h-4 text-gray-400 collapse-icon" :class="{ rotated: block.expanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                            </svg>
                        </div>
                        <div :id="block.collapseId" class="collapsible-content" :class="{ expanded: block.expanded }">
                            <div v-if="block.result" class="mt-2 pt-2 border-t border-gray-200/50">
                                <div class="tool-result-area">
                                    <pre class="mono overflow-x-auto whitespace-pre-wrap rounded-lg bg-white p-3 text-xs text-gray-700 border border-gray-200">{{ resultPreview(block.result) }}</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-else-if="block.type === 'error'" class="text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 my-1 text-sm">
                        {{ block.error }}
                    </div>
                </template>
            </div>
        </div>
    </div>

    <!-- Diff Message -->
    <div v-else-if="message.type === 'diff'" class="diff-message fade-in w-full">
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

// Render diff after DOM update
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

// Watch for changes
watch(() => props.message, renderDiffBlock, { deep: true, immediate: true })
</script>
