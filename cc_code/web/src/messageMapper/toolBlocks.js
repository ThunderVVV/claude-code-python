import { getNonEmptyLines } from '@/utils/format'
import { createDiff } from '@/utils/diffViewer'

export const summarizeToolUse = (toolName, toolInput) => {
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

export const summarizeToolResult = (toolName, toolInput, result, isError) => {
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

export const isFileEditTool = (toolName) => ['edit', 'write'].includes((toolName || '').toLowerCase())

const generateDiffData = (toolName, toolInput) => {
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

export const createToolBlockManager = ({ messages }) => {
    let toolUseCounter = 0
    let diffMessageCounter = 0

    const createToolBlock = (toolName, toolInput, toolUseId) => {
        const summary = summarizeToolUse(toolName, toolInput)
        const shouldExpand = isFileEditTool(toolName)

        return {
            type: 'tool_block',
            toolName,
            toolInput,
            toolUseId,
            collapseId: `tool-collapse-${++toolUseCounter}`,
            summary,
            expanded: shouldExpand,
            result: null,
            isError: false
        }
    }

    const createDiffMessage = (diffData, toolName, toolInput) => ({
        type: 'diff',
        diffId: `diff-message-${++diffMessageCounter}`,
        diffData,
        toolName,
        filePath: toolInput?.file_path || 'file'
    })

    const appendDiffMessage = (diffData, toolName, toolInput, afterMessage = null) => {
        if (!diffData) return null

        const diffMessage = createDiffMessage(diffData, toolName, toolInput)
        const targetIndex = afterMessage ? messages.value.indexOf(afterMessage) : -1

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

    const updateToolBlockResult = (targetMessage, block, toolName, toolInput) => {
        const diffData = !block.is_error && isFileEditTool(toolName)
            ? generateDiffData(toolName, toolInput)
            : null

        if (diffData) {
            appendDiffMessage(diffData, toolName, toolInput, targetMessage)
            if (removeToolBlock(targetMessage, block.tool_use_id)) {
                return null
            }
        } else {
            const toolBlock = targetMessage.content.find(
                item => item.type === 'tool_block' && item.toolUseId === block.tool_use_id
            )
            if (toolBlock) {
                toolBlock.result = block.result
                toolBlock.isError = block.is_error
                toolBlock.summary = summarizeToolResult(toolName, toolInput, block.result, block.is_error)
            }
        }
        return targetMessage
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

    return {
        createToolBlock,
        updateToolBlockResult,
        toggleCollapse,
    }
}
