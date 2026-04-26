import { ref, computed, nextTick } from 'vue'
import { formatTokens, hasWebReference, getNonEmptyLines, prefersCompactDiff, updateAppViewportHeight } from '@/utils/format'
import { createDiff } from '@/utils/diffViewer'

export function useChat() {
    // State
    const messages = ref([])
    const inputText = ref('')
    const isLoading = ref(false)
    const isStreaming = ref(false)
    const isTyping = ref(false)
    const sessionId = ref(null)
    const tokenUsed = ref(0)
    const sessions = ref([])
    const sessionsLoading = ref(false)
    const autoFollowOutput = ref(true)
    const isCompactViewport = ref(prefersCompactDiff())
    const showMobileSidebar = ref(false)
    const showWorkspaceDetails = ref(false)
    const showTokenDetails = ref(false)
    const showModelSelector = ref(false)
    const models = ref([])
    const modelsLoading = ref(false)
    const currentModelId = ref('')
    const currentModelName = ref('')
    const currentModelContext = ref('128000')
    const currentWorkspace = ref('')
    const webSearchEnabled = ref(false)
    const sessionHasUsedWebSearch = ref(false)

    // Input history
    const inputHistory = ref(JSON.parse(localStorage.getItem('inputHistory') || '[]'))
    const navItems = ref([])
    const historyIndex = ref(0)

    // Current streaming state
    const currentAssistantMessage = ref(null)
    const accumulatedText = ref('')
    const pendingToolUses = ref({})
    const toolUseCounter = ref(0)
    const diffMessageCounter = ref(0)

    // For aborting fetch request
    const abortController = ref(null)

    // Refs
    const messagesContainer = ref(null)
    const messageInput = ref(null)

    // Computed
    const inputPlaceholder = computed(() =>
        isCompactViewport.value ? '输入消息...' : '输入消息... (Shift+Enter 换行, ↑↓ 历史)'
    )

    // Methods
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
        e.target.style.height = 'auto'
        e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
    }

    const syncViewportMetrics = () => {
        updateAppViewportHeight()
        isCompactViewport.value = prefersCompactDiff()
    }

    const resetHistoryNavigation = () => {
        navItems.value = [...inputHistory.value, '']
        historyIndex.value = navItems.value.length - 1
    }

    const navigateHistory = (direction) => {
        if (navItems.value.length === 0) return

        navItems.value[historyIndex.value] = inputText.value

        historyIndex.value += direction
        historyIndex.value = Math.max(0, Math.min(historyIndex.value, navItems.value.length - 1))

        inputText.value = navItems.value[historyIndex.value] || ''
        nextTick(() => autoResize({ target: messageInput.value }))
    }

    const handleKeydown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            sendMessage()
        } else if (e.key === 'Escape' && isStreaming.value) {
            e.preventDefault()
            sendInterrupt()
        } else if (e.key === 'ArrowUp' && !e.shiftKey) {
            e.preventDefault()
            navigateHistory(-1)
        } else if (e.key === 'ArrowDown' && !e.shiftKey) {
            e.preventDefault()
            navigateHistory(1)
        }
    }

    const addToHistory = (text) => {
        if (text.trim() && (inputHistory.value.length === 0 || inputHistory.value[inputHistory.value.length - 1] !== text)) {
            inputHistory.value.push(text)
            if (inputHistory.value.length > 1000) inputHistory.value.shift()
            localStorage.setItem('inputHistory', JSON.stringify(inputHistory.value))
        }
        resetHistoryNavigation()
    }

    resetHistoryNavigation()

    const summarizeToolUse = (toolName, toolInput) => {
        if (!toolInput) return toolName
        if (toolInput.command) {
            const cmd = toolInput.command
            return `${toolName}: ${cmd.length > 50 ? cmd.substring(0, 47) + '...' : cmd}`
        }
        if (toolInput.file_path) {
            const path = toolInput.file_path
            const name = path.split('/').pop() || path
            return `${toolName}: ${name}`
        }
        if (toolInput.pattern) {
            const pat = toolInput.pattern
            return `${toolName}: ${pat.length > 50 ? pat.substring(0, 47) + '...' : pat}`
        }
        const keys = Object.keys(toolInput)
        if (keys.length > 0) {
            const preview = keys.slice(0, 3).join(', ')
            return `${toolName}: ${preview}${keys.length > 3 ? ', ...' : ''}`
        }
        return toolName
    }

    const summarizeToolResult = (toolName, toolInput, result, isError) => {
        const lines = getNonEmptyLines(result)
        const firstLine = lines[0] || ''

        const getBasename = () => (toolInput?.file_path || '').split('/').pop() || 'file'
        const getPattern = () => toolInput?.pattern ? `'${toolInput.pattern}'` : ''

        if (isError) {
            if (toolName === 'Bash') {
                const cmd = toolInput?.command || ''
                return `Failed to run ${cmd.length > 40 ? cmd.substring(0, 37) + '...' : cmd}`
            }
            if (['Read', 'Write', 'Edit'].includes(toolName)) return `Failed to ${toolName.toLowerCase()} ${getBasename()}`
            if (['Glob', 'Grep'].includes(toolName)) return `Failed to search ${getPattern()}`
            return `Failed to run ${toolName}`
        }

        if (toolName === 'Read') {
            const match = result?.match(/Lines:\s*(\d+)-(\d+)\s+of\s+(\d+)/)
            if (match) {
                const [, start, end, total] = match
                const count = parseInt(end) - parseInt(start) + 1
                return `Read ${count} line${count > 1 ? 's' : ''} from ${getBasename()} (${start}-${end} of ${total})`
            }
            return `Read ${getBasename()}`
        }

        if (toolName === 'Glob') {
            const pat = getPattern()
            if (firstLine.includes('No files found')) return `Glob found no files matching ${pat}`
            if (firstLine.startsWith('Found ')) return `Glob ${firstLine.charAt(0).toLowerCase()}${firstLine.slice(1)}`
            return `Glob results matching ${pat}`
        }

        if (toolName === 'Grep') {
            const pat = getPattern()
            if (firstLine === 'No matches found' || firstLine === 'No files found') return `Grep found no matches for ${pat}`
            if (firstLine.startsWith('Found ')) return `Grep ${firstLine.charAt(0).toLowerCase()}${firstLine.slice(1)}${pat ? ` matching ${pat}` : ''}`
            return `Grep matches for ${pat}`
        }

        if (toolName === 'Write' || toolName === 'Edit') return firstLine || `${toolName} completed`
        if (toolName === 'Bash') {
            const cmd = toolInput?.command || ''
            return `Ran: ${cmd.length > 40 ? cmd.substring(0, 37) + '...' : cmd}`
        }

        return firstLine || `${toolName} completed`
    }

    const isFileEditTool = (toolName) => ['edit', 'write'].includes((toolName || '').toLowerCase())

    const createToolBlock = (toolName, toolInput, toolUseId, collapseId) => {
        const summary = summarizeToolUse(toolName, toolInput)
        const shouldExpand = isFileEditTool(toolName)

        return {
            type: 'tool_block',
            toolName,
            toolInput,
            toolUseId,
            collapseId,
            summary,
            expanded: shouldExpand,
            result: null,
            isError: false
        }
    }

    const generateDiffData = (toolName, toolInput, result) => {
        const normalizedToolName = (toolName || '').toLowerCase()

        if (normalizedToolName === 'edit') {
            const oldString = toolInput.old_string || ''
            const newString = toolInput.new_string || ''
            const filePath = toolInput.file_path || 'file'

            if (oldString && newString) {
                return createDiff(oldString, newString, filePath)
            }
        } else if (normalizedToolName === 'write') {
            const content = toolInput.content || ''
            const filePath = toolInput.file_path || 'file'

            if (content) {
                return createDiff('', content, filePath)
            }
        }
        return null
    }

    const createDiffMessage = (diffData, toolName, toolInput) => ({
        type: 'diff',
        diffId: `diff-message-${++diffMessageCounter.value}`,
        diffData,
        toolName,
        filePath: toolInput?.file_path || 'file'
    })

    // Update tool block with result
    const updateToolBlockResult = (targetMessage, block, toolName, toolInput) => {
        const diffData = !block.is_error && isFileEditTool(toolName)
            ? generateDiffData(toolName, toolInput, block.result)
            : null

        if (diffData) {
            appendDiffMessage(diffData, toolName, toolInput, targetMessage)
            if (removeToolBlock(targetMessage, block.tool_use_id)) {
                return null
            }
        } else {
            const toolBlock = targetMessage.content.find(
                b => b.type === 'tool_block' && b.toolUseId === block.tool_use_id
            )
            if (toolBlock) {
                toolBlock.result = block.result
                toolBlock.isError = block.is_error
                toolBlock.summary = summarizeToolResult(toolName, toolInput, block.result, block.is_error)
            }
        }
        return targetMessage
    }

    const appendDiffMessage = (diffData, toolName, toolInput, afterMessage = null) => {
        if (!diffData) return null

        const diffMessage = createDiffMessage(diffData, toolName, toolInput)
        const targetMessage = afterMessage || currentAssistantMessage.value
        const targetIndex = targetMessage ? messages.value.indexOf(targetMessage) : -1

        if (targetIndex >= 0) {
            messages.value.splice(targetIndex + 1, 0, diffMessage)
        } else {
            messages.value.push(diffMessage)
        }

        return diffMessage
    }

    const removeMessageIfEmpty = (message) => {
        if (message?.type !== 'assistant' || message.content?.length) return false

        const messageIndex = messages.value.indexOf(message)
        if (messageIndex >= 0) {
            messages.value.splice(messageIndex, 1)
        }
        if (currentAssistantMessage.value === message) {
            currentAssistantMessage.value = null
        }
        return true
    }

    const removeToolBlock = (assistantMessage, toolUseId) => {
        if (!assistantMessage?.content) return false

        const blockIndex = assistantMessage.content.findIndex(
            block => block.type === 'tool_block' && block.toolUseId === toolUseId
        )
        if (blockIndex < 0) return false

        assistantMessage.content.splice(blockIndex, 1)
        return removeMessageIfEmpty(assistantMessage)
    }

    const createUserMessage = (text, options = {}) => ({
        type: 'user',
        text,
        originalText: options.originalText || text,
        fileExpansions: options.fileExpansions || [],
        webEnabled: options.webEnabled ?? hasWebReference(options.originalText || text)
    })

    const applyServerUserMessage = (message) => {
        const originalText = message.original_text || ''
        const updatedMessage = createUserMessage(originalText, {
            originalText,
            fileExpansions: message.file_expansions || [],
            webEnabled: Boolean(message.web_enabled)
        })

        const lastMessage = messages.value[messages.value.length - 1]
        if (lastMessage?.type === 'user') {
            messages.value[messages.value.length - 1] = updatedMessage
        } else {
            messages.value.push(updatedMessage)
        }
    }

    const toggleCollapse = (collapseId) => {
        for (const msg of messages.value) {
            if (msg.content) {
                for (const block of msg.content) {
                    if (block.type === 'tool_block' && block.collapseId === collapseId) {
                        block.expanded = !block.expanded
                        return
                    }
                }
            }
        }
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

    const handleEvent = (data) => {
        if (data.type === 'session_id') {
            sessionId.value = data.session_id
            return
        }

        if (data.type === 'message_complete') {
            if (data.message?.role === 'user') {
                applyServerUserMessage(data.message)
            } else if (data.message?.role === 'assistant' && data.message?.usage) {
                tokenUsed.value = data.message.usage.input_tokens + data.message.usage.output_tokens
            }
            scrollToBottom()
            return
        }

        if (data.type === 'turn_complete') {
            currentAssistantMessage.value = null
            accumulatedText.value = ''
            pendingToolUses.value = {}
            scrollToBottom()
            loadModels()
            return
        }

        isTyping.value = false

        if (!currentAssistantMessage.value) {
            currentAssistantMessage.value = {
                type: 'assistant',
                content: []
            }
            messages.value.push(currentAssistantMessage.value)
        }

        const content = currentAssistantMessage.value.content

        if (data.type === 'text') {
            accumulatedText.value += data.text
            let textBlock = content.find(b => b.type === 'text')
            if (!textBlock) {
                textBlock = { type: 'text', text: '' }
                content.push(textBlock)
            }
            textBlock.text = accumulatedText.value
        } else if (data.type === 'thinking') {
            const lastBlock = content[content.length - 1]
            if (lastBlock?.type === 'thinking') {
                lastBlock.thinking += data.thinking
            } else {
                content.push({ type: 'thinking', thinking: data.thinking })
            }
        } else if (data.type === 'tool_use') {
            const existingBlock = content.find(b => b.type === 'tool_block' && b.toolUseId === data.tool_use_id)

            pendingToolUses.value[data.tool_use_id] = {
                tool_name: data.tool_name,
                input: data.input
            }

            if (!existingBlock) {
                const collapseId = `tool-collapse-${++toolUseCounter.value}`
                const toolBlock = createToolBlock(data.tool_name, data.input, data.tool_use_id, collapseId)
                content.push(toolBlock)
            }
        } else if (data.type === 'tool_result') {
            const toolInfo = pendingToolUses.value[data.tool_use_id]
            const toolName = toolInfo?.tool_name || data.tool_name
            const toolInput = toolInfo?.input || {}
            const block = { tool_use_id: data.tool_use_id, result: data.result, is_error: data.is_error }

            updateToolBlockResult(currentAssistantMessage.value, block, toolName, toolInput)
            if (toolInfo) delete pendingToolUses.value[data.tool_use_id]
        } else if (data.type === 'error') {
            content.push({
                type: 'error',
                error: data.error
            })
        }

        scrollToBottom()
    }

    const sendMessage = async () => {
        let text = inputText.value.trim()
        if (!text || isLoading.value) return

        if (webSearchEnabled.value && !sessionHasUsedWebSearch.value) {
            text = '@web ' + text
            sessionHasUsedWebSearch.value = true
        }

        addToHistory(text)
        messages.value.push(createUserMessage(text))

        inputText.value = ''
        if (messageInput.value) {
            messageInput.value.style.height = 'auto'
        }

        isLoading.value = true
        isStreaming.value = true
        isTyping.value = true
        accumulatedText.value = ''

        abortController.value = new AbortController()

        autoFollowOutput.value = true
        scrollToBottom(true)

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId.value,
                    user_text: text
                }),
                signal: abortController.value.signal
            })

            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    try {
                        const data = JSON.parse(line.slice(6))
                        handleEvent(data)
                    } catch (err) {
                        console.error('Parse error:', err)
                    }
                }
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                // Request aborted
            } else {
                console.error('Chat error:', error)
            }
        } finally {
            isLoading.value = false
            isStreaming.value = false
            isTyping.value = false
            abortController.value = null
        }
    }

    const sendInterrupt = async () => {
        if (!abortController.value) return

        try {
            abortController.value.abort()

            if (sessionId.value) {
                await fetch('/api/interrupt', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionId.value,
                        reason: 'user_interrupt'
                    })
                })
            }

            currentAssistantMessage.value = null
            accumulatedText.value = ''
            pendingToolUses.value = {}
        } catch (error) {
            console.error('Interrupt error:', error)
        }
    }

    const getCurrentWorkspace = async () => {
        try {
            const response = await fetch('/api/workspace')
            const data = await response.json()
            if (data.workspace) {
                currentWorkspace.value = data.workspace
            }
        } catch (error) {
            console.error('Failed to get current workspace:', error)
        }
    }

    const startNewSession = () => {
        messages.value = []
        sessionId.value = null
        accumulatedText.value = ''
        tokenUsed.value = 0
        autoFollowOutput.value = true
        sessionHasUsedWebSearch.value = false
        loadModels()
        getCurrentWorkspace()
    }

    const loadSessions = async () => {
        sessionsLoading.value = true
        try {
            const response = await fetch('/api/sessions')
            const data = await response.json()
            sessions.value = data.sessions || []
        } catch (error) {
            console.error('Failed to load sessions:', error)
        } finally {
            sessionsLoading.value = false
        }
    }

    const loadModels = async () => {
        modelsLoading.value = true
        try {
            const response = await fetch('/api/models')
            const data = await response.json()
            models.value = data.models || []
            currentModelId.value = data.current_model || ''

            const currentModel = models.value.find(m => m.model_id === currentModelId.value)
            currentModelName.value = currentModel ? currentModel.model_name : ''
            currentModelContext.value = currentModel ? currentModel.context.toLocaleString() : '128000'
        } catch (error) {
            console.error('Failed to load models:', error)
        } finally {
            modelsLoading.value = false
        }
    }

    const ensureSession = async () => {
        if (!sessionId.value) {
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: '',
                        user_text: '',
                        working_directory: ''
                    })
                })

                const reader = response.body.getReader()
                const decoder = new TextDecoder()
                let buffer = ''

                while (true) {
                    const { done, value } = await reader.read()
                    if (done) break

                    buffer += decoder.decode(value, { stream: true })
                    const lines = buffer.split('\n\n')
                    buffer = lines.pop() || ''

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6))
                                if (data.type === 'session_id') {
                                    sessionId.value = data.session_id
                                    return true
                                }
                            } catch (e) {
                                console.error('Failed to parse SSE data:', e)
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('Failed to create session:', error)
                return false
            }
        }
        return true
    }

    const switchModel = async (modelId) => {
        const hasSession = await ensureSession()
        if (!hasSession) {
            return
        }

        if (modelId === currentModelId.value) {
            showModelSelector.value = false
            return
        }

        try {
            const response = await fetch('/api/model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId.value,
                    model_id: modelId
                })
            })

            const data = await response.json()

            if (data.success) {
                currentModelId.value = modelId
                currentModelName.value = data.model_name
                currentModelContext.value = data.context ? data.context.toLocaleString() : '128000'
                showModelSelector.value = false
                loadModels()
            } else {
                throw new Error(data.detail || 'Failed to switch model')
            }
        } catch (error) {
            console.error('Failed to switch model:', error)
        }
    }

    const loadSession = async (sid) => {
        messages.value = []
        sessionId.value = null
        sessionHasUsedWebSearch.value = false

        try {
            const response = await fetch(`/api/sessions/${sid}`)
            const data = await response.json()

            if (data.error) {
                alert('加载会话失败: ' + data.error)
                return
            }

            sessionId.value = sid

            if (data.messages && data.messages.length > 0) {
                let lastAssistantMsg = null
                const sessionToolUses = {}

                for (const msg of data.messages) {
                    if (msg.role === 'user') {
                        const fileExpansions = msg.file_expansions || []
                        const originalText = msg.original_text || ''
                        let displayText = ''

                        if (hasWebReference(originalText) || Boolean(msg.web_enabled)) {
                            sessionHasUsedWebSearch.value = true
                        }

                        if (msg.content_blocks) {
                            for (const block of msg.content_blocks) {
                                if (block.type === 'text') {
                                    displayText = block.text
                                    break
                                }
                            }
                        } else {
                            displayText = msg.content || ''
                        }

                        messages.value.push({
                            ...createUserMessage(originalText || displayText, {
                                originalText: originalText || displayText,
                                fileExpansions,
                                webEnabled: Boolean(msg.web_enabled)
                            })
                        })
                        lastAssistantMsg = null
                        Object.keys(sessionToolUses).forEach(key => delete sessionToolUses[key])
                    } else if (msg.role === 'assistant') {
                        const assistantMsg = {
                            type: 'assistant',
                            content: []
                        }

                        if (msg.content_blocks && msg.content_blocks.length > 0) {
                            for (const block of msg.content_blocks) {
                                if (block.type === 'text') {
                                    assistantMsg.content.push({ type: 'text', text: block.text })
                                } else if (block.type === 'thinking') {
                                    assistantMsg.content.push({ type: 'thinking', thinking: block.thinking })
                                } else if (block.type === 'tool_use') {
                                    const existingBlock = assistantMsg.content.find(
                                        b => b.type === 'tool_block' && b.toolUseId === block.tool_use_id
                                    )

                                    sessionToolUses[block.tool_use_id] = {
                                        tool_name: block.tool_name,
                                        input: block.input
                                    }

                                    if (!existingBlock) {
                                        const collapseId = `tool-collapse-${++toolUseCounter.value}`
                                        const toolBlock = createToolBlock(block.tool_name, block.input, block.tool_use_id, collapseId)
                                        assistantMsg.content.push(toolBlock)
                                    }
                                } else if (block.type === 'tool_result') {
                                    const toolInfo = sessionToolUses[block.tool_use_id]
                                    const toolName = toolInfo?.tool_name
                                    const toolInput = toolInfo?.input || {}

                                    const result = updateToolBlockResult(assistantMsg, block, toolName, toolInput)
                                    if (result === null) {
                                        lastAssistantMsg = null
                                    }
                                    if (toolInfo) delete sessionToolUses[block.tool_use_id]
                                }
                            }
                        }

                        if (assistantMsg.content.length > 0) {
                            messages.value.push(assistantMsg)
                            lastAssistantMsg = assistantMsg
                        } else {
                            lastAssistantMsg = null
                        }
                    } else if (msg.role === 'tool') {
                        if (msg.content_blocks) {
                            for (const block of msg.content_blocks) {
                                if (block.type === 'tool_result') {
                                    const targetMsg = lastAssistantMsg
                                    if (!targetMsg) continue

                                    const toolInfo = sessionToolUses[block.tool_use_id]
                                    const toolName = toolInfo?.tool_name
                                    const toolInput = toolInfo?.input || {}

                                    const result = updateToolBlockResult(targetMsg, block, toolName, toolInput)
                                    if (result === null) {
                                        lastAssistantMsg = null
                                    }
                                    if (toolInfo) delete sessionToolUses[block.tool_use_id]
                                }
                            }
                        }
                    }
                }
                autoFollowOutput.value = true
                scrollToBottom(true)
            }

            if (data.total_usage) {
                tokenUsed.value = data.total_usage.input_tokens + data.total_usage.output_tokens
            }

            if (data.working_directory) {
                currentWorkspace.value = data.working_directory
            }
        } catch (error) {
            console.error('Failed to load session:', error)
            alert('加载会话失败: ' + error.message)
        }
    }

    return {
        // State refs
        messages,
        inputText,
        isLoading,
        isStreaming,
        isTyping,
        sessionId,
        tokenUsed,
        sessions,
        sessionsLoading,
        autoFollowOutput,
        isCompactViewport,
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
        webSearchEnabled,
        sessionHasUsedWebSearch,
        inputPlaceholder,
        messagesContainer,
        messageInput,

        // Methods
        autoResize,
        handleMessagesScroll,
        handleKeydown,
        sendMessage,
        sendInterrupt,
        startNewSession,
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
        updateAutoFollowState,
    }
}
