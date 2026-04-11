// Icon Templates
const icons = {
    code: `<svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
    </svg>`,
    sessions: `<svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
    </svg>`,
    plus: `<svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
    </svg>`,
    send: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
    </svg>`,
    close: `<svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
    </svg>`,
    chat: `<svg class="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
    </svg>`,
    computer: `<svg class="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
    </svg>`,
    chevronRight: `<svg class="w-4 h-4 text-slate-400 collapse-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
    </svg>`
};

// State
let sessionId = null;
let isLoading = false;
let currentAssistantMessage = null;
let inputHistory = JSON.parse(localStorage.getItem('inputHistory') || '[]');
let historyIndex = -1;
let accumulatedText = '';
let pendingToolUses = {};
let toolUseCounter = 0;
let collapseCounter = 0;
let diffCounter = 0;

// DOM Elements
const messagesContainer = document.getElementById('messages');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const statusIndicator = document.getElementById('status');
const welcomeMessage = document.getElementById('welcome-message');
const sessionsBtn = document.getElementById('sessions-btn');
const newSessionBtn = document.getElementById('new-session-btn');
const sessionsModal = document.getElementById('sessions-modal');
const sessionsList = document.getElementById('sessions-list');
const tokenCountEl = document.getElementById('token-count');
const tokenUsedEl = document.getElementById('token-used');

// Configure marked
marked.setOptions({
    breaks: true,
    gfm: true
});

// Utility Functions
const escapeHtml = text => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

const renderMarkdown = text => marked.parse(text);

const appendHtml = (element, html) => {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    while (tempDiv.firstChild) {
        element.appendChild(tempDiv.firstChild);
    }
};

const isDiffContent = content => 
    content.includes('---') && content.includes('+++') || 
    content.includes('diff --git') ||
    (content.includes('-') && content.includes('+') && content.includes('@@'));

const setStatus = (text, color = 'emerald') => {
    statusIndicator.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-${color}-500"></span>
        ${text}
    `;
};

const updateTokenCount = used => {
    if (used > 0) {
        tokenCountEl.classList.remove('hidden');
        tokenUsedEl.textContent = used.toLocaleString();
    }
};

const scrollToBottom = () => {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
};

// Auto-resize textarea
messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

// Handle input history navigation
messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    } else if (e.key === 'ArrowUp' && !e.shiftKey) {
        e.preventDefault();
        navigateHistory(-1);
    } else if (e.key === 'ArrowDown' && !e.shiftKey) {
        e.preventDefault();
        navigateHistory(1);
    }
});

const navigateHistory = direction => {
    if (inputHistory.length === 0) return;
    
    historyIndex += direction;
    
    if (historyIndex < 0) {
        historyIndex = 0;
    } else if (historyIndex >= inputHistory.length) {
        historyIndex = inputHistory.length;
        messageInput.value = '';
        messageInput.style.height = 'auto';
        return;
    }
    
    messageInput.value = inputHistory[historyIndex] || '';
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
};

const addToHistory = text => {
    if (text.trim() && (inputHistory.length === 0 || inputHistory[inputHistory.length - 1] !== text)) {
        inputHistory.push(text);
        if (inputHistory.length > 100) {
            inputHistory.shift();
        }
        localStorage.setItem('inputHistory', JSON.stringify(inputHistory));
    }
    historyIndex = inputHistory.length;
};

// Diff Functions
const generateDiff = (oldContent, newContent, filePath) => {
    const oldLines = oldContent.split('\n');
    const newLines = newContent.split('\n');
    
    let diff = `diff --git a/${filePath} b/${filePath}\n`;
    diff += `--- a/${filePath}\n`;
    diff += `+++ b/${filePath}\n`;
    
    const diffResult = Diff.diffLines(oldContent, newContent);
    
    for (const part of diffResult) {
        const lines = part.value.split('\n');
        if (lines[lines.length - 1] === '') {
            lines.pop();
        }
        
        for (const line of lines) {
            if (part.added) {
                diff += `+${line}\n`;
            } else if (part.removed) {
                diff += `-${line}\n`;
            } else {
                diff += ` ${line}\n`;
            }
        }
    }
    
    return diff;
};

