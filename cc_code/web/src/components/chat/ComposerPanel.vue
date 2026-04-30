<template>
    <div class="composer-shell">
        <div class="chat-container">
            <form @submit.prevent="$emit('send')">
                <div class="composer-panel">
                    <textarea
                        :ref="messageInputRef"
                        :value="inputText"
                        rows="1"
                        :placeholder="inputPlaceholder"
                        class="composer-input"
                        style="max-height: 168px; min-height: 44px;"
                        @input="handleInput"
                        @keydown="handleKeydown"
                        :disabled="isStreaming"
                    ></textarea>

                    <div class="composer-footer">
                        <div class="composer-footer__left">
                            <button
                                type="button"
                                @click="toggleWebSearch"
                                class="feature-toggle"
                                :class="{ 'feature-toggle--active': webSearchEnabled }"
                                :disabled="isStreaming"
                            >
                                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path>
                                </svg>
                                Web Search
                            </button>
                        </div>

                        <button
                            v-if="!isStreaming"
                            type="submit"
                            :disabled="isLoading || !inputText.trim()"
                            class="send-button"
                        >
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                            </svg>
                            Send
                        </button>
                        <button
                            v-else
                            type="button"
                            @click="$emit('interrupt')"
                            class="stop-button"
                        >
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path>
                            </svg>
                            Stop
                        </button>
                    </div>
                </div>
            </form>

            <div class="composer-status-row">
                <div class="composer-status-group">
                    <div class="relative">
                        <button
                            data-info-popover-trigger
                            @click="$emit('toggle-workspace-details')"
                            class="status-chip"
                        >
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                            </svg>
                            <span class="truncate max-w-[10rem]">{{ workspaceLabel }}</span>
                        </button>

                        <div v-if="showWorkspaceDetails" data-info-popover class="meta-popover absolute bottom-full left-0 z-40 mb-2.5 w-72 max-w-[calc(100vw-2rem)]">
                            <div class="meta-popover__header">
                                <span>Workspace</span>
                                <button @click="$emit('close-workspace-details')" class="meta-popover__close" aria-label="Close workspace details">
                                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                    </svg>
                                </button>
                            </div>
                            <div class="meta-popover__body font-mono text-xs">{{ currentWorkspace || 'No workspace' }}</div>
                        </div>
                    </div>

                    <div class="relative">
                        <button
                            data-info-popover-trigger
                            @click="$emit('toggle-token-details')"
                            class="status-chip"
                        >
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                            <span>{{ formatTokens(tokenUsed) }} / {{ formatTokens(contextLimit) }}</span>
                        </button>

                        <div v-if="showTokenDetails" data-info-popover class="meta-popover absolute bottom-full left-0 z-40 mb-2.5 w-72 max-w-[calc(100vw-2rem)]">
                            <div class="meta-popover__header">
                                <span>Token Usage</span>
                                <button @click="$emit('close-token-details')" class="meta-popover__close" aria-label="Close token details">
                                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                    </svg>
                                </button>
                            </div>
                            <div class="meta-popover__body token-popover-body">
                                <div class="token-stat">
                                    <span>Used</span>
                                    <strong>{{ formatTokens(tokenUsed) }}</strong>
                                </div>
                                <div class="token-stat">
                                    <span>Context Window</span>
                                    <strong>{{ formatTokens(contextLimit) }}</strong>
                                </div>
                                <div class="token-stat">
                                    <span>Remaining</span>
                                    <strong>{{ formatTokens(Math.max(contextLimit - tokenUsed, 0)) }}</strong>
                                </div>
                                <div class="token-meter">
                                    <div
                                        class="token-meter__fill"
                                        :style="{ width: Math.min((tokenUsed / contextLimit) * 100, 100) + '%' }"
                                    ></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
    inputText: {
        type: String,
        required: true,
    },
    inputPlaceholder: {
        type: String,
        required: true,
    },
    isStreaming: {
        type: Boolean,
        required: true,
    },
    isLoading: {
        type: Boolean,
        required: true,
    },
    webSearchEnabled: {
        type: Boolean,
        required: true,
    },
    currentWorkspace: {
        type: String,
        default: '',
    },
    showWorkspaceDetails: {
        type: Boolean,
        required: true,
    },
    showTokenDetails: {
        type: Boolean,
        required: true,
    },
    tokenUsed: {
        type: Number,
        required: true,
    },
    currentModelContext: {
        type: [String, Number],
        default: 128000,
    },
    messageInputRef: {
        type: Function,
        required: true,
    },
    autoResize: {
        type: Function,
        required: true,
    },
    handleKeydown: {
        type: Function,
        required: true,
    },
    formatTokens: {
        type: Function,
        required: true,
    },
})

