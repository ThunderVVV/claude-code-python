import { marked } from 'marked'
import hljs from 'highlight.js'
import { markedHighlight } from 'marked-highlight'

// 注册highlight扩展
marked.use(markedHighlight({
    langPrefix: 'hljs language-',
    highlight: (code, language) => {
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
}))

export const escapeHtml = (text) => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
}

export const renderMarkdown = (text) => {
    const rendered = marked.parse(text || '')

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