const renderDiff = (content, containerId) => {
    const container = document.createElement('div');
    container.className = 'diff-container my-2';
    const innerDiv = document.createElement('div');
    innerDiv.id = containerId;
    container.appendChild(innerDiv);
    
    try {
        const configuration = {
            drawFileList: false,
            matching: 'lines',
            outputFormat: 'side-by-side',
            highlight: true,
            synchronisedScroll: true,
            colorScheme: 'dark'
        };
        const diff2htmlUi = new Diff2HtmlUI(innerDiv, content, configuration);
        diff2htmlUi.draw();
        diff2htmlUi.highlightCode();
        return container.outerHTML;
    } catch (e) {
        console.error('Diff render error:', e);
        return `<pre class="mono text-xs text-slate-300 bg-slate-900/50 rounded p-2 overflow-x-auto whitespace-pre-wrap">${escapeHtml(content)}</pre>`;
    }
};

const renderToolResultWithDiff = (toolName, toolInput, result) => {
    const normalizedToolName = (toolName || '').toLowerCase();
    
    if (normalizedToolName === 'edit') {
        const oldString = toolInput.old_string || '';
        const newString = toolInput.new_string || '';
        const filePath = toolInput.file_path || 'file';
        
        if (oldString && newString) {
            const diff = generateDiff(oldString, newString, filePath);
            const containerId = `diff-container-${++diffCounter}`;
            return renderDiff(diff, containerId);
        }
    } else if (normalizedToolName === 'write') {
        const content = toolInput.content || '';
        const filePath = toolInput.file_path || 'file';
        
        if (content) {
            const diff = generateDiff('', content, filePath);
            const containerId = `diff-container-${++diffCounter}`;
            return renderDiff(diff, containerId);
        }
    }
    
    // Default: render as pre-formatted text
    return `<pre class="mono text-xs text-slate-300 bg-slate-900/50 rounded p-2 overflow-x-auto whitespace-pre-wrap">${escapeHtml(result)}</pre>`;
};

const isFileEditTool = toolName => {
    const normalized = (toolName || '').toLowerCase();
    return normalized === 'edit' || normalized === 'write';
};

const summarizeToolUse = (toolName, toolInput) => {
    if (!toolInput) return toolName;
    if (toolInput.command) {
        const cmd = toolInput.command;
        return `${toolName}: ${cmd.length > 50 ? cmd.substring(0, 47) + '...' : cmd}`;
    }
    if (toolInput.file_path) {
        const path = toolInput.file_path;
        const name = path.split('/').pop() || path;
        return `${toolName}: ${name}`;
    }
    if (toolInput.pattern) {
        const pat = toolInput.pattern;
        return `${toolName}: ${pat.length > 50 ? pat.substring(0, 47) + '...' : pat}`;
    }
    const keys = Object.keys(toolInput);
    if (keys.length > 0) {
        const preview = keys.slice(0, 3).join(', ');
        return `${toolName}: ${preview}${keys.length > 3 ? ', ...' : ''}`;
    }
    return toolName;
};

