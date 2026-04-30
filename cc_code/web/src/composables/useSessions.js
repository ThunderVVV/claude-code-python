import { ref } from 'vue'
import { hasWebReference } from '@/utils/format'
import { createUserMessage, getUserDisplayText } from '@/messageMapper/messages'

export function useSessions({
    messages,
    sessionId,
    tokenUsed,
    sessionHasUsedWebSearch,
    currentWorkspace,
    serverWorkspace,
    autoFollowOutput,
    closeNewSessionModal,
    loadModels,
    resetStreamState,
    scrollToBottom,
    toolBlocks,
}) {
    const sessions = ref([])
    const sessionsLoading = ref(false)

    const startNewSession = (workingDirectory = '') => {
        messages.value = []
        sessionId.value = null
        resetStreamState()
        tokenUsed.value = 0
        autoFollowOutput.value = true
        sessionHasUsedWebSearch.value = false
        currentWorkspace.value = workingDirectory || serverWorkspace.value || currentWorkspace.value
        closeNewSessionModal()
        loadModels()
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

    const loadSession = async (sid) => {
        messages.value = []
        sessionId.value = null
        sessionHasUsedWebSearch.value = false
        resetStreamState()

        try {
            const response = await fetch(`/api/sessions/${sid}`)
            const data = await response.json()

            if (data.error) {
                alert('Failed to load chat: ' + data.error)
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
                        const displayText = getUserDisplayText(msg)

                        if (hasWebReference(originalText) || Boolean(msg.web_enabled)) {
                            sessionHasUsedWebSearch.value = true
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
                                        item => item.type === 'tool_block' && item.toolUseId === block.tool_use_id
                                    )

                                    sessionToolUses[block.tool_use_id] = {
                                        tool_name: block.tool_name,
                                        input: block.input
                                    }

                                    if (!existingBlock) {
                                        const toolBlock = toolBlocks.createToolBlock(block.tool_name, block.input, block.tool_use_id)
                                        assistantMsg.content.push(toolBlock)
                                    }
                                } else if (block.type === 'tool_result') {
                                    const toolInfo = sessionToolUses[block.tool_use_id]
                                    const toolName = toolInfo?.tool_name
                                    const toolInput = toolInfo?.input || {}

                                    const result = toolBlocks.updateToolBlockResult(assistantMsg, block, toolName, toolInput)
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

                                    const result = toolBlocks.updateToolBlockResult(targetMsg, block, toolName, toolInput)
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
            alert('Failed to load chat: ' + error.message)
        }
    }

    return {
        sessions,
        sessionsLoading,
        startNewSession,
        loadSessions,
        loadSession,
    }
}
