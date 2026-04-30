<template>
    <div class="app-shell">
        <div class="app-frame">
            <AppSidebar
                :is-desktop-sidebar-collapsed="isDesktopSidebarCollapsed"
                :is-streaming="isStreaming"
                :sessions-loading="sessionsLoading"
                :sessions="sessions"
                :session-id="sessionId"
                @open-new-chat="openNewSessionModal"
                @select-session="loadSession"
                @open-settings="showSettingsModal = true"
            />

            <div class="main-panel">
                <ChatTopbar
                    :is-desktop-sidebar-collapsed="isDesktopSidebarCollapsed"
                    :show-model-selector="showModelSelector"
                    :models-loading="modelsLoading"
                    :models="models"
                    :current-model-id="currentModelId"
                    :current-model-name="currentModelName"
                    @open-mobile-sidebar="showMobileSidebar = true"
                    @toggle-desktop-sidebar="toggleDesktopSidebar"
                    @toggle-model-selector="showModelSelector = !showModelSelector"
                    @switch-model="switchModel"
                />

                <ConversationView
                    :messages="messages"
                    :is-typing="isTyping"
                    :messages-container-ref="bindMessagesContainer"
                    :handle-messages-scroll="handleMessagesScroll"
                    @toggle-collapse="toggleCollapse"
                />

                <ComposerPanel
                    :input-text="inputText"
                    :input-placeholder="inputPlaceholder"
                    :is-streaming="isStreaming"
                    :is-loading="isLoading"
                    :web-search-enabled="webSearchEnabled"
                    :current-workspace="currentWorkspace"
                    :show-workspace-details="showWorkspaceDetails"
                    :show-token-details="showTokenDetails"
                    :token-used="tokenUsed"
                    :current-model-context="currentModelContext"
                    :message-input-ref="bindMessageInput"
                    :auto-resize="autoResize"
                    :handle-keydown="handleKeydown"
                    :format-tokens="formatTokens"
                    @update:input-text="inputText = $event"
                    @update:web-search-enabled="webSearchEnabled = $event"
                    @send="sendMessage"
                    @interrupt="sendInterrupt"
                    @toggle-workspace-details="toggleWorkspaceDetails"
                    @toggle-token-details="toggleTokenDetails"
                    @close-workspace-details="showWorkspaceDetails = false"
                    @close-token-details="showTokenDetails = false"
                />
            </div>

            <MobileSidebar
                v-if="showMobileSidebar"
                :is-streaming="isStreaming"
                :sessions-loading="sessionsLoading"
                :sessions="sessions"
                :session-id="sessionId"
                @close="showMobileSidebar = false"
                @open-new-chat="handleOpenNewChatFromMobile"
                @select-session="handleSelectMobileSession"
                @open-settings="handleOpenSettingsFromMobile"
            />

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
import AppSidebar from './components/layout/AppSidebar.vue'
import MobileSidebar from './components/layout/MobileSidebar.vue'
import ChatTopbar from './components/chat/ChatTopbar.vue'
import ConversationView from './components/chat/ConversationView.vue'
import ComposerPanel from './components/chat/ComposerPanel.vue'
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

const bindMessagesContainer = (element) => {
    messagesContainer.value = element
}

const bindMessageInput = (element) => {
    messageInput.value = element
}

const handleOpenNewChatFromMobile = () => {
    showMobileSidebar.value = false
    openNewSessionModal()
}

const handleSelectMobileSession = (targetSessionId) => {
    showMobileSidebar.value = false
    loadSession(targetSessionId)
}

const handleOpenSettingsFromMobile = () => {
    showMobileSidebar.value = false
    showSettingsModal.value = true
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
