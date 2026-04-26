import { marked } from 'marked'
import hljs from 'highlight.js'

export const escapeHtml = (text) => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
}

const highlightCode = (code, language) => {
    if (!hljs) {
        return escapeHtml(code)
    }

    try {
        if (language && hljs.getLanguage(language)) {
            return hljs.highlight(code, { language }).value
        }
        return hljs.highlightAuto(code).value
    } catch (error) {
        console.warn('Markdown code highlight failed:', error)
        return escapeHtml(code)
    }
}

export const renderMarkdown = (text) => {
    const rendered = marked.parse(text || '', {
        langPrefix: 'hljs language-',
        highlight: highlightCode,
    })

    const container = document.createElement('div')
    container.innerHTML = rendered

    for (const table of container.querySelectorAll('table')) {
        const wrapper = document.createElement('div')
        wrapper.className = 'markdown-table-wrapper'
        table.parentNode.insertBefore(wrapper, table)
        wrapper.appendChild(table)
    }

    return container.innerHTML
}
