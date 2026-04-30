import { hasWebReference } from '@/utils/format'

export const createUserMessage = (text, options = {}) => ({
    type: 'user',
    text,
    originalText: options.originalText || text,
    fileExpansions: options.fileExpansions || [],
    webEnabled: options.webEnabled ?? hasWebReference(options.originalText || text)
})

export const applyServerUserMessage = (messages, message) => {
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

export const getUserDisplayText = (message) => {
    if (message.content_blocks) {
        const textBlock = message.content_blocks.find(block => block.type === 'text')
        if (textBlock) return textBlock.text
    }
    return message.content || ''
}