const summarizeToolResult = (toolName, toolInput, result, isError) => {
    const lines = (result || '').split('\n').filter(l => l.trim());
    const firstLine = lines[0] || '';
    
    const getBasename = () => {
        const fp = toolInput?.file_path || '';
        return fp.split('/').pop() || 'file';
    };
    
    const getPattern = () => {
        const pat = toolInput?.pattern || '';
        return pat ? `'${pat}'` : '';
    };
    
    if (isError) {
        if (toolName === 'Bash') {
            const cmd = toolInput?.command || '';
            return `Failed to run ${cmd.length > 40 ? cmd.substring(0, 37) + '...' : cmd}`;
        }
        if (['Read', 'Write', 'Edit'].includes(toolName)) {
            return `Failed to ${toolName.toLowerCase()} ${getBasename()}`;
        }
        if (['Glob', 'Grep'].includes(toolName)) {
            return `Failed to search ${getPattern()}`;
        }
        return `Failed to run ${toolName}`;
    }
    
    if (toolName === 'Read') {
        const match = result?.match(/Lines:\s*(\d+)-(\d+)\s+of\s+(\d+)/);
        if (match) {
            const [, start, end, total] = match;
            const count = parseInt(end) - parseInt(start) + 1;
            return `Read ${count} line${count > 1 ? 's' : ''} from ${getBasename()} (${start}-${end} of ${total})`;
        }
        return `Read ${getBasename()}`;
    }
    
    if (toolName === 'Glob') {
        const pat = getPattern();
        if (firstLine.includes('No files found')) {
            return `Glob found no files matching ${pat}`;
        }
        if (firstLine.startsWith('Found ')) {
            return `Glob ${firstLine.charAt(0).toLowerCase()}${firstLine.slice(1)}`;
        }
        return `Glob results matching ${pat}`;
    }
    
    if (toolName === 'Grep') {
        const pat = getPattern();
        if (firstLine === 'No matches found' || firstLine === 'No files found') {
            return `Grep found no matches for ${pat}`;
        }
        if (firstLine.startsWith('Found ')) {
            return `Grep ${firstLine.charAt(0).toLowerCase()}${firstLine.slice(1)}${pat ? ` matching ${pat}` : ''}`;
        }
        return `Grep matches for ${pat}`;
    }
    
    if (toolName === 'Write' || toolName === 'Edit') {
        return firstLine || `${toolName} completed`;
    }
    
    if (toolName === 'Bash') {
        const cmd = toolInput?.command || '';
        return `Ran: ${cmd.length > 40 ? cmd.substring(0, 37) + '...' : cmd}`;
    }
    
    return firstLine || `${toolName} completed`;
};

const createToolUseBlock = (toolName, toolInput, toolUseId, collapseId) => {
    const summary = summarizeToolUse(toolName, toolInput);
    const shouldExpand = isFileEditTool(toolName);
    const expandedClass = shouldExpand ? 'expanded' : '';
    const iconClass = shouldExpand ? 'rotated' : '';
    
    let inputDetails = '';
    const excludeKeys = isFileEditTool(toolName) ? 
        (toolName.toLowerCase() === 'edit' ? ['old_string', 'new_string'] : ['content']) : [];
    
    for (const [key, value] of Object.entries(toolInput || {})) {
        if (excludeKeys.includes(key)) continue;
        let displayValue;
        if (typeof value === 'object') {
            displayValue = JSON.stringify(value, null, 2);
        } else {
            displayValue = String(value);
        }
        if (displayValue.length > 100) {
            displayValue = displayValue.substring(0, 97) + '...';
        }
        inputDetails += `<div class="text-xs text-slate-400"><span class="text-slate-500">${escapeHtml(key)}:</span> ${escapeHtml(displayValue.split('\n')[0])}</div>`;
    }
    
    // Store tool name and input as data attributes for later use
    // Use base64 encoding for the JSON to avoid HTML attribute escaping issues
    const toolInputBase64 = btoa(encodeURIComponent(JSON.stringify(toolInput || {})));
    
    return `
        <div class="tool-block rounded-lg p-3 my-2 border-l-4 border-blue-500" 
             data-tool-use-id="${toolUseId}" 
             data-tool-name="${escapeHtml(toolName)}"
             data-tool-input="${toolInputBase64}">
            <div class="collapsible-header flex items-center justify-between rounded -m-3 p-3" onclick="toggleCollapse('${collapseId}')">
                <div class="text-sm font-medium text-blue-400 tool-summary">
                    ${escapeHtml(summary)}
                </div>
                <svg class="w-4 h-4 text-slate-400 collapse-icon ${iconClass}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </div>
            <div id="${collapseId}" class="collapsible-content ${expandedClass}">
                <div class="mt-2">
                    ${inputDetails}
                    <div class="tool-result-area mt-2"></div>
                </div>
            </div>
        </div>
    `;
};

