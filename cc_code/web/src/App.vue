<template>
    <div class="app-shell">
        <div class="app-frame">
            <aside v-show="!isDesktopSidebarCollapsed" class="sidebar-panel hidden md:flex">
                <button
                    @click="openNewSessionModal"
                    :disabled="isStreaming"
                    class="primary-action"
                >
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                    </svg>
                    New Chat
                </button>

                <div class="sidebar-section-header">
                    <span>Recent Chats</span>
                    <span>{{ sessions.length }}</span>
                </div>

                <div class="sidebar-list">
                    <div v-if="sessionsLoading" class="sidebar-empty">Loading...</div>
                    <div v-else-if="sessions.length === 0" class="sidebar-empty sidebar-empty--muted">No chats yet</div>
                    <div v-else class="space-y-2">
                        <button
                            v-for="sess in sessions"
                            :key="sess.session_id"
                            @click="loadSession(sess.session_id)"
                            class="session-card"
                            :class="{ 'session-card--active': sess.session_id === sessionId }"
                        >
                            <div class="session-card__icon">
                                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                                </svg>
                            </div>
                            <div class="min-w-0 flex-1 text-left">
                                <div class="session-card__title">{{ sess.title || 'Untitled Chat' }}</div>
                                <div class="session-card__meta">{{ sess.message_count || 0 }} messages</div>
                            </div>
                        </button>
                    </div>
                </div>

                <div class="sidebar-footer">
                    <button
                        @click="showSettingsModal = true"
                        class="secondary-action secondary-action--ghost"
                    >
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h6M14 6h6M4 12h10M18 12h2M4 18h2M10 18h10"></path>
                            <circle cx="12" cy="6" r="2"></circle>
                            <circle cx="16" cy="12" r="2"></circle>
                            <circle cx="8" cy="18" r="2"></circle>
                        </svg>
                        Settings
                    </button>
                </div>
            </aside>

            <div class="main-panel">
                <header class="topbar">
                    <div class="topbar-left">
                        <button @click="showMobileSidebar = true" class="icon-button md:hidden" aria-label="Open chat list">
                            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                            </svg>
                        </button>
                        <button
                            @click="toggleDesktopSidebar"
                            class="icon-button topbar-sidebar-toggle hidden md:inline-flex"
                            :aria-label="isDesktopSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
                        >
                            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5v14"></path>
                                <path
                                    v-if="isDesktopSidebarCollapsed"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    stroke-width="2"
                                    d="M12 8l3 4-3 4"
                                ></path>
                                <path
                                    v-else
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    stroke-width="2"
                                    d="M16 8l-3 4 3 4"
                                ></path>
                            </svg>
                        </button>

                        <div class="relative model-selector" data-model-selector>
                            <button @click="showModelSelector = !showModelSelector" class="model-pill">
                                <span class="model-pill__value">{{ currentModelName || 'Choose a model' }}</span>
                                <svg class="model-pill__chevron h-4 w-4 text-slate-500 transition-transform" :class="{ 'rotate-180': showModelSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                                </svg>
                            </button>

                            <div v-if="showModelSelector" class="floating-menu model-menu absolute left-0 top-full z-50 mt-1.5">
                                <div class="floating-menu__body">
                                    <div v-if="modelsLoading" class="dropdown-empty">Loading...</div>
                                    <div v-else-if="models.length === 0" class="dropdown-empty">No models available</div>
                                    <div v-else class="space-y-1">
                                        <button
                                            v-for="model in models"
                                            :key="model.model_id"
                                            @click.stop="switchModel(model.model_id)"
                                            class="dropdown-item"
                                            :class="{ 'dropdown-item--active': model.model_id === currentModelId }"
                                        >
                                            <div class="min-w-0 flex-1 text-left">
                                                <div class="dropdown-item__title">{{ model.model_name }}</div>
                                                <div class="dropdown-item__meta">{{ model.model_id }}</div>
                                            </div>
                                            <span v-if="model.model_id === currentModelId" class="dropdown-badge">Active</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </header>

                <div class="conversation-surface">
                    <div ref="messagesContainer" class="messages-area" @scroll="handleMessagesScroll">
                        <div class="chat-container conversation-column">
                            <div v-if="messages.length === 0" class="welcome-stage">
                                <div class="welcome-card">
                                    <div class="welcome-icon">
                                        <svg class="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"></path>
                                        </svg>
                                    </div>
                                    <h2>What do you want to work on?</h2>
                                    <p>I can help you write code, debug issues, and explain concepts.</p>
                                </div>
                            </div>

                            <MessageItem
                                v-for="(msg, index) in messages"
                                :key="index"
                                :message="msg"
                                @toggle-collapse="toggleCollapse"
                            />

                            <div v-if="isTyping" class="message-row message-row--assistant fade-in">
                                <div class="assistant-avatar assistant-avatar--typing">
                                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                    </svg>
                                </div>
                                <div class="typing-bubble">
                                    <div class="typing-indicator flex gap-1.5">
                                        <span class="h-2 w-2 rounded-full"></span>
                                        <span class="h-2 w-2 rounded-full"></span>
                                        <span class="h-2 w-2 rounded-full"></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="composer-shell">
                        <div class="chat-container">
                            <form @submit.prevent="sendMessage">
                                <div class="composer-panel">
                                    <textarea
                                        ref="messageInput"
                                        v-model="inputText"
                                        rows="1"
                                        :placeholder="inputPlaceholder"
                                        class="composer-input"
                                        style="max-height: 168px; min-height: 44px;"
                                        @input="autoResize"
                                        @keydown="handleKeydown"
                                        :disabled="isStreaming"
                                    ></textarea>

                                    <div class="composer-footer">
                                        <div class="composer-footer__left">
                                            <button
                                                type="button"
                                                @click="webSearchEnabled = !webSearchEnabled"
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
                                            @click="sendInterrupt"
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
                                            @click="toggleWorkspaceDetails"
                                            class="status-chip"
                                        >
                                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                                            </svg>
                                            <span class="truncate max-w-[10rem]">{{ currentWorkspace ? currentWorkspace.split('/').pop() : 'No workspace' }}</span>
                                        </button>

                                        <div v-if="showWorkspaceDetails" data-info-popover class="meta-popover absolute bottom-full left-0 z-40 mb-2.5 w-72 max-w-[calc(100vw-2rem)]">
                                            <div class="meta-popover__header">
                                                <span>Workspace</span>
                                                <button @click="showWorkspaceDetails = false" class="meta-popover__close" aria-label="Close workspace details">
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
                                            @click="toggleTokenDetails"
                                            class="status-chip"
                                        >
                                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                                            </svg>
                                            <span>{{ formatTokens(tokenUsed) }} / {{ formatTokens(Number(currentModelContext) || 128000) }}</span>
                                        </button>

                                        <div v-if="showTokenDetails" data-info-popover class="meta-popover absolute bottom-full left-0 z-40 mb-2.5 w-72 max-w-[calc(100vw-2rem)]">
                                            <div class="meta-popover__header">
                                                <span>Token Usage</span>
                                                <button @click="showTokenDetails = false" class="meta-popover__close" aria-label="Close token details">
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
                                                    <strong>{{ formatTokens(Number(currentModelContext) || 128000) }}</strong>
                                                </div>
                                                <div class="token-stat">
                                                    <span>Remaining</span>
                                                    <strong>{{ formatTokens((Number(currentModelContext) || 128000) - tokenUsed) }}</strong>
                                                </div>
                                                <div class="token-meter">
                                                    <div
                                                        class="token-meter__fill"
                                                        :style="{ width: Math.min((tokenUsed / (Number(currentModelContext) || 128000)) * 100, 100) + '%' }"
                                                    ></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="showMobileSidebar" class="mobile-overlay md:hidden" @click="showMobileSidebar = false">
                <div class="mobile-overlay__backdrop"></div>
                <aside class="mobile-sidebar" @click.stop>
                    <div class="mobile-sidebar__header">
                        <div>
                            <div class="eyebrow">Sessions</div>
                            <div class="text-base font-semibold text-slate-900">Chat List</div>
                        </div>
                        <button @click="showMobileSidebar = false" class="icon-button" aria-label="Close chat list">
                            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>

                    <button
                        @click="openNewSessionModal(); showMobileSidebar = false"
                        :disabled="isStreaming"
                        class="primary-action"
                    >
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                        </svg>
                        New Chat
                    </button>

                    <div class="sidebar-list mt-4">
                        <div v-if="sessionsLoading" class="sidebar-empty">Loading...</div>
                        <div v-else-if="sessions.length === 0" class="sidebar-empty sidebar-empty--muted">No chats yet</div>
                        <div v-else class="space-y-2">
                            <button
                                v-for="sess in sessions"
                                :key="sess.session_id"
                                @click="loadSession(sess.session_id); showMobileSidebar = false"
                                class="session-card"
                                :class="{ 'session-card--active': sess.session_id === sessionId }"
                            >
                                <div class="session-card__icon">
                                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                                    </svg>
                                </div>
                                <div class="min-w-0 flex-1 text-left">
                                    <div class="session-card__title">{{ sess.title || 'Untitled Chat' }}</div>
                                    <div class="session-card__meta">{{ sess.message_count || 0 }} messages</div>
                                </div>
                            </button>
                        </div>
                    </div>

                    <div class="sidebar-footer mt-auto">
                        <button
                            @click="showSettingsModal = true; showMobileSidebar = false"
                            class="secondary-action secondary-action--ghost"
                        >
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h6M14 6h6M4 12h10M18 12h2M4 18h2M10 18h10"></path>
                                <circle cx="12" cy="6" r="2"></circle>
                                <circle cx="16" cy="12" r="2"></circle>
                                <circle cx="8" cy="18" r="2"></circle>
                            </svg>
                            Settings
                        </button>
                    </div>
                </aside>
            </div>

            <NewSessionModal
                v-if="showNewSessionModal"
                :workspace-browser-loading="workspaceBrowserLoading"
                :workspace-browser-error="workspaceBrowserError"
                :workspace-browser-path="workspaceBrowserPath"
                :workspace-browser-input="workspaceBrowserInput"
                :workspace-browser-parent-path="workspaceBrowserParentPath"
                :workspace-browser-directories="workspaceBrowserDirectories"
                :workspace-browser-roots="workspaceBrowserRoots"
                @close="closeNewSessionModal"
                @update:workspace-browser-input="workspaceBrowserInput = $event"
                @browse-workspace="browseWorkspace"
                @browse-workspace-parent="browseWorkspaceParent"
                @submit-workspace-browser-path="submitWorkspaceBrowserPath"
                @start-new-session="startNewSession"
            />

            <SettingsModal
                v-if="showSettingsModal"
                :active-settings-tab="activeSettingsTab"
                :settings="settings"
                :settings-loading="settingsLoading"
                :selected-provider="selectedProvider"
                :available-models="availableModels"
                :selected-models="selectedModels"
                :current-provider="currentProvider"
                @close="showSettingsModal = false"
                @update:active-settings-tab="activeSettingsTab = $event"
                @update:selected-provider="selectedProvider = $event"
                @update:selected-models="selectedModels = $event"
                @fetch-provider-models="fetchProviderModels"
                @add-selected-models="addSelectedModels"
                @delete-model="deleteModel"
                @save-settings="saveSettings"
            />
        </div>
    </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import MessageItem from './components/MessageItem.vue'