const emit = defineEmits([
    'update:input-text',
    'update:web-search-enabled',
    'send',
    'interrupt',
    'toggle-workspace-details',
    'toggle-token-details',
    'close-workspace-details',
    'close-token-details',
])

const contextLimit = computed(() => Number(props.currentModelContext) || 128000)
const workspaceLabel = computed(() => props.currentWorkspace?.split('/').pop() || 'No workspace')

const handleInput = (event) => {
    emit('update:input-text', event.target.value)
    props.autoResize(event)
}

const toggleWebSearch = () => {
    emit('update:web-search-enabled', !props.webSearchEnabled)
}
</script>

<style scoped>
.composer-shell {
    padding: 0 16px 10px;
    margin-top: -1px;
    background: transparent;
}

.chat-container {
    width: min(100%, 1000px);
    margin: 0 auto;
}

.composer-panel {
    border: 1px solid rgba(143, 122, 100, 0.18);
    border-radius: var(--radius-md) var(--radius-md) var(--radius-lg) var(--radius-lg);
    padding: 8px 10px 9px;
    background: linear-gradient(180deg, #fffefb, #fcf8f1);
    box-shadow: var(--shadow-panel);
    backdrop-filter: blur(10px);
}

.composer-input {
    width: 100%;
    resize: none;
    border: none;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.84);
    color: #233042;
    padding: 10px 12px;
    font-size: 0.96rem;
    line-height: 1.5;
    box-shadow: inset 0 0 0 1px rgba(59, 66, 82, 0.07);
}

.composer-input::placeholder {
    color: #8d98a8;
}

.composer-input:focus {
    outline: none;
    box-shadow: inset 0 0 0 1px rgba(143, 122, 100, 0.16), 0 0 0 3px rgba(194, 179, 159, 0.1);
}

.composer-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding-top: 8px;
    margin-top: 6px;
    border-top: 1px solid rgba(59, 66, 82, 0.08);
}

.composer-footer__left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    flex-wrap: wrap;
}

.feature-toggle {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 34px;
    padding: 0 11px;
    border-radius: 999px;
    border: 1px solid var(--border-subtle);
    background: rgba(255, 255, 255, 0.96);
    color: var(--text-main);
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;
}

.feature-toggle--active {
    border-color: rgba(194, 179, 159, 0.16);
    background: #f4ede5;
    color: var(--text-strong);
}

.send-button,
.stop-button {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 40px;
    padding: 0 15px;
    border-radius: var(--radius-sm);
    font-weight: 700;
    cursor: pointer;
}

.send-button {
    background: linear-gradient(135deg, #cdb79c, #b99f81);
    color: #fffdf9;
    box-shadow: 0 10px 20px rgba(143, 122, 100, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.stop-button {
    background: #fee2e2;
    color: #991b1b;
}

.composer-status-row {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 8px;
    padding: 5px 0 0;
    flex-wrap: wrap;
    opacity: 0.98;
}

.composer-status-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.composer-status-group :deep(.status-chip) {
    background: #fffdfa;
}

.meta-popover {
    border: 1px solid var(--border-soft);
    border-radius: var(--radius-md);
    background: #ffffff;
    box-shadow: var(--shadow-float);
    padding-bottom: 6px;
}

.meta-popover__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    padding: 10px 10px 8px;
    border-bottom: 1px solid rgba(59, 66, 82, 0.08);
}

.meta-popover__header span {
    margin: 2px 0 0;
    color: var(--text-strong);
    font-size: 0.94rem;
    font-weight: 700;
}

.meta-popover__body {
    padding: 6px 8px 8px;
}

.meta-popover__close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 8px;
    color: var(--text-muted);
    cursor: pointer;
}

.meta-popover__close:hover {
    background: rgba(59, 66, 82, 0.08);
}

.token-popover-body {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.token-stat {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    color: var(--text-main);
    font-size: 0.82rem;
    padding: 0;
}

.token-stat strong {
    color: var(--text-strong);
}

.token-meter {
    width: 100%;
    height: 8px;
    border-radius: 999px;
    background: rgba(155, 128, 96, 0.14);
    overflow: hidden;
    margin-top: 4px;
}

.token-meter__fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #d5c4b1, #b89f81);
}

@media (max-width: 1024px) {
    .composer-shell {
        padding-left: 18px;
        padding-right: 18px;
    }
}

@media (max-width: 767px) {
    .composer-footer {
        flex-direction: column;
        align-items: stretch;
    }

    .status-chip,
    .send-button,
    .stop-button {
        justify-content: center;
    }

    .composer-shell {
        padding: 0 14px 18px;
    }

    .composer-panel {
        border-radius: 22px;
        padding: 12px 14px 14px;
    }

    .composer-input {
        font-size: 16px;
    }

    .composer-footer__left {
        width: 100%;
    }

    .feature-toggle,
    .send-button,
    .stop-button {
        width: 100%;
    }
}
</style>
