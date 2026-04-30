import { computed, nextTick, ref } from 'vue'
import { formatTokens, prefersCompactDiff, updateAppViewportHeight } from '@/utils/format'
import { createToolBlockManager } from '@/messageMapper/toolBlocks'
import { useChatStream } from './useChatStream'
import { useInputHistory } from './useInputHistory'
import { useModels } from './useModels'
import { useSessions } from './useSessions'
import { useSettings } from './useSettings'
import { useWorkspaceBrowser } from './useWorkspaceBrowser'

export function useChat() {
    const messages = ref([])
    const inputText = ref('')
    const isLoading = ref(false)
    const isStreaming = ref(false)
    const isTyping = ref(false)
    const sessionId = ref(null)
    const tokenUsed = ref(0)
    const autoFollowOutput = ref(true)
    const isCompactViewport = ref(prefersCompactDiff())
    const showMobileSidebar = ref(false)
    const showWorkspaceDetails = ref(false)
    const showTokenDetails = ref(false)
    const showModelSelector = ref(false)
    const webSearchEnabled = ref(false)
    const sessionHasUsedWebSearch = ref(false)
    const messagesContainer = ref(null)
    const messageInput = ref(null)

    const inputPlaceholder = computed(() => 'Message CC Code...')

    const isNearBottom = () => {
        if (!messagesContainer.value) return true
        const { scrollHeight, scrollTop, clientHeight } = messagesContainer.value
        return scrollHeight - scrollTop - clientHeight <= 24
    }

    const updateAutoFollowState = () => {
        autoFollowOutput.value = isNearBottom()
    }

    const scrollToBottom = (force = false) => {
        nextTick(() => {
            if (messagesContainer.value && (force || autoFollowOutput.value)) {
                messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
                autoFollowOutput.value = true
            }
        })
    }

    const handleMessagesScroll = () => {
        updateAutoFollowState()
    }

    const autoResize = (e) => {
        if (!e?.target) return
        e.target.style.height = 'auto'
        e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
    }

    const syncViewportMetrics = () => {
        updateAppViewportHeight()
        isCompactViewport.value = prefersCompactDiff()
    }

    const closeInfoPopovers = () => {
        showWorkspaceDetails.value = false
        showTokenDetails.value = false
    }

    const toggleWorkspaceDetails = () => {
        const nextState = !showWorkspaceDetails.value
        closeInfoPopovers()
        showWorkspaceDetails.value = nextState
    }

    const toggleTokenDetails = () => {
        const nextState = !showTokenDetails.value
        closeInfoPopovers()
        showTokenDetails.value = nextState
    }

    const toolBlocks = createToolBlockManager({ messages })
    const modelsState = useModels({ sessionId, showModelSelector })
    const workspaceState = useWorkspaceBrowser({
        isStreaming,
        showModelSelector,
        closeInfoPopovers,
    })
    const inputHistory = useInputHistory({
        inputText,
        messageInput,
        autoResize,
    })

    let sessionsState
    const chatStream = useChatStream({
        messages,
        inputText,
        isLoading,
        isStreaming,
        isTyping,
        sessionId,
        tokenUsed,
        autoFollowOutput,
        webSearchEnabled,
        sessionHasUsedWebSearch,
        currentWorkspace: workspaceState.currentWorkspace,
        serverWorkspace: workspaceState.serverWorkspace,
        messageInput,
        addToHistory: inputHistory.addToHistory,
        loadSessions: () => sessionsState.loadSessions(),
        scrollToBottom,
        toolBlocks,
    })

    sessionsState = useSessions({
        messages,
        sessionId,
        tokenUsed,
        sessionHasUsedWebSearch,
        currentWorkspace: workspaceState.currentWorkspace,
        serverWorkspace: workspaceState.serverWorkspace,
        autoFollowOutput,
        closeNewSessionModal: workspaceState.closeNewSessionModal,
        loadModels: modelsState.loadModels,
        resetStreamState: chatStream.resetStreamState,
        scrollToBottom,
        toolBlocks,
    })

    const settingsState = useSettings({
        loadModels: modelsState.loadModels,
    })

    const handleKeydown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            chatStream.sendMessage()
        } else if (e.key === 'Escape' && isStreaming.value) {
            e.preventDefault()
            chatStream.sendInterrupt()
        } else if (e.key === 'ArrowUp' && !e.shiftKey) {
            e.preventDefault()
            inputHistory.navigateHistory(-1)
        } else if (e.key === 'ArrowDown' && !e.shiftKey) {
            e.preventDefault()
            inputHistory.navigateHistory(1)
        }
    }

    return {
        messages,
        inputText,
        isLoading,
        isStreaming,
        isTyping,
        sessionId,
        tokenUsed,
        sessions: sessionsState.sessions,
        sessionsLoading: sessionsState.sessionsLoading,
        autoFollowOutput,
        isCompactViewport,
        showMobileSidebar,
        showWorkspaceDetails,
        showTokenDetails,
        showModelSelector,
        models: modelsState.models,
        modelsLoading: modelsState.modelsLoading,
        currentModelId: modelsState.currentModelId,
        currentModelName: modelsState.currentModelName,
        currentModelContext: modelsState.currentModelContext,
        currentWorkspace: workspaceState.currentWorkspace,
        showNewSessionModal: workspaceState.showNewSessionModal,
        webSearchEnabled,
        sessionHasUsedWebSearch,
        workspaceBrowserLoading: workspaceState.workspaceBrowserLoading,
        workspaceBrowserError: workspaceState.workspaceBrowserError,
        workspaceBrowserPath: workspaceState.workspaceBrowserPath,
        workspaceBrowserInput: workspaceState.workspaceBrowserInput,
        workspaceBrowserParentPath: workspaceState.workspaceBrowserParentPath,
        workspaceBrowserDirectories: workspaceState.workspaceBrowserDirectories,
        workspaceBrowserRoots: workspaceState.workspaceBrowserRoots,
        showSettingsModal: settingsState.showSettingsModal,
        activeSettingsTab: settingsState.activeSettingsTab,
        settings: settingsState.settings,
        settingsLoading: settingsState.settingsLoading,
        selectedProvider: settingsState.selectedProvider,
        availableModels: settingsState.availableModels,
        selectedModels: settingsState.selectedModels,
        currentProvider: settingsState.currentProvider,
        inputPlaceholder,
        messagesContainer,
        messageInput,

        autoResize,
        handleMessagesScroll,
        handleKeydown,
        sendMessage: chatStream.sendMessage,
        sendInterrupt: chatStream.sendInterrupt,
        startNewSession: sessionsState.startNewSession,
        openNewSessionModal: workspaceState.openNewSessionModal,
        closeNewSessionModal: workspaceState.closeNewSessionModal,
        browseWorkspace: workspaceState.browseWorkspace,
        browseWorkspaceParent: workspaceState.browseWorkspaceParent,
        submitWorkspaceBrowserPath: workspaceState.submitWorkspaceBrowserPath,
        loadSession: sessionsState.loadSession,
        switchModel: modelsState.switchModel,
        toggleCollapse: toolBlocks.toggleCollapse,
        scrollToBottom,
        formatTokens,
        getCurrentWorkspace: workspaceState.getCurrentWorkspace,
        loadSessions: sessionsState.loadSessions,
        loadModels: modelsState.loadModels,
        toggleWorkspaceDetails,
        toggleTokenDetails,
        closeInfoPopovers,
        syncViewportMetrics,
        updateAutoFollowState,
        fetchProviderModels: settingsState.fetchProviderModels,
        addSelectedModels: settingsState.addSelectedModels,
        deleteModel: settingsState.deleteModel,
        saveSettings: settingsState.saveSettings,
    }
}