import SettingsModal from './components/settings/SettingsModal.vue'
import NewSessionModal from './components/workspace/NewSessionModal.vue'
import { useChat } from './composables/useChat'

const {
    messages,
    inputText,
    isLoading,
    isStreaming,
    isTyping,
    sessionId,
    tokenUsed,
    sessions,
    sessionsLoading,
    showMobileSidebar,
    showWorkspaceDetails,
    showTokenDetails,
    showModelSelector,
    models,
    modelsLoading,
    currentModelId,
    currentModelName,
    currentModelContext,
    currentWorkspace,
    showNewSessionModal,
    webSearchEnabled,
    sessionHasUsedWebSearch,
    workspaceBrowserLoading,
    workspaceBrowserError,
    workspaceBrowserPath,
    workspaceBrowserInput,
    workspaceBrowserParentPath,
    workspaceBrowserDirectories,
    workspaceBrowserRoots,
    showSettingsModal,
    activeSettingsTab,
    settings,
    settingsLoading,
    selectedProvider,
    availableModels,
    selectedModels,
    currentProvider,
    inputPlaceholder,
    messagesContainer,
    messageInput,
    autoResize,
    handleMessagesScroll,
    handleKeydown,
    sendMessage,
    sendInterrupt,
    startNewSession,
    openNewSessionModal,
    closeNewSessionModal,
    browseWorkspace,
    browseWorkspaceParent,
    submitWorkspaceBrowserPath,
    loadSession,
    switchModel,
    toggleCollapse,
    scrollToBottom,
    formatTokens,
    getCurrentWorkspace,
    loadSessions,
    loadModels,
    toggleWorkspaceDetails,
    toggleTokenDetails,
    closeInfoPopovers,
    syncViewportMetrics,
    fetchProviderModels,
    addSelectedModels,
    deleteModel,
    saveSettings,
} = useChat()