const updateToolResult = (toolUseId, toolName, toolInput, result, isError) => {
    const toolBlock = document.querySelector(`[data-tool-use-id="${toolUseId}"]`);
    if (!toolBlock) return;
    
    const summaryEl = toolBlock.querySelector('.tool-summary');
    const resultArea = toolBlock.querySelector('.tool-result-area');
    
    if (summaryEl) {
        const summary = summarizeToolResult(toolName, toolInput, result, isError);
        const statusColor = isError ? 'text-red-400' : 'text-emerald-400';
        const statusIcon = isError ? '✗' : '●';
        summaryEl.className = `text-sm font-medium ${statusColor} tool-summary`;
        summaryEl.innerHTML = `${statusIcon} ${escapeHtml(summary)}`;
    }
    
    if (resultArea) {
        if (isFileEditTool(toolName) && !isError) {
            resultArea.innerHTML = renderToolResultWithDiff(toolName, toolInput, result);
        } else {
            const lines = result.split('\n').filter(l => l.trim());
            const preview = lines.slice(0, 6).join('\n');
            const hasMore = lines.length > 6;
            resultArea.innerHTML = `<pre class="mono text-xs text-slate-300 bg-slate-900/50 rounded p-2 overflow-x-auto whitespace-pre-wrap">${escapeHtml(preview)}${hasMore ? '\n...' : ''}</pre>`;
        }
    }
    
    // Update border color
    toolBlock.classList.remove('border-blue-500');
    toolBlock.classList.add(isError ? 'border-red-500' : 'border-emerald-500');
};

const toggleCollapse = id => {
    const el = document.getElementById(id);
    const header = el.previousElementSibling;
    const icon = header.querySelector('.collapse-icon');
    if (el) {
        el.classList.toggle('expanded');
        if (icon) icon.classList.toggle('rotated');
    }
};

// Message Creation Functions
const createUserMessage = (text, fileExpansions = []) => {
    const div = document.createElement('div');
    div.className = 'flex justify-end fade-in';
    
    let expansionsHtml = '';
    if (fileExpansions && fileExpansions.length > 0) {
        expansionsHtml = fileExpansions.map(exp => `
            <div class="file-expansion rounded-lg p-3 mb-2">
                <div class="text-sm text-blue-300 font-medium mb-1">@${escapeHtml(exp.display_path || exp.file_path)}</div>
                <pre class="mono text-xs text-slate-400 bg-slate-900/50 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto">${escapeHtml(exp.content.substring(0, 500))}${exp.content.length > 500 ? '\n... (more lines)' : ''}</pre>
            </div>
        `).join('');
    }
    
    div.innerHTML = `
        <div class="max-w-[90%]">
            ${expansionsHtml}
            <div class="message-user rounded-2xl rounded-tr-md px-4 py-3 shadow-lg">
                <p class="text-white whitespace-pre-wrap">${escapeHtml(text)}</p>
            </div>
        </div>
    `;
    return div;
};

const createAssistantMessage = () => {
    const div = document.createElement('div');
    div.className = 'flex justify-start fade-in';
    div.innerHTML = `
        <div class="w-full">
            <div class="flex items-start gap-3">
                <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center flex-shrink-0">
                    ${icons.computer}
                </div>
                <div class="flex-1 message-assistant rounded-2xl rounded-tl-md px-4 py-3 min-w-0">
                    <div class="assistant-content markdown-body"></div>
                </div>
            </div>
        </div>
    `;
    return div;
};

