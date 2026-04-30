import { ref } from 'vue'
import { applyServerUserMessage, createUserMessage } from '@/messageMapper/messages'

class QueryGuard {
    constructor() {
        this._status = 'idle'
        this._generation = 0
    }

    tryStart() {
        if (this._status === 'running') return null
        this._status = 'running'
        this._generation += 1
        return this._generation
    }

    end(generation) {
        if (this._generation !== generation || this._status !== 'running') return false
        this._status = 'idle'
        return true
    }

    forceEnd() {
        if (this._status === 'idle') return
        this._status = 'idle'
        this._generation += 1
    }

    get isActive() {
        return this._status !== 'idle'
    }
}

export function useChatStream({
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
    currentWorkspace,
    serverWorkspace,
    messageInput,
    addToHistory,
    loadSessions,
    scrollToBottom,
    toolBlocks,
}) {
    const currentAssistantMessage = ref(null)
    const accumulatedText = ref('')
    const pendingToolUses = ref({})
    const abortController = ref(null)
    const queryGuard = new QueryGuard()
    const activeRequestGeneration = ref(null)

    const resetStreamState = () => {
        currentAssistantMessage.value = null
        accumulatedText.value = ''
        pendingToolUses.value = {}
    }

    const isCurrentRequestGeneration = (generation) => activeRequestGeneration.value === generation

    const requestInterrupt = async () => {
        if (sessionId.value) {
            try {
                await fetch('/api/interrupt', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionId.value,
                        reason: 'user_interrupt'
                    })
                })
            } catch (error) {
                console.error('Interrupt error:', error)
            }
        }
    }

    const ensureAssistantMessage = () => {
        if (!currentAssistantMessage.value) {
            currentAssistantMessage.value = {
                type: 'assistant',
                content: []
            }
            messages.value.push(currentAssistantMessage.value)
        }
        return currentAssistantMessage.value
    }

    const handleEvent = (data) => {
        if (data.type === 'session_id') {
            sessionId.value = data.session_id
            return
        }

        if (data.type === 'message_complete') {
            if (data.message?.role === 'user') {
                applyServerUserMessage(messages, data.message)
            } else if (data.message?.role === 'assistant' && data.message?.usage) {
                tokenUsed.value = data.message.usage.input_tokens + data.message.usage.output_tokens
            }
            scrollToBottom()
            return
        }

        if (data.type === 'turn_complete') {
            resetStreamState()
            // A single request can contain multiple tool-execution turns.
            // Refresh sessions only after the final turn to avoid redundant
            // /api/sessions requests while the same response is still running.
            if (!data.has_more_turns) {
                void loadSessions()
            }
            scrollToBottom()
            return
        }

        isTyping.value = false

        const assistantMessage = ensureAssistantMessage()
        const content = assistantMessage.content

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
                const toolBlock = toolBlocks.createToolBlock(data.tool_name, data.input, data.tool_use_id)
                content.push(toolBlock)
            }
        } else if (data.type === 'tool_result') {
            const toolInfo = pendingToolUses.value[data.tool_use_id]
            const toolName = toolInfo?.tool_name || data.tool_name
            const toolInput = toolInfo?.input || {}
            const block = { tool_use_id: data.tool_use_id, result: data.result, is_error: data.is_error }

            const result = toolBlocks.updateToolBlockResult(currentAssistantMessage.value, block, toolName, toolInput)
            if (result === null) {
                currentAssistantMessage.value = null
            }
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
        if (!text || queryGuard.isActive) return

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

        const generation = queryGuard.tryStart()
        if (generation === null) {
            isLoading.value = false
            isStreaming.value = false
            isTyping.value = false
            return
        }

        activeRequestGeneration.value = generation
        const requestAbortController = new AbortController()
        abortController.value = requestAbortController

        autoFollowOutput.value = true
        scrollToBottom(true)

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId.value,
                    user_text: text,
                    working_directory: currentWorkspace.value || serverWorkspace.value || ''
                }),
                signal: requestAbortController.signal
            })

            if (!response.ok) {
                let errorMessage = 'Failed to send message'
                try {
                    const errorData = await response.json()
                    errorMessage = errorData.detail || errorMessage
                } catch {
                    // Ignore JSON parse failures for error responses.
                }
                throw new Error(errorMessage)
            }

            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                if (!isCurrentRequestGeneration(generation)) break

                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (!isCurrentRequestGeneration(generation)) break
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
                alert('Failed to send message: ' + error.message)
            }
        } finally {
            if (abortController.value === requestAbortController) {
                abortController.value = null
            }
            if (queryGuard.end(generation)) {
                activeRequestGeneration.value = null
                isLoading.value = false
                isStreaming.value = false
                isTyping.value = false
            }
        }
    }

    const sendInterrupt = async () => {
        if (!queryGuard.isActive && !abortController.value) return

        queryGuard.forceEnd()
        activeRequestGeneration.value = null

        resetStreamState()
        isLoading.value = false
        isStreaming.value = false
        isTyping.value = false

        if (!abortController.value) return

        const activeAbortController = abortController.value
        abortController.value = null
        activeAbortController.abort('user-cancel')

        void requestInterrupt()
    }

    return {
        sendMessage,
        sendInterrupt,
        resetStreamState,
    }
}