const isDesktopSidebarCollapsed = ref(false)

const toggleDesktopSidebar = () => {
    isDesktopSidebarCollapsed.value = !isDesktopSidebarCollapsed.value
}

const getSelectedText = () => {
    const activeElement = document.activeElement
    if (
        activeElement &&
        typeof activeElement.selectionStart === 'number' &&
        typeof activeElement.selectionEnd === 'number' &&
        typeof activeElement.value === 'string'
    ) {
        const { selectionStart, selectionEnd, value } = activeElement
        if (selectionStart !== selectionEnd) {
            return value.slice(selectionStart, selectionEnd)
        }
    }
    return window.getSelection()?.toString() || ''
}

const copySelectedText = async (e) => {
    const selectedText = getSelectedText()
    if (!selectedText || !navigator.clipboard?.writeText) return false

    try {
        e.preventDefault()
        await navigator.clipboard.writeText(selectedText)
        return true
    } catch (error) {
        console.error('Copy failed:', error)
        return false
    }
}

const handleGlobalKeydown = async (e) => {
    const key = e.key.toLowerCase()
    const isCopyShortcut = (e.metaKey || e.ctrlKey) && key === 'c' && !e.altKey

    if (isCopyShortcut) {
        await copySelectedText(e)
        return
    }

    if (e.key === 'Escape') {
        if (showNewSessionModal.value) {
            closeNewSessionModal()
        } else if (showModelSelector.value) {
            showModelSelector.value = false
        } else if (showWorkspaceDetails.value || showTokenDetails.value) {
            closeInfoPopovers()
        } else if (isStreaming.value) {
            e.preventDefault()
            sendInterrupt()
        }
    }
}