const createTypingIndicator = () => {
    const div = document.createElement('div');
    div.className = 'flex justify-start fade-in typing-indicator-message';
    div.innerHTML = `
        <div class="w-full">
            <div class="flex items-start gap-3">
                <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center flex-shrink-0">
                    ${icons.computer}
                </div>
                <div class="message-assistant rounded-2xl rounded-tl-md px-4 py-3">
                    <div class="typing-indicator flex gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-slate-400"></span>
                        <span class="w-2 h-2 rounded-full bg-slate-400"></span>
                        <span class="w-2 h-2 rounded-full bg-slate-400"></span>
                    </div>
                </div>
            </div>
        </div>
    `;
    return div;
};

const removeTypingIndicator = () => {
    const indicator = document.querySelector('.typing-indicator-message');
    if (indicator) {
        indicator.remove();
    }
};

const clearChat = () => {
    messagesContainer.innerHTML = '';
    messagesContainer.appendChild(welcomeMessage);
    welcomeMessage.classList.remove('hidden');
    sessionId = null;
    accumulatedText = '';
};

const startNewSession = () => {
    clearChat();
    setStatus('就绪', 'emerald');
};

// Session Management
const loadSessions = async () => {
    try {
        const response = await fetch('/api/sessions');
        const data = await response.json();
        
        if (data.error) {
            sessionsList.innerHTML = `
                <div class="p-4 text-center text-red-400 text-sm">
                    加载失败: ${escapeHtml(data.error)}
                </div>
            `;
            return;
        }
        
        if (!data.sessions || data.sessions.length === 0) {
            sessionsList.innerHTML = `
                <div class="p-4 text-center text-slate-400 text-sm">
                    暂无会话
                </div>
            `;
            return;
        }
        
        sessionsList.innerHTML = data.sessions.map(sess => `
            <div class="session-item p-4 border-b border-slate-700/50 cursor-pointer transition-colors" onclick="loadSession('${sess.session_id}')">
                <div class="flex items-center justify-between">
                    <div class="flex-1 min-w-0">
                        <h3 class="text-white font-medium truncate">${escapeHtml(sess.title || 'Untitled')}</h3>
                        <p class="text-xs text-slate-500 mt-1">
                            ${escapeHtml(sess.working_directory || '')} • ${sess.message_count || 0} 条消息
                        </p>
                    </div>
                    <svg class="w-4 h-4 text-slate-500 flex-shrink-0 ml-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load sessions:', error);
        sessionsList.innerHTML = `
            <div class="p-4 text-center text-red-400 text-sm">
                加载失败: ${escapeHtml(error.message)}
            </div>
        `;
    }
};

const loadSession = async sessionIdToLoad => {
    try {
        closeSessionsModal();
        clearChat();
        
        const response = await fetch(`/api/sessions/${sessionIdToLoad}`);
        const data = await response.json();
        
        if (data.error) {
            alert('加载会话失败: ' + data.error);
            return;
        }
        
        sessionId = sessionIdToLoad;
        
        // Load messages
        if (data.messages && data.messages.length > 0) {
            welcomeMessage.classList.add('hidden');
            
            let lastAssistantMsg = null;
            let lastAssistantContentEl = null;
            let sessionToolUses = {}; // Track tool uses for this session
            
            for (const msg of data.messages) {
                if (msg.role === 'user') {
                    const fileExpansions = msg.file_expansions || [];
                    const originalText = msg.original_text || '';
                    let displayText = '';
                    
                    if (msg.content_blocks) {
                        for (const block of msg.content_blocks) {
                            if (block.type === 'text') {
                                displayText = block.text;
                                break;
                            }
                        }
                    } else {
                        displayText = msg.content || '';
                    }
                    
                    messagesContainer.appendChild(createUserMessage(originalText || displayText, fileExpansions));
                    lastAssistantMsg = null;
                    lastAssistantContentEl = null;
                    sessionToolUses = {};
                    
                } else if (msg.role === 'assistant') {
                    const assistantMsg = createAssistantMessage();
                    const contentEl = assistantMsg.querySelector('.assistant-content');
                    lastAssistantMsg = assistantMsg;
                    lastAssistantContentEl = contentEl;
                    
                    if (msg.content_blocks && msg.content_blocks.length > 0) {
                        for (const block of msg.content_blocks) {
                            if (block.type === 'text') {
                                // Use text-container wrapper for consistency with streaming
                                const textContainer = document.createElement('div');
                                textContainer.className = 'text-container';
                                textContainer.innerHTML = renderMarkdown(block.text);
                                contentEl.appendChild(textContainer);
                            } else if (block.type === 'thinking') {
                                const thinkingSpan = document.createElement('span');
                                thinkingSpan.className = 'text-slate-500 italic thinking-block';
                                thinkingSpan.textContent = block.thinking;
                                contentEl.appendChild(thinkingSpan);
                            } else if (block.type === 'tool_use') {
                                // Check if tool block already exists
                                const existingBlock = document.querySelector(`[data-tool-use-id="${block.tool_use_id}"]`);
                                if (existingBlock) {
                                    console.warn('Tool block already exists in history, skipping:', block.tool_use_id, block.tool_name);
                                    continue;
                                }
                                
                                // Save tool use info
                                sessionToolUses[block.tool_use_id] = {
                                    tool_name: block.tool_name,
                                    input: block.input
                                };
                                
                                const collapseId = `tool-collapse-${++toolUseCounter}`;
                                appendHtml(contentEl, createToolUseBlock(block.tool_name, block.input, block.tool_use_id, collapseId));
                            } else if (block.type === 'tool_result') {
                                const toolInfo = sessionToolUses[block.tool_use_id];
                                
                                if (toolInfo) {
                                    updateToolResult(block.tool_use_id, toolInfo.tool_name, toolInfo.input, block.result, block.is_error);
                                    delete sessionToolUses[block.tool_use_id];
                                } else {
                                    // Tool use block should already exist, just find and update it
                                    const toolBlock = document.querySelector(`[data-tool-use-id="${block.tool_use_id}"]`);
                                    if (toolBlock) {
                                        const summaryEl = toolBlock.querySelector('.tool-summary');
                                        const resultArea = toolBlock.querySelector('.tool-result-area');
                                        
                                        if (summaryEl) {
                                            const lines = (block.result || '').split('\n').filter(l => l.trim());
                                            const firstLine = lines[0] || '';
                                            const summary = firstLine || 'Tool completed';
                                            const statusColor = block.is_error ? 'text-red-400' : 'text-emerald-400';
                                            const statusIcon = block.is_error ? '✗' : '●';
                                            summaryEl.className = `text-sm font-medium ${statusColor} tool-summary`;
                                            summaryEl.innerHTML = `${statusIcon} ${escapeHtml(summary)}`;
                                        }
                                        
                                        if (resultArea) {
                                            const lines = (block.result || '').split('\n').filter(l => l.trim());
                                            const preview = lines.slice(0, 6).join('\n');
                                            const hasMore = lines.length > 6;
                                            resultArea.innerHTML = `<pre class="mono text-xs text-slate-300 bg-slate-900/50 rounded p-2 overflow-x-auto whitespace-pre-wrap">${escapeHtml(preview)}${hasMore ? '\n...' : ''}</pre>`;
                                        }
                                        
                                        toolBlock.classList.remove('border-blue-500');
                                        toolBlock.classList.add(block.is_error ? 'border-red-500' : 'border-emerald-500');
                                    }
                                }
                            }
                        }
                    } else {
                        contentEl.innerHTML = renderMarkdown(msg.content || '');
                    }
                    
                    messagesContainer.appendChild(assistantMsg);
                    
                } else if (msg.role === 'tool') {
                    // Tool result messages - append to last assistant message
                    if (msg.content_blocks) {
                        for (const block of msg.content_blocks) {
                            if (block.type === 'tool_result') {
                                let targetContentEl = lastAssistantContentEl;
                                
                                // If no assistant message exists, create one
                                if (!targetContentEl) {
                                    const assistantMsg = createAssistantMessage();
                                    messagesContainer.appendChild(assistantMsg);
                                    targetContentEl = assistantMsg.querySelector('.assistant-content');
                                    lastAssistantMsg = assistantMsg;
                                    lastAssistantContentEl = targetContentEl;
                                }
                                
                                const toolInfo = sessionToolUses[block.tool_use_id];
                                
                                if (toolInfo) {
                                    updateToolResult(block.tool_use_id, toolInfo.tool_name, toolInfo.input, block.result, block.is_error);
                                    delete sessionToolUses[block.tool_use_id];
                                } else {
                                    // Tool use block should already exist, just find and update it
                                    const toolBlock = document.querySelector(`[data-tool-use-id="${block.tool_use_id}"]`);
                                    if (toolBlock) {
                                        const summaryEl = toolBlock.querySelector('.tool-summary');
                                        const resultArea = toolBlock.querySelector('.tool-result-area');
                                        
                                        if (summaryEl) {
                                            const lines = (block.result || '').split('\n').filter(l => l.trim());
                                            const firstLine = lines[0] || '';
                                            const summary = firstLine || 'Tool completed';
                                            const statusColor = block.is_error ? 'text-red-400' : 'text-emerald-400';
                                            const statusIcon = block.is_error ? '✗' : '●';
                                            summaryEl.className = `text-sm font-medium ${statusColor} tool-summary`;
                                            summaryEl.innerHTML = `${statusIcon} ${escapeHtml(summary)}`;
                                        }
                                        
                                        if (resultArea) {
                                            const lines = (block.result || '').split('\n').filter(l => l.trim());
                                            const preview = lines.slice(0, 6).join('\n');
                                            const hasMore = lines.length > 6;
                                            resultArea.innerHTML = `<pre class="mono text-xs text-slate-300 bg-slate-900/50 rounded p-2 overflow-x-auto whitespace-pre-wrap">${escapeHtml(preview)}${hasMore ? '\n...' : ''}</pre>`;
                                        }
                                        
                                        toolBlock.classList.remove('border-blue-500');
                                        toolBlock.classList.add(block.is_error ? 'border-red-500' : 'border-emerald-500');
                                    }
                                }
                            }
                        }
                    }
                }
            }
            scrollToBottom();
        }
        
        // Update token count if available
        if (data.total_usage) {
            updateTokenCount(data.total_usage.input_tokens + data.total_usage.output_tokens);
        }
    } catch (error) {
        console.error('Failed to load session:', error);
        alert('加载会话失败: ' + error.message);
    }
};

const openSessionsModal = () => {
    sessionsModal.classList.remove('hidden');
    sessionsModal.classList.add('flex');
    loadSessions();
};

const closeSessionsModal = () => {
    sessionsModal.classList.add('hidden');
    sessionsModal.classList.remove('flex');
};

// Event Listeners
sessionsBtn.addEventListener('click', openSessionsModal);
newSessionBtn.addEventListener('click', startNewSession);

chatForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const text = messageInput.value.trim();
    if (!text || isLoading) return;

    // Clear welcome message
    if (welcomeMessage && !welcomeMessage.classList.contains('hidden')) {
        welcomeMessage.classList.add('hidden');
    }

    // Add to history
    addToHistory(text);

    // Add user message
    messagesContainer.appendChild(createUserMessage(text));
    scrollToBottom();

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Set loading state
    isLoading = true;
    sendBtn.disabled = true;
    setStatus('思考中...', 'yellow');
    accumulatedText = '';

    // Add typing indicator
    const typingIndicator = createTypingIndicator();
    messagesContainer.appendChild(typingIndicator);
    scrollToBottom();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                user_text: text
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        currentAssistantMessage = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                
                try {
                    const data = JSON.parse(line.slice(6));
                    handleEvent(data);
                } catch (err) {
                    console.error('Parse error:', err);
                }
            }
        }
    } catch (error) {
        console.error('Chat error:', error);
        setStatus('错误', 'red');
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        setStatus('就绪', 'emerald');
        removeTypingIndicator();
    }
});

const handleEvent = data => {
    removeTypingIndicator();
    setStatus('输出中...', 'blue');

    if (data.type === 'session_id') {
        sessionId = data.session_id;
        return;
    }

    if (!currentAssistantMessage) {
        currentAssistantMessage = createAssistantMessage();
        messagesContainer.appendChild(currentAssistantMessage);
    }

    const contentEl = currentAssistantMessage.querySelector('.assistant-content');

    if (data.type === 'text') {
        accumulatedText += data.text;
        // Find or create a text container
        let textContainer = contentEl.querySelector('.text-container');
        if (!textContainer) {
            textContainer = document.createElement('div');
            textContainer.className = 'text-container';
            // Append to end to maintain order
            contentEl.appendChild(textContainer);
        }
        textContainer.innerHTML = renderMarkdown(accumulatedText);
    } else if (data.type === 'thinking') {
        const thinkingSpan = document.createElement('span');
        thinkingSpan.className = 'text-slate-500 italic thinking-block';
        thinkingSpan.textContent = data.thinking;
        // Append to end to maintain order
        contentEl.appendChild(thinkingSpan);
    } else if (data.type === 'tool_use') {
        // Check if tool block already exists
        const existingBlock = document.querySelector(`[data-tool-use-id="${data.tool_use_id}"]`);
        
        // Always save to pendingToolUses for later result update
        pendingToolUses[data.tool_use_id] = {
            tool_name: data.tool_name,
            input: data.input
        };
        
        if (!existingBlock) {
            const collapseId = `tool-collapse-${++toolUseCounter}`;
            appendHtml(contentEl, createToolUseBlock(data.tool_name, data.input, data.tool_use_id, collapseId));
        }
    } else if (data.type === 'tool_result') {
        const toolInfo = pendingToolUses[data.tool_use_id];
        
        // Get tool name and input from pending, or from DOM data attributes
        let toolName = toolInfo?.tool_name;
        let toolInput = toolInfo?.input;
        
        // If not in pending, try to get from the tool block's data attributes
        if (!toolInfo) {
            const toolBlock = document.querySelector(`[data-tool-use-id="${data.tool_use_id}"]`);
            if (toolBlock) {
                toolName = toolBlock.getAttribute('data-tool-name');
                const inputBase64 = toolBlock.getAttribute('data-tool-input');
                if (inputBase64) {
                    try {
                        toolInput = JSON.parse(decodeURIComponent(atob(inputBase64)));
                    } catch (e) {
                        console.error('Failed to parse tool input:', e);
                        toolInput = {};
                    }
                }
            }
        }
        
        // Always use updateToolResult which handles diff rendering
        if (toolName) {
            updateToolResult(data.tool_use_id, toolName, toolInput || {}, data.result, data.is_error);
            if (toolInfo) {
                delete pendingToolUses[data.tool_use_id];
            }
        }
    } else if (data.type === 'message_complete') {
        // Message complete - we could do something here
    } else if (data.type === 'error') {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-red-400 bg-red-900/30 border border-red-800 rounded-lg p-3 my-2';
        errorDiv.textContent = data.error;
        contentEl.appendChild(errorDiv);
    } else if (data.type === 'turn_complete') {
        currentAssistantMessage = null;
        accumulatedText = '';
        pendingToolUses = {};
        setStatus('就绪', 'emerald');
    }

    scrollToBottom();
};

// Close modal on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeSessionsModal();
    }
});