const handleGlobalClick = (e) => {
    if (showModelSelector.value) {
        const modelSelector = document.querySelector('[data-model-selector]')
        if (modelSelector && !modelSelector.contains(e.target)) {
            showModelSelector.value = false
        }
    }

    const target = e.target
    if (
        (showWorkspaceDetails.value || showTokenDetails.value) &&
        target?.closest &&
        !target.closest('[data-info-popover]') &&
        !target.closest('[data-info-popover-trigger]')
    ) {
        closeInfoPopovers()
    }
}

watch(showModelSelector, (val) => {
    if (val) loadModels()
})

onMounted(() => {
    syncViewportMetrics()
    document.addEventListener('keydown', handleGlobalKeydown)
    document.addEventListener('click', handleGlobalClick)
    window.addEventListener('resize', syncViewportMetrics)
    window.visualViewport?.addEventListener('resize', syncViewportMetrics)
    window.visualViewport?.addEventListener('scroll', syncViewportMetrics)
    loadModels()
    getCurrentWorkspace()
    loadSessions()
    scrollToBottom(true)
})

onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleGlobalKeydown)
    document.removeEventListener('click', handleGlobalClick)
    window.removeEventListener('resize', syncViewportMetrics)
    window.visualViewport?.removeEventListener('resize', syncViewportMetrics)
    window.visualViewport?.removeEventListener('scroll', syncViewportMetrics)
})
</script>
